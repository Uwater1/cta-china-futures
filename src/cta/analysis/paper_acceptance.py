"""纸面交易验收(只读;设计日志十八):数据完整率、成交率、权益对账、持仓对账、滑点校准、失败与漂移、共同日期、故障演练证据、champion/challenger 配对差。

只读约定:本模块只读取 paper*/ 目录(以及 git 历史、交易所行情文件),任何输出都写到调用方指定的输出目录;不修改账本、不新增账本、不选赢家。
权益对账按账本真实语义:当日权益变化 = 当日成交产生的 realized_pnl + 当日持仓盯市盈亏 − 当日手续费(滑点已在成交价里,不再扣)。
持仓对账(18.2 第 4 项):前一日日志持仓 + 当日成交腿 = 当日日志持仓 = 前一日订单目标(各腿成交的前提下);最新一日再与 state.json、positions.csv 核对。
滑点校准(18.2 第 3 项,只报告):每条成交腿的交易所开盘价 vs 当日成交均价(成交额 / 成交量 / 乘数),以跳数计。
失败记录除工作区外还读 git 历史:成功重放会删掉 FAILED.json 并覆盖当日日志,只看工作区会把修复过的失败日数成 0。
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from cta.analysis.stats import paired_differences, paired_summary
from cta.data.exchanges.calendar import load_holidays
from cta.instruments.specs import InstrumentTable, load_instruments

# 能改变五本账订单、成交与权益的文件;其余提交(文档、研究代码、纸面数据本身)不会。各账本的配置文件另从协议清单 books.*.config 取。
BOOK_CODE_PATHS = [
    "src/cta",
    "scripts/paper_daily.sh",
    "requirements.txt",
    "requirements-dev.txt",
    "configs/instruments.yaml",
    "configs/holidays.csv",
]
# 交易所行情 turnover 的单位:上期所、能源中心为万元,大商所、郑商所为元(2026-09-23 → 10-15 逐日核对:
# turnover/(volume×乘数) 换算后与结算价之比的中位数都在 1 ± 0.01 内)。
TURNOVER_UNIT = {"SHFE": 1e4, "INE": 1e4, "DCE": 1.0, "CZCE": 1.0}

EQUITY_COLS = [
    "equity",
    "realized_pnl",
    "fees_paid",
    "slippage_paid",
    "margin_used",
    "n_positions",
    "pnl_by_symbol",
]
DRIFT_CATEGORY = {
    "config_digest": "策略配置变化",
    "instruments_digest": "参数表变化",
    "git_sha": "代码变化",
    "primary_sha": "数据版本变化(米筐段)",
    "secondary_sha": "数据增量(交易所段,预期每日变化)",
}


@dataclass
class Book:
    name: str
    root: Path
    role: str
    equity: pd.DataFrame
    fills: pd.DataFrame
    snapshots: pd.DataFrame
    logs: dict[str, dict[str, Any]] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    failed: dict[str, Any] | None = None


@dataclass
class AcceptanceResult:
    status: str  # PRELIMINARY | FINAL
    asof: pd.Timestamp
    reconciliation_ok: bool
    positions_ok: bool
    completeness_ok: bool
    undeclared_drift: int
    drills_status: str
    report_path: Path
    summary: pd.DataFrame


# ---------- 读取 ----------
def load_protocol(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data


def _sha_from_manifest(s: str) -> str:
    m = re.search(r"'sha256':\s*'([0-9a-f]+)'", str(s))
    return m.group(1) if m else ""


def _coverage_from_manifest(s: str) -> str:
    m = re.search(r"'coverage':\s*'([^']*)'", str(s))
    return m.group(1) if m else ""


def load_book(root: Path, name: str, role: str) -> Book:
    root = Path(root)
    eq_path = root / "equity.csv"
    if eq_path.exists():
        eq = pd.read_csv(eq_path)
        eq["date"] = pd.to_datetime(eq["date"])
        eq = eq.set_index("date").sort_index()
    else:
        eq = pd.DataFrame(columns=EQUITY_COLS)
    parts = []
    for f in sorted((root / "fills").glob("*.csv")) if (root / "fills").exists() else []:
        try:
            df = pd.read_csv(f)
        except pd.errors.EmptyDataError:
            continue
        if df.empty:
            continue
        df["file_date"] = pd.Timestamp(f.stem)
        parts.append(df)
    fills = (
        pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["date", "symbol", "status"])
    )
    if "date" in fills.columns and len(fills):
        fills["date"] = pd.to_datetime(fills["date"])
    snaps = []
    for d in sorted((root / "orders").glob("*/snapshot.json")) if (root / "orders").exists() else []:
        try:
            j = json.loads(d.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        man = j.get("data_manifest", {}) or {}
        snaps.append(
            {
                "date": pd.Timestamp(j.get("asof", d.parent.name)),
                "config_digest": str(j.get("config_digest", "")),
                "instruments_digest": str(j.get("instruments_digest", "")),
                "git_sha": str(j.get("git_sha", "")),
                "primary_sha": _sha_from_manifest(man.get("primary", "")) if isinstance(man, dict) else "",
                "secondary_sha": _sha_from_manifest(man.get("secondary", ""))
                if isinstance(man, dict)
                else "",
                "coverage": _coverage_from_manifest(man.get("secondary", ""))
                if isinstance(man, dict)
                else "",
            }
        )
    snapshots = (
        pd.DataFrame(snaps).set_index("date").sort_index()
        if snaps
        else pd.DataFrame(
            columns=[
                "config_digest",
                "instruments_digest",
                "git_sha",
                "primary_sha",
                "secondary_sha",
                "coverage",
            ]
        )
    )
    logs: dict[str, dict[str, Any]] = {}
    for f in sorted((root / "log").glob("*.json")) if (root / "log").exists() else []:
        try:
            logs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logs[f.stem] = {"date": f.stem, "unreadable": True}
    state = (
        json.loads((root / "state.json").read_text(encoding="utf-8"))
        if (root / "state.json").exists()
        else {}
    )
    failed = (
        json.loads((root / "FAILED.json").read_text(encoding="utf-8"))
        if (root / "FAILED.json").exists()
        else None
    )
    return Book(name, root, role, eq, fills, snapshots, logs, state, failed)


# ---------- 工程验收 ----------
def expected_days(
    start: pd.Timestamp, end: pd.Timestamp, holidays: pd.DatetimeIndex | None = None
) -> pd.DatetimeIndex:
    """预期交易日:周一至周五且不在公告休市日(与纸面 runner 同一规则)。"""
    hol = holidays if holidays is not None else load_holidays()
    days = [d for d in pd.bdate_range(start, end) if d not in hol]
    return pd.DatetimeIndex(days)


def completeness(book: Book, days: pd.DatetimeIndex) -> dict[str, Any]:
    have = pd.DatetimeIndex(book.equity.index) if len(book.equity) else pd.DatetimeIndex([])
    missing = [d for d in days if d not in have]
    return {
        "book": book.name,
        "role": book.role,
        "expected": int(len(days)),
        "present": int(len(days) - len(missing)),
        "rate": (len(days) - len(missing)) / len(days) if len(days) else np.nan,
        "missing": ",".join(str(d.date()) for d in missing),
    }


def fill_stats(book: Book, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame]:
    f = book.fills
    if f.empty or "date" not in f.columns:
        return {"book": book.name, "filled": 0, "blocked": 0, "fill_rate": np.nan}, pd.DataFrame()
    w = f[(f["date"] >= start) & (f["date"] <= end)]
    filled = int((w["status"] == "filled").sum())
    blocked_df = w[w["status"] != "filled"].copy()
    blocked = int(len(blocked_df))
    cols = [
        c
        for c in ("date", "symbol", "contract", "lots", "status", "reason", "leg")
        if c in blocked_df.columns
    ]
    blocked_df = blocked_df[cols]
    blocked_df.insert(0, "book", book.name)
    rate = filled / (filled + blocked) if (filled + blocked) else np.nan
    return {"book": book.name, "filled": filled, "blocked": blocked, "fill_rate": rate}, blocked_df


def _mtm_sum(cell: Any) -> float:
    if isinstance(cell, str) and cell.strip():
        try:
            return float(sum(float(v) for v in json.loads(cell).values()))
        except (json.JSONDecodeError, TypeError, ValueError):
            return float("nan")
    return 0.0


def reconcile_book(book: Book, start: pd.Timestamp, end: pd.Timestamp, abs_tol: float = 1e-4) -> pd.DataFrame:
    """逐日:Δ权益 vs Δ已实现 + 当日盯市 − Δ手续费;另用当日 fills 交叉核对手续费(与已实现盈亏,若有该列)。
    第一行(账本开立日)以 cash_start 为基;换月/多腿日:已实现与手续费都是当日累计量之差,天然涵盖多腿;无成交日:Δ已实现 = Δ手续费 = 0。"""
    eq = book.equity
    rows: list[dict[str, Any]] = []
    if eq.empty:
        return pd.DataFrame(
            columns=["book", "date", "d_equity", "d_realized", "mtm", "d_fees", "expected", "diff", "ok"]
        )
    cash_start = float(book.state.get("cash_start", eq["equity"].iloc[0]))
    idx = pd.DatetimeIndex(eq.index)
    for i, d in enumerate(idx):
        if d < start or d > end:
            continue
        cur = eq.iloc[i]
        if i == 0:
            prev_eq, prev_real, prev_fee = cash_start, 0.0, 0.0
        else:
            p = eq.iloc[i - 1]
            prev_eq, prev_real, prev_fee = float(p["equity"]), float(p["realized_pnl"]), float(p["fees_paid"])
        d_eq = float(cur["equity"]) - prev_eq
        d_real = float(cur["realized_pnl"]) - prev_real
        d_fee = float(cur["fees_paid"]) - prev_fee
        mtm = _mtm_sum(cur.get("pnl_by_symbol", "{}"))
        expected = d_real + mtm - d_fee
        diff = d_eq - expected
        fills_fee = fills_real = float("nan")
        fills_fee_diff = float("nan")
        if not book.fills.empty and "date" in book.fills.columns:
            fd = book.fills[(book.fills["date"] == d) & (book.fills["status"] == "filled")]
            if len(fd):
                fills_fee = float(fd["fee"].sum()) if "fee" in fd.columns else float("nan")
                if "realized_pnl" in fd.columns:
                    fills_real = float(fd["realized_pnl"].fillna(0.0).sum())
            else:
                fills_fee = 0.0
        if np.isfinite(fills_fee):
            fills_fee_diff = fills_fee - d_fee
        ok = bool(
            np.isfinite(diff)
            and abs(diff) <= abs_tol
            and (not np.isfinite(fills_fee_diff) or abs(fills_fee_diff) <= abs_tol)
        )
        rows.append(
            {
                "book": book.name,
                "date": d,
                "d_equity": d_eq,
                "d_realized": d_real,
                "mtm": mtm,
                "d_fees": d_fee,
                "expected": expected,
                "diff": diff,
                "fills_fee": fills_fee,
                "fills_fee_diff": fills_fee_diff,
                "fills_realized": fills_real,
                "ok": ok,
            }
        )
    return pd.DataFrame(rows)


def weekly_reconciliation(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["book", "week", "n_days", "max_abs_diff", "ok"])
    d = daily.copy()
    d["week"] = pd.DatetimeIndex(d["date"]).strftime("%G-W%V")
    g = d.groupby(["book", "week"])
    out = pd.DataFrame(
        {
            "n_days": g.size(),
            "max_abs_diff": g["diff"].apply(lambda s: float(np.nanmax(np.abs(s.to_numpy(dtype=float))))),
            "ok": g["ok"].all(),
        }
    ).reset_index()
    return out


def failures(book: Book, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for day, j in book.logs.items():
        try:
            d = pd.Timestamp(day)
        except ValueError:
            continue
        if d < start or d > end:
            continue
        if "failed" in j:
            f = j["failed"] if isinstance(j["failed"], dict) else {"stage": "?", "error": str(j["failed"])}
            rows.append(
                {
                    "book": book.name,
                    "date": d,
                    "stage": f.get("stage", "?"),
                    "error": str(f.get("error", ""))[:200],
                    "source": "log.failed",
                }
            )
        if "orders_error" in j:
            rows.append(
                {
                    "book": book.name,
                    "date": d,
                    "stage": "orders",
                    "error": str(j["orders_error"])[:200],
                    "source": "log.orders_error(旧格式,已被吞的失败)",
                }
            )
    if book.failed is not None:
        rows.append(
            {
                "book": book.name,
                "date": pd.Timestamp(book.failed.get("date", start)),
                "stage": book.failed.get("stage", "?"),
                "error": str(book.failed.get("error", ""))[:200],
                "source": "FAILED.json(当前存在)",
            }
        )
    return pd.DataFrame(rows, columns=["book", "date", "stage", "error", "source"])


def drift(
    book: Book,
    start: pd.Timestamp,
    end: pd.Timestamp,
    protocol: dict[str, Any],
    root: Path | None = None,
    paths: list[str] | None = None,
) -> pd.DataFrame:
    """相邻订单快照之间的摘要变化(含验收期首日与其前一次快照的比较),按字段分类;与协议清单里声明的切换比对。
    git_sha 每个纸面提交都会变,所以给了 root 时先用 git 看两个版本之间账本运行路径(`paths`)有没有改动:
    没有 → 记为"仅非账本路径的提交",算已声明;有 → 要么在清单里(同日或 from → to),要么列出改动文件、算未声明。"""
    s = book.snapshots
    rows: list[dict[str, Any]] = []
    if s.empty:
        return pd.DataFrame(
            rows, columns=["book", "date", "field", "old", "new", "category", "declared", "note"]
        )
    declared = protocol.get("declared_transitions", []) or []
    paths = paths if paths is not None else book_code_paths(protocol)
    before = s[s.index < start]
    window = s[(s.index >= start) & (s.index <= end)]
    seq = pd.concat([before.tail(1), window]) if len(before) else window
    fields = ["config_digest", "instruments_digest", "git_sha", "primary_sha", "secondary_sha"]
    prev: pd.Series[Any] | None = None
    for d, row in seq.iterrows():
        if prev is not None and pd.Timestamp(str(d)) >= start:
            for f in fields:
                if str(row[f]) != str(prev[f]):
                    old, new = str(prev[f]), str(row[f])
                    dec = [t for t in declared if _transition_matches(t, pd.Timestamp(str(d)), f, old, new)]
                    is_dec = bool(dec) or f == "secondary_sha"
                    note = (
                        str(dec[0].get("note", ""))
                        if dec
                        else ("交易所数据每日增量" if f == "secondary_sha" else "未在协议清单中声明")
                    )
                    if f == "git_sha" and root is not None:
                        files = code_change(root, old, new, paths)
                        if files is None:
                            note += ";无法用 git 判定改动范围(非 git 仓库或版本不在仓库)"
                        elif not files:
                            is_dec = True
                            note = (
                                "仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、"
                                "五本账配置、参数表、假期表无改动" + (";清单声明:" + note if dec else "")
                            )
                        else:
                            shown = ", ".join(files[:4]) + ("…" if len(files) > 4 else "")
                            note += f";账本路径改动 {len(files)} 个文件:{shown}"
                    rows.append(
                        {
                            "book": book.name,
                            "date": pd.Timestamp(str(d)),
                            "field": f,
                            "old": old,
                            "new": new,
                            "category": DRIFT_CATEGORY[f],
                            "declared": is_dec,
                            "note": note,
                        }
                    )
        prev = row
    exp_cfg = ((protocol.get("books") or {}).get(book.name) or {}).get("expected_config_digest")
    exp_ins = protocol.get("expected_instruments_digest")
    for d, row in window.iterrows():
        if exp_cfg and str(row["config_digest"]) != str(exp_cfg):
            rows.append(
                {
                    "book": book.name,
                    "date": pd.Timestamp(str(d)),
                    "field": "config_digest",
                    "old": str(exp_cfg),
                    "new": str(row["config_digest"]),
                    "category": "与协议清单不符",
                    "declared": False,
                    "note": "快照配置摘要 ≠ 协议清单预期",
                }
            )
        if exp_ins and str(row["instruments_digest"]) != str(exp_ins):
            rows.append(
                {
                    "book": book.name,
                    "date": pd.Timestamp(str(d)),
                    "field": "instruments_digest",
                    "old": str(exp_ins),
                    "new": str(row["instruments_digest"]),
                    "category": "与协议清单不符",
                    "declared": False,
                    "note": "快照参数表摘要 ≠ 协议清单预期",
                }
            )
    return pd.DataFrame(rows, columns=["book", "date", "field", "old", "new", "category", "declared", "note"])


def common_range(books: list[Book]) -> dict[str, Any]:
    idx: pd.DatetimeIndex | None = None
    for b in books:
        bi = pd.DatetimeIndex(b.equity.index)
        idx = bi if idx is None else idx.intersection(bi)
    if idx is None or len(idx) == 0:
        return {"start": None, "end": None, "n_common_days": 0}
    return {"start": str(idx.min().date()), "end": str(idx.max().date()), "n_common_days": int(len(idx))}


# ---------- git(只读)与账本运行路径 ----------
def _git(root: Path, *args: str) -> str | None:
    """只读 git 调用;没有 git、不是仓库或对象不存在时返回 None,调用方按"无法判定"处理。"""
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        return None


def _is_repo_root(root: Path) -> bool:
    """root 本身就是 git 仓库的顶层目录(避免 tmp 目录落在别的仓库里时读错仓库)。"""
    out = _git(root, "rev-parse", "--show-toplevel")
    if out is None:
        return False
    try:
        return Path(out.strip()).resolve() == Path(root).resolve()
    except OSError:
        return False


def book_code_paths(protocol: dict[str, Any]) -> list[str]:
    """能改变五本账订单/成交/权益的文件:BOOK_CODE_PATHS 加协议清单里各账本的配置文件。"""
    cfgs = sorted(
        {
            str(v["config"])
            for v in (protocol.get("books") or {}).values()
            if isinstance(v, dict) and v.get("config")
        }
    )
    return BOOK_CODE_PATHS + cfgs


def code_change(root: Path, old_sha: str, new_sha: str, paths: list[str]) -> list[str] | None:
    """两个代码版本之间账本运行路径上改动的文件(不含 .md);无法判定(非仓库、版本不在仓库)→ None。"""
    if not old_sha or not new_sha or not _is_repo_root(root):
        return None
    out = _git(root, "diff", "--name-only", old_sha, new_sha, "--", *paths)
    if out is None:
        return None
    return [f for f in out.split() if not f.endswith(".md")]


def _sha_eq(a: str, b: str) -> bool:
    a, b = str(a), str(b)
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def _transition_matches(t: dict[str, Any], d: pd.Timestamp, f: str, old: str, new: str) -> bool:
    """协议清单的一条声明:同日同字段(effective + fields),或 git_sha 的 from → to(短 sha 前缀即可)。"""
    if f not in (t.get("fields") or []):
        return False
    if t.get("effective") and pd.Timestamp(t["effective"]) == d:
        return True
    if f == "git_sha" and t.get("from") and t.get("to"):
        return _sha_eq(old, str(t["from"])) and _sha_eq(new, str(t["to"]))
    return False


FAIL_COLS = ["book", "date", "stage", "error", "source"]


def historical_failures(
    root: Path, book_dirs: dict[str, str], start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """从 git 历史读出曾提交过的 FAILED.json(每日脚本把失败日连同 FAILED.json 一起提交;成功重放后 runner 删掉它并覆盖当日日志)。
    路径按协议清单的 dir 或旧目录名(= 账本标签,2026-10-06 之前五本账在仓库根目录)映射到标签。非 git 仓库 → 空表。"""
    if not _is_repo_root(root):
        return pd.DataFrame(columns=FAIL_COLS)
    rows: list[dict[str, Any]] = []
    for sha in (_git(root, "log", "--diff-filter=A", "--format=%H", "--", "*FAILED.json") or "").split():
        names = _git(root, "show", "--name-only", "--format=", "--diff-filter=A", sha) or ""
        for p in names.split():
            if not p.endswith("FAILED.json"):
                continue
            parent = Path(p).parent.as_posix()
            label = next((k for k, dd in book_dirs.items() if parent in (str(dd).rstrip("/"), k)), None)
            if label is None:
                continue
            try:
                j = json.loads(_git(root, "show", f"{sha}:{p}") or "")
            except json.JSONDecodeError:
                j = {}
            d = pd.Timestamp(str(j.get("date") or "1900-01-01"))
            if pd.isna(d) or d < start or d > end:
                continue
            rows.append(
                {
                    "book": label,
                    "date": d,
                    "stage": j.get("stage", "?"),
                    "error": str(j.get("error", ""))[:200],
                    "source": f"git {sha[:7]}",
                }
            )
    return pd.DataFrame(rows, columns=FAIL_COLS)


def merge_failures(book: Book, current: pd.DataFrame, historical: pd.DataFrame) -> pd.DataFrame:
    """工作区的失败记录(未修复)与 git 历史里的(当日现已有权益行且无 FAILED.json → 已修复)合并,同一账本同一日只留一条,未修复优先。"""
    cur = current.copy()
    cur["status"] = "未修复"
    hist = historical.copy()
    have = pd.DatetimeIndex(book.equity.index) if len(book.equity) else pd.DatetimeIndex([])
    failed_date = pd.Timestamp(str(book.failed.get("date"))) if book.failed else None
    hist["status"] = (
        [
            "已修复(重放补齐)" if (d in have and d != failed_date) else "未修复"
            for d in pd.DatetimeIndex(hist["date"])
        ]
        if len(hist)
        else []
    )
    parts = [x for x in (cur, hist) if len(x)]
    if not parts:
        return pd.DataFrame(columns=[*FAIL_COLS, "status"])
    both = pd.concat(parts, ignore_index=True)
    both["_k"] = (both["status"] != "未修复").astype(int)
    both = both.sort_values(["book", "date", "_k"]).drop_duplicates(["book", "date"]).drop(columns="_k")
    return both.reset_index(drop=True)


# ---------- 持仓对账(18.2 第 4 项) ----------
def _is_date(s: str) -> bool:
    try:
        return not pd.isna(pd.Timestamp(s))
    except (ValueError, TypeError):
        return False


def _log_positions(j: dict[str, Any]) -> dict[str, tuple[str, float]] | None:
    """日志里的持仓 {symbol: [contract, lots]} → {symbol: (contract, lots)};旧格式无该字段 → None。"""
    p = j.get("positions")
    if not isinstance(p, dict):
        return None
    out: dict[str, tuple[str, float]] = {}
    for s, v in p.items():
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            out[str(s)] = (str(v[0]), float(v[1]))
    return out


def _fmt_pos(p: tuple[str, float] | None) -> str:
    return f"{p[0]}/{p[1]:g}" if p else "无"


def _pos_diff(expected: dict[str, tuple[str, float]], actual: dict[str, tuple[str, float]]) -> list[str]:
    out = []
    for s in sorted(set(expected) | set(actual)):
        e, a = expected.get(s), actual.get(s)
        if e is None or a is None or e[0] != a[0] or abs(e[1] - a[1]) > 1e-9:
            out.append(f"{s}: 期望 {_fmt_pos(e)} 实际 {_fmt_pos(a)}")
    return out


def _read_orders(book: Book, day: str) -> pd.DataFrame | None:
    p = book.root / "orders" / day / "orders.csv"
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return None


POS_COLS = ["book", "date", "n_positions", "fills_ok", "target_ok", "detail", "ok"]


def reconcile_positions(book: Book, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """逐日:前一日日志持仓 + 当日成交腿(filled)= 当日日志持仓;当日持仓 = 前一日订单的 target(该品种各腿都成交)或 held(有腿未成交)。
    日志在每日步成功后写,失败日被重放后同样有;没有前一日日志的日子无法核对,不计入。"""
    days = sorted(k for k in book.logs if _is_date(k))
    rows: list[dict[str, Any]] = []
    f = book.fills
    has_fills = not f.empty and "date" in f.columns
    for i, day in enumerate(days):
        d = pd.Timestamp(day)
        if d < start or d > end or i == 0:
            continue
        cur = _log_positions(book.logs[day])
        prev = _log_positions(book.logs[days[i - 1]])
        if cur is None or prev is None:
            continue
        legs = (
            f[f["date"] == d] if has_fills else pd.DataFrame(columns=["symbol", "contract", "lots", "status"])
        )
        acc: dict[tuple[str, str], float] = {(s, c): lots for s, (c, lots) in prev.items()}
        for _, r in legs[legs["status"] == "filled"].iterrows():
            key = (str(r["symbol"]), str(r["contract"]))
            acc[key] = acc.get(key, 0.0) + float(r["lots"])
        exp_fills: dict[str, tuple[str, float]] = {}
        dup: list[str] = []
        for (s, c), lots in acc.items():
            if abs(lots) <= 1e-9:
                continue
            if s in exp_fills:
                dup.append(f"{s}: 两个合约同时有仓 {exp_fills[s][0]}/{c}")
            exp_fills[s] = (c, lots)
        detail = dup + _pos_diff(exp_fills, cur)
        fills_ok = not detail
        target_ok: bool | None = None
        od = _read_orders(book, days[i - 1])
        need = {"symbol", "target_contract", "target_lots", "held_contract", "held_lots"}
        if od is not None and need <= set(od.columns):
            exp_t: dict[str, tuple[str, float]] = {}
            for _, o in od.iterrows():
                s = str(o["symbol"])
                sl = legs[legs["symbol"] == s] if len(legs) else legs
                all_filled = bool((sl["status"] == "filled").all()) if len(sl) else True
                c, lots = (
                    (o["target_contract"], o["target_lots"])
                    if all_filled
                    else (o["held_contract"], o["held_lots"])
                )
                lots_f = float(lots) if pd.notna(lots) else 0.0
                if abs(lots_f) > 1e-9 and isinstance(c, str) and c:
                    exp_t[s] = (c, lots_f)
            tdiff = _pos_diff(exp_t, cur)
            target_ok = not tdiff
            detail += [f"目标 {x}" for x in tdiff]
        else:
            detail.append("无前一日订单文件,目标未核")
        rows.append(
            {
                "book": book.name,
                "date": d,
                "n_positions": len(cur),
                "fills_ok": fills_ok,
                "target_ok": target_ok,
                "detail": "; ".join(detail),
                "ok": bool(fills_ok and target_ok is not False),
            }
        )
    return pd.DataFrame(rows, columns=POS_COLS)


def weekly_positions(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["book", "week", "n_days", "n_bad", "ok"])
    d = daily.copy()
    d["week"] = pd.DatetimeIndex(d["date"]).strftime("%G-W%V")
    g = d.groupby(["book", "week"])
    return pd.DataFrame(
        {"n_days": g.size(), "n_bad": g["ok"].apply(lambda s: int((~s).sum())), "ok": g["ok"].all()}
    ).reset_index()


def state_consistency(book: Book) -> dict[str, Any]:
    """最新一日:state.json 持仓 = 当日日志持仓 = positions.csv(三者都只存最新一天)。"""
    sp = book.state.get("positions") or {}
    s_pos = {
        str(k): (str(v.get("contract")), float(v.get("lots", 0.0)))
        for k, v in sp.items()
        if isinstance(v, dict) and abs(float(v.get("lots", 0.0))) > 1e-9
    }
    last = str(book.state.get("last_settled") or "")
    log_pos = _log_positions(book.logs.get(last, {})) if last else None
    csv_pos: dict[str, tuple[str, float]] | None = None
    p = book.root / "positions.csv"
    if p.exists():
        try:
            df = pd.read_csv(p)
            csv_pos = {
                str(sym): (str(c), float(lots))
                for sym, c, lots in zip(df["symbol"], df["contract"], df["lots"], strict=True)
            }
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError, KeyError, ValueError):
            csv_pos = None
    d_log = _pos_diff(s_pos, log_pos) if log_pos is not None else ["无当日日志持仓"]
    d_csv = _pos_diff(s_pos, csv_pos) if csv_pos is not None else []
    return {
        "book": book.name,
        "date": last,
        "n_positions": len(s_pos),
        "state_vs_log": not d_log,
        "state_vs_csv": (not d_csv) if csv_pos is not None else None,
        "detail": "; ".join(d_log + [f"positions.csv {x}" for x in d_csv]),
        "ok": not d_log and not d_csv,
    }


# ---------- 滑点校准(18.2 第 3 项,只报告) ----------
SLIP_LEG_COLS = [
    "book", "date", "symbol", "contract", "leg", "lots", "side", "price", "open", "vwap", "tick",
    "open_vs_vwap_ticks", "open_vs_vwap_bp", "fill_vs_open_ticks", "fill_vs_vwap_ticks",
]  # fmt: skip
SLIP_SUM_COLS = [
    "book", "symbol", "n", "n_missing", "open_vwap_ticks_mean", "open_vwap_ticks_median",
    "open_vwap_ticks_p10", "open_vwap_ticks_p90", "open_vwap_bp_mean_abs", "fill_open_ticks_mean",
    "fill_vwap_ticks_mean",
]  # fmt: skip


def _quotes_day(
    quotes_root: Path,
    exchange: str,
    d: pd.Timestamp,
    cache: dict[tuple[str, pd.Timestamp], pd.DataFrame | None],
) -> pd.DataFrame | None:
    key = (exchange, d)
    if key not in cache:
        p = quotes_root / exchange / "quotes" / f"{d.year}" / f"{d.strftime('%Y%m%d')}.parquet"
        df: pd.DataFrame | None = None
        if p.exists():
            try:
                q = pd.read_parquet(p)
                df = q.set_index("contract") if "contract" in q.columns else None
            except (OSError, ValueError, KeyError):
                df = None
        cache[key] = df
    return cache[key]


def slippage_calibration(
    book: Book, start: pd.Timestamp, end: pd.Timestamp, quotes_root: Path, specs: InstrumentTable
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """每条成交腿:交易所开盘价 vs 当日成交均价 VWAP = turnover × 单位 / (volume × 乘数),以跳数计(open_vs_vwap_ticks);
    成交价 − 开盘价(账本假设 ±1 跳);side × (成交价 − VWAP),正 = 比当日均价差。交易所不公布首 bar 均价,全日均价是 18.2 写定的口径。
    返回 (逐腿, 按账本×品种汇总);行情文件缺失的腿记 NaN 并计入 n_missing。"""
    f = book.fills
    if f.empty or "date" not in f.columns:
        return pd.DataFrame(columns=SLIP_LEG_COLS), pd.DataFrame(columns=SLIP_SUM_COLS)
    w = f[(f["date"] >= start) & (f["date"] <= end) & (f["status"] == "filled")]
    cache: dict[tuple[str, pd.Timestamp], pd.DataFrame | None] = {}
    rows: list[dict[str, Any]] = []
    for _, r in w.iterrows():
        sym = str(r["symbol"])
        if sym not in specs.specs:
            continue
        sp = specs[sym]
        d = pd.Timestamp(r["date"])
        q = _quotes_day(quotes_root, sp.exchange, d, cache)
        open_ = vwap = float("nan")
        contract = str(r["contract"])
        if q is not None and contract in q.index:
            row = q.loc[contract]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            open_ = float(row.get("open", np.nan))
            vol, to = float(row.get("volume", np.nan)), float(row.get("turnover", np.nan))
            if np.isfinite(vol) and vol > 0 and np.isfinite(to):
                vwap = to * TURNOVER_UNIT.get(sp.exchange, 1.0) / (vol * sp.multiplier)
        lots = float(r["lots"])
        side = 1.0 if lots > 0 else -1.0
        price = float(r["price"]) if "price" in r.index and pd.notna(r["price"]) else float("nan")
        rows.append(
            {
                "book": book.name,
                "date": d,
                "symbol": sym,
                "contract": contract,
                "leg": str(r.get("leg", "")),
                "lots": lots,
                "side": side,
                "price": price,
                "open": open_,
                "vwap": vwap,
                "tick": sp.tick,
                "open_vs_vwap_ticks": (open_ - vwap) / sp.tick,
                "open_vs_vwap_bp": (open_ - vwap) / vwap * 1e4,
                "fill_vs_open_ticks": (price - open_) / sp.tick,
                "fill_vs_vwap_ticks": side * (price - vwap) / sp.tick,
            }
        )
    legs = pd.DataFrame(rows, columns=SLIP_LEG_COLS)
    if legs.empty:
        return legs, pd.DataFrame(columns=SLIP_SUM_COLS)
    g = legs.groupby(["book", "symbol"])
    summ = pd.DataFrame(
        {
            "n": g.size(),
            "n_missing": g["vwap"].apply(lambda s: int(s.isna().sum())),
            "open_vwap_ticks_mean": g["open_vs_vwap_ticks"].mean(),
            "open_vwap_ticks_median": g["open_vs_vwap_ticks"].median(),
            "open_vwap_ticks_p10": g["open_vs_vwap_ticks"].quantile(0.1),
            "open_vwap_ticks_p90": g["open_vs_vwap_ticks"].quantile(0.9),
            "open_vwap_bp_mean_abs": g["open_vs_vwap_bp"].apply(lambda s: float(s.abs().mean())),
            "fill_open_ticks_mean": g["fill_vs_open_ticks"].mean(),
            "fill_vwap_ticks_mean": g["fill_vs_vwap_ticks"].mean(),
        }
    ).reset_index()
    return legs, summ[SLIP_SUM_COLS]


def slippage_by_book(legs: pd.DataFrame) -> pd.DataFrame:
    """逐腿表按账本汇总(报告正文用;按品种的明细在 CSV)。"""
    if legs.empty:
        return pd.DataFrame(columns=SLIP_SUM_COLS).drop(columns="symbol")
    g = legs.groupby("book")
    return pd.DataFrame(
        {
            "n": g.size(),
            "n_missing": g["vwap"].apply(lambda s: int(s.isna().sum())),
            "open_vwap_ticks_mean": g["open_vs_vwap_ticks"].mean(),
            "open_vwap_ticks_median": g["open_vs_vwap_ticks"].median(),
            "open_vwap_ticks_p10": g["open_vs_vwap_ticks"].quantile(0.1),
            "open_vwap_ticks_p90": g["open_vs_vwap_ticks"].quantile(0.9),
            "open_vwap_bp_mean_abs": g["open_vs_vwap_bp"].apply(lambda s: float(s.abs().mean())),
            "fill_open_ticks_mean": g["fill_vs_open_ticks"].mean(),
            "fill_vwap_ticks_mean": g["fill_vs_vwap_ticks"].mean(),
        }
    ).reset_index()


DRILL_REQUIRED = ("date", "book", "injected", "detected", "recovered", "outcome")


def drill_evidence(evidence_dir: Path) -> tuple[str, list[dict[str, Any]]]:
    """故障恢复演练证据:evidence_dir/*.json,每个必须含 date/book/injected/detected/recovered/outcome;没有合格证据 → PENDING。"""
    items: list[dict[str, Any]] = []
    p = Path(evidence_dir)
    if p.exists():
        for f in sorted(p.glob("*.json")):
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                items.append({"file": f.name, "valid": False, "reason": "JSON 解析失败"})
                continue
            missing = [k for k in DRILL_REQUIRED if k not in j]
            items.append(
                {
                    "file": f.name,
                    "valid": not missing,
                    "reason": f"缺字段 {missing}" if missing else "",
                    **{k: j.get(k) for k in DRILL_REQUIRED},
                }
            )
    status = "DONE" if any(i.get("valid") for i in items) else "PENDING"
    return status, items


# ---------- 汇总 ----------
def _stop_condition(
    champion: pd.Series[Any], challenger: pd.Series[Any], lags: int, seed: int, start: pd.Timestamp
) -> dict[str, Any]:
    """预注册停账条件:配对差 t < −3 且 challenger 回撤差 < −10pp,连续两个月末成立。触及 ≠ champion 更优。"""
    pdf = paired_differences(champion, challenger, start)
    if pdf.empty:
        return {"evaluable": False, "months_evaluated": 0, "triggered": False, "detail": "无共同日期"}
    dates = pd.Series(pd.DatetimeIndex(pdf.index), index=pdf.index)
    month_ends = dates.groupby(pd.DatetimeIndex(pdf.index).to_period("M")).max()
    flags = []
    for me in month_ends:
        me_ts = pd.Timestamp(me)
        ca = champion[pd.DatetimeIndex(champion.index) <= me_ts]
        cb = challenger[pd.DatetimeIndex(challenger.index) <= me_ts]
        s = paired_summary(ca, cb, lags=lags, n_boot=200, seed=seed, start=start)
        flags.append(bool(np.isfinite(s["t"]) and s["t"] < -3 and s["dd_diff"] < -0.10))
    if len(flags) < 2:
        return {
            "evaluable": False,
            "months_evaluated": len(flags),
            "triggered": False,
            "detail": "不足两个月末,无法评估",
        }
    return {
        "evaluable": True,
        "months_evaluated": len(flags),
        "triggered": bool(flags[-1] and flags[-2]),
        "detail": ",".join("触" if f else "否" for f in flags),
    }


def run_acceptance(
    root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    out_dir: Path,
    report_path: Path,
    protocol_path: Path,
    strict: bool = False,
    asof: pd.Timestamp | None = None,
    lags: int = 5,
    block: int = 10,
    n_boot: int = 2000,
    seed: int = 20260923,
    drills_dir: Path | None = None,
    holidays: pd.DatetimeIndex | None = None,
    specs: InstrumentTable | None = None,
    quotes_root: Path | None = None,
) -> AcceptanceResult:
    root, out_dir, report_path = Path(root), Path(out_dir), Path(report_path)
    protocol = load_protocol(protocol_path)
    champ_name = str(protocol["champion"])
    book_dirs = {str(k): str(v.get("dir", k)) for k, v in (protocol.get("books") or {}).items()}
    specs = specs if specs is not None else load_instruments()
    quotes_root = quotes_root if quotes_root is not None else root / "data" / "exchanges"
    code_paths = book_code_paths(protocol)

    def _load(name: str, role: str) -> Book:
        d = root / book_dirs.get(name, name)
        if not (d / "state.json").exists():  # 目录写错时不能静默当成空账本(完整率 0、对账空真)
            raise FileNotFoundError(f"book {name!r}: no state.json under {d}")
        return load_book(d, name, role)

    books = [_load(champ_name, "champion")] + [
        _load(str(n), "challenger") for n in protocol.get("challengers", [])
    ]
    last = max((pd.Timestamp(b.equity.index.max()) for b in books if len(b.equity)), default=start)
    asof_ts = asof if asof is not None else min(end, last)
    status = "PRELIMINARY" if asof_ts < end else "FINAL"
    days = expected_days(start, asof_ts, holidays)
    comp = pd.DataFrame([completeness(b, days) for b in books])
    hist_fail = historical_failures(root, book_dirs, start, asof_ts)
    fill_rows, blocked_parts, rec_parts, fail_parts, drift_parts = [], [], [], [], []
    pos_parts, state_rows, slip_leg_parts, slip_parts = [], [], [], []
    for b in books:
        fs, bl = fill_stats(b, start, asof_ts)
        fill_rows.append(fs)
        if len(bl):
            blocked_parts.append(bl)
        rec_parts.append(reconcile_book(b, start, asof_ts))
        pos_parts.append(reconcile_positions(b, start, asof_ts))
        state_rows.append(state_consistency(b))
        fail_parts.append(
            merge_failures(b, failures(b, start, asof_ts), hist_fail[hist_fail["book"] == b.name])
        )
        drift_parts.append(drift(b, start, asof_ts, protocol, root=root, paths=code_paths))
        legs, summ = slippage_calibration(b, start, asof_ts, quotes_root, specs)
        slip_leg_parts.append(legs)
        slip_parts.append(summ)
    fills_df = pd.DataFrame(fill_rows)
    blocked_df = (
        pd.concat(blocked_parts, ignore_index=True)
        if blocked_parts
        else pd.DataFrame(columns=["book", "date", "symbol", "contract", "lots", "status", "reason"])
    )
    rec_df = pd.concat(rec_parts, ignore_index=True) if rec_parts else pd.DataFrame()
    weekly = weekly_reconciliation(rec_df)
    pos_df = pd.concat(pos_parts, ignore_index=True)
    pos_weekly = weekly_positions(pos_df)
    state_df = pd.DataFrame(state_rows)
    fail_df = pd.concat(fail_parts, ignore_index=True)
    drift_df = pd.concat(drift_parts, ignore_index=True)
    slip_legs = pd.concat(slip_leg_parts, ignore_index=True)
    slip_df = pd.concat(slip_parts, ignore_index=True)
    slip_book = slippage_by_book(slip_legs)
    cr = common_range(books)
    drills_status, drills = drill_evidence(drills_dir if drills_dir is not None else root / "docs" / "drills")
    champ = books[0]
    paired_rows = []
    stop_rows = []
    for b in books[1:]:
        if len(champ.equity) and len(b.equity):
            ce = champ.equity["equity"].loc[
                (champ.equity.index >= start - pd.Timedelta(days=10)) & (champ.equity.index <= asof_ts)
            ]
            be = b.equity["equity"].loc[
                (b.equity.index >= start - pd.Timedelta(days=10)) & (b.equity.index <= asof_ts)
            ]
            # 起算点:第一条配对差用 start 当日相对其前一交易日的收益,所以取 start 之前一条权益作基
            s = paired_summary(ce, be, lags=lags, block=block, n_boot=n_boot, seed=seed, start=start)
            s["challenger"] = b.name
            paired_rows.append(s)
            sc = _stop_condition(ce, be, lags, seed, start)
            sc["challenger"] = b.name
            stop_rows.append(sc)
    paired_df = pd.DataFrame(paired_rows)
    stop_df = pd.DataFrame(stop_rows)
    # ---- 输出 ----
    out_dir.mkdir(parents=True, exist_ok=True)
    comp.to_csv(out_dir / "completeness.csv", index=False)
    fills_df.to_csv(out_dir / "fills.csv", index=False)
    blocked_df.to_csv(out_dir / "blocked.csv", index=False)
    rec_df.to_csv(out_dir / "reconciliation.csv", index=False)
    weekly.to_csv(out_dir / "reconciliation_weekly.csv", index=False)
    pos_df.to_csv(out_dir / "positions_reconciliation.csv", index=False)
    pos_weekly.to_csv(out_dir / "positions_reconciliation_weekly.csv", index=False)
    state_df.to_csv(out_dir / "state_consistency.csv", index=False)
    fail_df.to_csv(out_dir / "failures.csv", index=False)
    drift_df.to_csv(out_dir / "config_drift.csv", index=False)
    slip_legs.to_csv(out_dir / "slippage_legs.csv", index=False)
    slip_df.to_csv(out_dir / "slippage_by_symbol.csv", index=False)
    slip_book.to_csv(out_dir / "slippage_by_book.csv", index=False)
    paired_df.to_csv(out_dir / "paired_differences.csv", index=False)
    stop_df.to_csv(out_dir / "stop_condition.csv", index=False)
    rec_ok = bool(rec_df["ok"].all()) if len(rec_df) else True
    # 持仓:有预期交易日却一天都核不了(没有带持仓的日志)不算通过;最新一日 state/positions.csv 也要一致
    pos_ok = bool(
        (len(pos_df) > 0 and pos_df["ok"].all() and state_df["ok"].all())
        if len(days)
        else state_df["ok"].all()
    )
    comp_ok = bool((comp["rate"].fillna(1.0) >= 1.0).all()) if len(comp) else False  # 尚无预期交易日 → 无缺失
    undeclared = int((~drift_df["declared"]).sum()) if len(drift_df) else 0

    def _fail_cell(b: str) -> str:
        fb = fail_df[fail_df["book"] == b]
        n, k = len(fb), int((fb["status"] != "未修复").sum()) if len(fb) else 0
        return f"{n}(已修复 {k})" if n else "0"

    summary = pd.DataFrame(
        {
            "book": comp["book"],
            "role": comp["role"],
            "present/expected": comp["present"].astype(str) + "/" + comp["expected"].astype(str),
            "fill_rate": fills_df["fill_rate"].round(4) if len(fills_df) else np.nan,
            "reconciled": [
                bool(rec_df[rec_df["book"] == b]["ok"].all()) if len(rec_df) else True for b in comp["book"]
            ],
            "positions_reconciled": [
                bool(len(pos_df[pos_df["book"] == b]) and pos_df[pos_df["book"] == b]["ok"].all())
                and bool(state_df[state_df["book"] == b]["ok"].all())
                for b in comp["book"]
            ],
            "failures": [_fail_cell(b) for b in comp["book"]],
            "undeclared_drift": [
                int(((drift_df["book"] == b) & (~drift_df["declared"])).sum()) if len(drift_df) else 0
                for b in comp["book"]
            ],
        }
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _render_report(
            status,
            start,
            end,
            asof_ts,
            days,
            comp,
            fills_df,
            blocked_df,
            rec_df,
            weekly,
            pos_df,
            pos_weekly,
            state_df,
            fail_df,
            drift_df,
            slip_book,
            slip_df,
            cr,
            drills_status,
            drills,
            paired_df,
            stop_df,
            protocol,
            protocol_path,
            lags,
            block,
            n_boot,
            seed,
            out_dir,
        ),
        encoding="utf-8",
    )
    return AcceptanceResult(
        status, asof_ts, rec_ok, pos_ok, comp_ok, undeclared, drills_status, report_path, summary
    )


def _rate(x: Any) -> str:
    return f"{float(x):.1%}" if x is not None and np.isfinite(float(x)) else "n/a"


def _fmt_pct(x: Any) -> str:
    return f"{float(x):+.2%}" if x is not None and np.isfinite(float(x)) else "n/a"


def _render_report(
    status: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    asof: pd.Timestamp,
    days: pd.DatetimeIndex,
    comp: pd.DataFrame,
    fills_df: pd.DataFrame,
    blocked_df: pd.DataFrame,
    rec_df: pd.DataFrame,
    weekly: pd.DataFrame,
    pos_df: pd.DataFrame,
    pos_weekly: pd.DataFrame,
    state_df: pd.DataFrame,
    fail_df: pd.DataFrame,
    drift_df: pd.DataFrame,
    slip_book: pd.DataFrame,
    slip_df: pd.DataFrame,
    cr: dict[str, Any],
    drills_status: str,
    drills: list[dict[str, Any]],
    paired_df: pd.DataFrame,
    stop_df: pd.DataFrame,
    protocol: dict[str, Any],
    protocol_path: Path,
    lags: int,
    block: int,
    n_boot: int,
    seed: int,
    out_dir: Path,
) -> str:
    lines: list[str] = []
    banner = (
        f"**PRELIMINARY —— 验收期 {start.date()} → {end.date()} 尚未结束,本报告截至 {asof.date()},只是阶段性结果。**"
        if status == "PRELIMINARY"
        else f"FINAL —— 验收期 {start.date()} → {end.date()} 已结束。"
    )
    lines += [
        f"# 纸面交易验收报告({status},截至 {asof.date()})",
        "",
        banner,
        "",
        f"预注册规则:`docs/design_log.md` 十八;协议清单:`{protocol_path}`;champion = `{protocol['champion']}`,challenger = {', '.join('`' + str(c) + '`' for c in protocol.get('challengers', []))}。**不选赢家,不采用、不淘汰任何版本。**",
        "",
    ]
    lines += [
        "## 0. 摘要",
        "",
        "| 账本 | 角色 | 有数据/预期交易日 | 成交率 | 权益对账 | 持仓对账 | 失败记录(已修复) | 未声明漂移 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, c in comp.iterrows():
        fr = fills_df[fills_df["book"] == c["book"]]["fill_rate"]
        rec_ok = bool(rec_df[rec_df["book"] == c["book"]]["ok"].all()) if len(rec_df) else True
        pb = pos_df[pos_df["book"] == c["book"]]
        sb = state_df[state_df["book"] == c["book"]]
        pos_ok = bool(len(pb) and pb["ok"].all() and sb["ok"].all())
        pos_cell = ("一致" if pos_ok else "**不一致**") if len(pb) else "**无法核对**"
        fb = fail_df[fail_df["book"] == c["book"]]
        nf, nk = len(fb), int((fb["status"] != "未修复").sum()) if len(fb) else 0
        nd = int(((drift_df["book"] == c["book"]) & (~drift_df["declared"])).sum()) if len(drift_df) else 0
        lines.append(
            f"| {c['book']} | {c['role']} | {c['present']}/{c['expected']} | {_rate(fr.iloc[0]) if len(fr) else 'n/a'} | {'一致' if rec_ok else '**不一致**'} | {pos_cell} | {nf}({nk}) | {nd} |"
        )
    if len(days) == 0:
        lines += [
            "",
            f"> 验收期从 {start.date()} 起算,账本最新日期为 {asof.date()}:**验收期尚未产生任何数据**,下面各节为空是正常的;"
            "09-16 → 09-22 的记录期数据不计入验收(设计日志 18.2 第 6 条)。",
        ]
    lines += [
        "",
        f"预期交易日 = 周一至周五且不在 `configs/holidays.csv`,{start.date()} → {asof.date()} 共 {len(days)} 天。五本账共同有效日期:{cr['start']} → {cr['end']}({cr['n_common_days']} 天)。",
        "",
    ]
    lines += ["## 1. 数据完整率", "", "| 账本 | 预期 | 有数据 | 完整率 | 缺失日期 |", "|---|---|---|---|---|"]
    for _, c in comp.iterrows():
        lines.append(
            f"| {c['book']} | {c['expected']} | {c['present']} | {float(c['rate']):.1%} | {c['missing'] or '—'} |"
        )
    lines += [
        "",
        "预注册阈值:验收期内每个交易日五本账都有权益行(FAILED 日在后续运行中修复重放算完整;最终仍缺失 → 不通过)。",
        "",
    ]
    lines += [
        "## 2. 成交率(按腿)",
        "",
        "| 账本 | filled | blocked | filled/(filled+blocked) |",
        "|---|---|---|---|",
    ]
    for _, f in fills_df.iterrows():
        lines.append(f"| {f['book']} | {f['filled']} | {f['blocked']} | {_rate(f['fill_rate'])} |")
    lines += ["", "阈值 ≥ 95%。blocked 逐条:", ""]
    if len(blocked_df):
        lines += ["| 账本 | 日期 | 品种 | 合约 | 手数 | 状态 | 原因 |", "|---|---|---|---|---|---|---|"]
        for _, r in blocked_df.iterrows():
            lines.append(
                f"| {r['book']} | {pd.Timestamp(r['date']).date()} | {r.get('symbol', '')} | {r.get('contract', '')} | {r.get('lots', '')} | {r['status']} | {r.get('reason', '')} |"
            )
    else:
        lines.append("(无)")
    lines += ["", "## 3. 权益对账(账本语义:Δ权益 = Δ已实现 + 当日盯市 − Δ手续费;滑点已在成交价内,不再扣)", ""]
    if len(rec_df):
        bad = rec_df[~rec_df["ok"]]
        lines += [
            f"逐日检查 {len(rec_df)} 条,不一致 {len(bad)} 条;容差 1e-4 元(浮点)。另用当日 fills 交叉核对手续费(旧格式 fills 无 realized_pnl 列,只核手续费)。",
            "",
        ]
        lines += ["| 账本 | 周 | 天数 | 最大|差| | 通过 |", "|---|---|---|---|---|"]
        for _, w in weekly.iterrows():
            lines.append(
                f"| {w['book']} | {w['week']} | {w['n_days']} | {float(w['max_abs_diff']):.6f} | {'是' if w['ok'] else '**否**'} |"
            )
        if len(bad):
            lines += [
                "",
                "**不一致明细**:",
                "",
                "| 账本 | 日期 | Δ权益 | 期望 | 差额 | fills 手续费差 |",
                "|---|---|---|---|---|---|",
            ]
            for _, r in bad.iterrows():
                lines.append(
                    f"| {r['book']} | {pd.Timestamp(r['date']).date()} | {float(r['d_equity']):,.2f} | {float(r['expected']):,.2f} | {float(r['diff']):,.6f} | {r['fills_fee_diff']} |"
                )
    else:
        lines.append("(验收期内无权益行)")
    lines += [
        "",
        "## 4. 持仓对账(18.2 第 4 项:前一日持仓 + 当日成交腿 = 当日持仓 = 前一日订单目标;有腿未成交的品种保持前一日持仓)",
        "",
    ]
    if len(pos_df):
        bad_p = pos_df[~pos_df["ok"]]
        lines += [
            f"逐日检查 {len(pos_df)} 条(账本日志 `log/<日>.json` 的持仓、`fills/<日>.csv`、`orders/<前一日>/orders.csv`),不一致 {len(bad_p)} 条。",
            "",
            "| 账本 | 周 | 天数 | 不一致 | 通过 |",
            "|---|---|---|---|---|",
        ]
        for _, w in pos_weekly.iterrows():
            lines.append(
                f"| {w['book']} | {w['week']} | {w['n_days']} | {w['n_bad']} | {'是' if w['ok'] else '**否**'} |"
            )
        if len(bad_p):
            lines += [
                "",
                "**不一致明细**:",
                "",
                "| 账本 | 日期 | 成交累计 | 订单目标 | 说明 |",
                "|---|---|---|---|---|",
            ]
            for _, r in bad_p.iterrows():
                t = r["target_ok"]
                t_cell = "未核" if t is None or pd.isna(t) else ("是" if bool(t) else "否")
                lines.append(
                    f"| {r['book']} | {pd.Timestamp(r['date']).date()} | {'是' if r['fills_ok'] else '否'} | {t_cell} | {str(r['detail']).replace('|', '/')} |"
                )
    else:
        lines.append("(验收期内没有带持仓的日志,无法核对)")
    lines += ["", "最新一日 `state.json` 持仓 = 当日日志持仓 = `positions.csv`:", ""]
    lines += ["| 账本 | 日期 | 持仓品种数 | 对日志 | 对 positions.csv | 说明 |", "|---|---|---|---|---|---|"]
    for _, r in state_df.iterrows():
        sc = r["state_vs_csv"]
        csv_cell = "无文件" if sc is None or pd.isna(sc) else ("一致" if bool(sc) else "**不一致**")
        lines.append(
            f"| {r['book']} | {r['date']} | {r['n_positions']} | {'一致' if r['state_vs_log'] else '**不一致**'} | {csv_cell} | {str(r['detail']).replace('|', '/')} |"
        )
    lines += [
        "",
        "## 5. 失败记录(工作区 FAILED.json、日志,以及 git 历史里已被成功重放清除的 FAILED.json)",
        "",
    ]
    if len(fail_df):
        lines += ["| 账本 | 日期 | 阶段 | 错误 | 来源 | 状态 |", "|---|---|---|---|---|---|"]
        for _, r in fail_df.iterrows():
            lines.append(
                f"| {r['book']} | {pd.Timestamp(r['date']).date()} | {r['stage']} | {str(r['error']).replace('|', '/')} | {r['source']} | {r['status']} |"
            )
        lines += [
            "",
            "已修复 = 该日现已有权益行且无 FAILED.json(18.2 第 1 项:FAILED 日在后续运行中修复重放算完整);未修复的失败日同时出现在第 1 节的缺失日期里。",
        ]
    else:
        lines.append("(无)")
    lines += [
        "",
        "## 6. 配置 / 参数表 / 代码 / 数据漂移(基于订单快照 config_digest、instruments_digest、git_sha、data_manifest)",
        "",
    ]
    if len(drift_df):
        lines += [
            "| 账本 | 日期 | 字段 | 旧 | 新 | 分类 | 已声明 | 说明 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, r in drift_df.iterrows():
            lines.append(
                f"| {r['book']} | {pd.Timestamp(r['date']).date()} | {r['field']} | {str(r['old'])[:16]} | {str(r['new'])[:16]} | {r['category']} | {'是' if r['declared'] else '**否**'} | {r['note']} |"
            )
    else:
        lines.append("(验收期内无快照变化)")
    lines += [
        "",
        "默认只检测和报告,不阻止每日作业。协议清单声明的切换视为合法;未声明的策略配置/参数表/代码/数据版本变化需要解释。"
        "git_sha 每个纸面提交都会变:两个版本之间若 `src/cta`、每日脚本、依赖、五本账配置、参数表、假期表都没改,记为'仅非账本路径的提交',算已声明;改了则须在清单里声明(同日或 from → to),否则列出改动文件。",
        "",
    ]
    lines += [
        "## 7. 故障恢复演练证据",
        "",
        f"状态:**{drills_status}**(证据目录 `docs/drills/*.json`,必需字段 {', '.join(DRILL_REQUIRED)};没有合格证据即 PENDING,不凭空判定通过)。",
        "",
    ]
    for it in drills:
        lines.append(
            f"- `{it['file']}`:{'合格' if it.get('valid') else '不合格 ' + str(it.get('reason', ''))}"
            + (
                f" —— {it.get('date')} {it.get('book')} 注入 {it.get('injected')} / 检出 {it.get('detected')} / 恢复 {it.get('recovered')} / 结果 {it.get('outcome')}"
                if it.get("valid")
                else ""
            )
        )
    lines += [
        "",
        "## 8. 滑点校准(18.2 第 3 项;只报告,不判定)",
        "",
        "每条成交腿:交易所开盘价 − 当日成交均价(成交额 / 成交量 / 乘数;上期所、能源中心成交额单位万元),以跳数计;成交价 − 开盘价是账本假设的 ±1 跳;side × (成交价 − 均价) 正 = 比当日均价差。交易所不公布首 bar 均价,全日均价是预注册写定的口径。按品种的明细在 `slippage_by_symbol.csv`,逐腿在 `slippage_legs.csv`。",
        "",
    ]
    if len(slip_book):
        lines += [
            "| 账本 | 腿数 | 缺行情 | 开盘−均价 跳数:均值 / 中位 / p10 / p90 | 开盘−均价 平均|bp| | 成交−开盘 跳数均值 | side×(成交−均价) 跳数均值 |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, r in slip_book.iterrows():
            lines.append(
                f"| {r['book']} | {int(r['n'])} | {int(r['n_missing'])} | {float(r['open_vwap_ticks_mean']):.2f} / {float(r['open_vwap_ticks_median']):.2f} / {float(r['open_vwap_ticks_p10']):.2f} / {float(r['open_vwap_ticks_p90']):.2f} | {float(r['open_vwap_bp_mean_abs']):.1f} | {float(r['fill_open_ticks_mean']):+.2f} | {float(r['fill_vwap_ticks_mean']):+.2f} |"
            )
        champ_slip = slip_df[slip_df["book"] == str(protocol["champion"])]
        if len(champ_slip):
            lines += [
                "",
                f"champion `{protocol['champion']}` 按品种:",
                "",
                "| 品种 | 腿数 | 缺行情 | 开盘−均价 跳数均值 / 中位 | p10 / p90 | 平均|bp| | side×(成交−均价) 跳数均值 |",
                "|---|---|---|---|---|---|---|",
            ]
            for _, r in champ_slip.iterrows():
                lines.append(
                    f"| {r['symbol']} | {int(r['n'])} | {int(r['n_missing'])} | {float(r['open_vwap_ticks_mean']):.2f} / {float(r['open_vwap_ticks_median']):.2f} | {float(r['open_vwap_ticks_p10']):.2f} / {float(r['open_vwap_ticks_p90']):.2f} | {float(r['open_vwap_bp_mean_abs']):.1f} | {float(r['fill_vwap_ticks_mean']):+.2f} |"
                )
    else:
        lines.append("(验收期内无成交腿)")
    lines += ["", "## 9. champion / challenger 配对差(预注册 18.3;只报告,不选择)", ""]
    if len(paired_df) and int(paired_df["n_days"].max()) > 0:
        insufficient = paired_df[~paired_df["sample_sufficient"]]
        if len(insufficient):
            lines += [
                f"> **样本量不足**:{', '.join(insufficient['challenger'])} 的共同交易日少于 60 天(当前 {int(paired_df['n_days'].max())} 天)。下面的数字只是记录,不能用来比较优劣;标准误按 17.5 的估计要 12 个月才降到 ±0.65。",
                "",
            ]
        lines += [
            "| challenger | 共同日 | 配对差年化均值 | NW SE(年化) | t | bootstrap 95% 区间(年化) | 夏普(日频,champion / challenger) | 最大回撤(champion / challenger) | 回撤差 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for _, r in paired_df.iterrows():
            lines.append(
                f"| {r['challenger']} | {int(r['n_days'])} | {_fmt_pct(r['ann_mean'])} | {_fmt_pct(r['nw_se_ann'])} | {float(r['t']):.2f} | [{_fmt_pct(r['boot_ci_low_ann'])}, {_fmt_pct(r['boot_ci_high_ann'])}] | {float(r['sharpe_champion_daily']):.2f} / {float(r['sharpe_challenger_daily']):.2f} | {_fmt_pct(r['mdd_champion'])} / {_fmt_pct(r['mdd_challenger'])} | {_fmt_pct(r['dd_diff'])} |"
            )
        lines += [
            "",
            f"方法:d_t = challenger 日收益 − champion 日收益,各自以自身前一交易日权益为分母,只用双方共同有效日期;Newey–West lag={lags};移动块 bootstrap 块长 {block} 个交易日、重采样 {n_boot} 次、随机种子 {seed}(可复现);夏普为日频年化({'243'} 个交易日),样本短时无意义。",
            "",
        ]
        lines += [
            "预注册停账条件(唯一允许的动作):配对差 t < −3 且 challenger 回撤差 < −10pp,连续两个月末成立 → 可停账止损。**触及停账条件 ≠ champion 已被统计证明更优;未触及也不说明 challenger 更好。**",
            "",
        ]
        lines += ["| challenger | 可评估 | 已评估月末数 | 是否触及 | 逐月 |", "|---|---|---|---|---|"]
        for _, r in stop_df.iterrows():
            lines.append(
                f"| {r['challenger']} | {'是' if r['evaluable'] else '否'} | {r['months_evaluated']} | {'**触及**' if r['triggered'] else '未触及'} | {r['detail']} |"
            )
    else:
        lines.append("(验收期内尚无配对日期,无法计算)")
    lines += [
        "",
        "## 10. 方法与参数",
        "",
        f"- 输出目录:`{out_dir}`;协议清单:`{protocol_path}`;随机种子 {seed};bootstrap {n_boot} 次、块长 {block};NW lag {lags};权益对账容差 1e-4 元,持仓对账手数容差 1e-9。",
        "- 本报告只读取 paper*/ 目录、git 历史与交易所行情文件,不修改任何账本文件;不新增账本;不据结果采用或淘汰版本。",
        f"- 与回测的比较(18.4)留到验收期结束再做;本阶段共同日期 {cr['n_common_days']} 天。",
        "",
    ]
    return "\n".join(lines)
