"""纸面验收:缺失日期 / blocked / FAILED 统计、权益对账发现注入错误、持仓对账发现注入错误、滑点校准的单位与缺行情、
git 历史里的已修复失败日、按账本运行路径分类的代码漂移、配置摘要漂移、PRELIMINARY 阶段报告、演练证据 PENDING。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from cta.analysis import paper_acceptance as pa
from cta.instruments.specs import load_instruments

DAYS = pd.bdate_range("2026-09-23", periods=4)  # 周三→周一(跨周末)
HOL = pd.DatetimeIndex([])


def _book(
    root: Path,
    name: str,
    days: pd.DatetimeIndex,
    *,
    skip: frozenset[int] = frozenset(),
    snaps: list[str] | None = None,
    git_shas: list[str] | None = None,
    failed_day: int | None = None,
    blocked: bool = False,
) -> Path:
    """合成账本:equity 按账本恒等式生成;fills 带 fee(CU 每日 +1 手);快照带摘要;日志带持仓(CU 累计手数);
    orders 带下一日目标(CU 再 +1 手;blocked 时第 2 天给 AL 一个目标,第 3 天那条 AL 腿被挡);可选一日 FAILED 日志。"""
    b = root / name
    (b / "fills").mkdir(parents=True)
    (b / "orders").mkdir()
    (b / "log").mkdir()
    eq, real, fee, held = 1_000_000.0, 0.0, 0.0, 0.0
    rows = []
    for i, d in enumerate(days):
        if i in skip:
            continue
        day_fee = 6.0 if i > 0 else 0.0
        day_real = 100.0 * i if i > 1 else 0.0
        mtm = {"CU": 250.0 * i, "AL": -40.0 * i} if i > 0 else {}
        real += day_real
        fee += day_fee
        eq += day_real + sum(mtm.values()) - day_fee
        rows.append(
            {
                "date": str(d.date()),
                "equity": eq,
                "realized_pnl": real,
                "fees_paid": fee,
                "slippage_paid": 10.0 * i,
                "margin_used": 1000.0,
                "n_positions": 2,
                "pnl_by_symbol": json.dumps(mtm),
            }
        )
        fills = (
            [
                {
                    "date": str(d.date()),
                    "symbol": "CU",
                    "contract": "CU2610",
                    "lots": 1.0,
                    "status": "filled",
                    "reason": "",
                    "leg": "rebalance",
                    "price": 70000.0,
                    "fee": day_fee,
                    "slippage": 10.0,
                    "realized_pnl": day_real,
                }
            ]
            if i > 0
            else []
        )
        if i > 0:
            held += 1.0
        if blocked and i == 2:
            fills.append(
                {
                    "date": str(d.date()),
                    "symbol": "AL",
                    "contract": "AL2610",
                    "lots": 2.0,
                    "status": "limit_locked",
                    "reason": "limit_locked",
                    "leg": "rebalance",
                }
            )
        if fills:
            pd.DataFrame(fills).to_csv(b / "fills" / f"{d.date()}.csv", index=False)
        snap_digest = (snaps or ["cfg0"] * len(days))[i]
        sha = (git_shas or ["abc1234"] * len(days))[i]
        (b / "orders" / str(d.date())).mkdir()
        (b / "orders" / str(d.date()) / "snapshot.json").write_text(
            json.dumps(
                {
                    "asof": str(d.date()),
                    "config_digest": snap_digest,
                    "instruments_digest": "ins0",
                    "git_sha": sha,
                    "data_manifest": {
                        "primary": "{'sha256': 'p0'}",
                        "secondary": f"{{'coverage': 'SHFE:{i}', 'sha256': 's{i}'}}",
                    },
                }
            ),
            encoding="utf-8",
        )
        al_target = 2.0 if (blocked and i == 1) else 0.0
        pd.DataFrame(
            [
                {
                    "symbol": "CU",
                    "target_contract": "CU2610",
                    "target_lots": held + 1.0,
                    "held_contract": "CU2610" if held else "",
                    "held_lots": held,
                    "roll_required": False,
                    "delta_lots": 1.0,
                },
                {
                    "symbol": "AL",
                    "target_contract": "AL2610",
                    "target_lots": al_target,
                    "held_contract": "",
                    "held_lots": 0.0,
                    "roll_required": False,
                    "delta_lots": al_target,
                },
            ]
        ).to_csv(b / "orders" / str(d.date()) / "orders.csv", index=False)
        log: dict[str, Any] = {"date": str(d.date()), "positions": {"CU": ["CU2610", held]} if held else {}}
        if failed_day == i:
            log["failed"] = {"stage": "settle", "error": "LedgerIntegrityError: x"}
        (b / "log" / f"{d.date()}.json").write_text(json.dumps(log), encoding="utf-8")
    pd.DataFrame(rows).to_csv(b / "equity.csv", index=False)
    (b / "state.json").write_text(
        json.dumps(
            {
                "equity": eq,
                "cash_start": 1_000_000.0,
                "last_settled": str(days[-1].date()),
                "positions": {"CU": {"contract": "CU2610", "lots": held, "ref_price": 70000.0}}
                if held
                else {},
            }
        ),
        encoding="utf-8",
    )
    return b


def _protocol(root: Path, declared: bool = False, extra: str = "") -> Path:
    p = root / "paper_protocol.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    dec = (
        "declared_transitions:\n  - {effective: '2026-09-25', fields: [config_digest], note: 声明的切换}\n"
        + extra
        if declared or extra
        else "declared_transitions: []\n"
    )
    p.write_text(
        "champion: champ\nchallengers: [chal]\nbooks:\n  champ: {expected_config_digest: cfg0}\n  chal: {expected_config_digest: cfg0}\nexpected_instruments_digest: ins0\n"
        + dec,
        encoding="utf-8",
    )
    return p


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@x", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_missing_days_blocked_and_failed_are_counted(tmp_path: Path) -> None:
    b = pa.load_book(
        _book(tmp_path, "champ", DAYS, skip={2}, failed_day=1, blocked=True), "champ", "champion"
    )
    c = pa.completeness(b, pa.expected_days(DAYS[0], DAYS[-1], HOL))
    assert c["expected"] == 4 and c["present"] == 3 and c["missing"] == str(DAYS[2].date())
    fs, bl = pa.fill_stats(b, DAYS[0], DAYS[-1])
    assert fs["filled"] == 2 and fs["blocked"] == 0  # 第 3 天被 skip,blocked 那条随之不存在
    b2 = pa.load_book(_book(tmp_path / "x", "champ", DAYS, blocked=True), "champ", "champion")
    fs2, bl2 = pa.fill_stats(b2, DAYS[0], DAYS[-1])
    assert (
        fs2["filled"] == 3
        and fs2["blocked"] == 1
        and fs2["fill_rate"] == 0.75
        and bl2.iloc[0]["status"] == "limit_locked"
    )
    f = pa.failures(b, DAYS[0], DAYS[-1])
    assert len(f) == 1 and f.iloc[0]["stage"] == "settle"
    m = pa.merge_failures(b, f, pd.DataFrame(columns=pa.FAIL_COLS))
    assert list(m["status"]) == ["未修复"]


def test_expected_days_respect_holidays() -> None:
    d = pa.expected_days(
        pd.Timestamp("2026-09-23"), pd.Timestamp("2026-09-28"), pd.DatetimeIndex([pd.Timestamp("2026-09-25")])
    )
    assert [x.date().isoformat() for x in d] == ["2026-09-23", "2026-09-24", "2026-09-28"]


def test_reconciliation_passes_then_detects_injected_error(tmp_path: Path) -> None:
    root = _book(tmp_path, "champ", DAYS)
    b = pa.load_book(root, "champ", "champion")
    r = pa.reconcile_book(b, DAYS[0], DAYS[-1])
    assert len(r) == 4 and r["ok"].all() and abs(r["fills_fee_diff"].dropna()).max() < 1e-9
    eq = pd.read_csv(root / "equity.csv")
    eq.loc[2, "equity"] += 1.0  # 注入 1 元错误
    eq.to_csv(root / "equity.csv", index=False)
    b2 = pa.load_book(root, "champ", "champion")
    r2 = pa.reconcile_book(b2, DAYS[0], DAYS[-1])
    bad = r2[~r2["ok"]]
    # 权益的水平错误在逐日差里出现两次:注入日 +1,次日 −1(次日的基数被抬高)
    assert list(bad["date"]) == [DAYS[2], DAYS[3]] and list(bad["diff"].round(9)) == [1.0, -1.0]
    w = pa.weekly_reconciliation(r2)
    assert (~w["ok"]).sum() == 2  # 09-25 与 09-28 分属两个 ISO 周


def test_positions_reconcile_then_detect_injected_mismatch(tmp_path: Path) -> None:
    root = _book(tmp_path, "champ", DAYS, blocked=True)
    b = pa.load_book(root, "champ", "champion")
    p = pa.reconcile_positions(b, DAYS[0], DAYS[-1])
    # 第 1 天没有前一日日志不计;第 2–4 天:成交累计与订单目标都对得上,被挡的 AL 腿保持空仓
    assert (
        list(p["date"]) == list(DAYS[1:]) and p["ok"].all() and p["fills_ok"].all() and p["target_ok"].all()
    )
    assert list(p["n_positions"]) == [1, 1, 1]
    st = pa.state_consistency(b)
    assert st["ok"] and st["state_vs_log"] and st["state_vs_csv"] is None  # 合成账本没有 positions.csv
    assert list(pa.weekly_positions(p)["ok"]) == [True, True]
    # 注入 1:最后一天日志持仓改成 99 手 → 成交累计与目标都对不上,state.json 与日志也对不上
    lp = root / "log" / f"{DAYS[-1].date()}.json"
    j = json.loads(lp.read_text(encoding="utf-8"))
    j["positions"]["CU"][1] = 99.0
    lp.write_text(json.dumps(j), encoding="utf-8")
    b2 = pa.load_book(root, "champ", "champion")
    p2 = pa.reconcile_positions(b2, DAYS[0], DAYS[-1])
    last = p2.iloc[-1]
    assert not last["ok"] and not last["fills_ok"] and last["target_ok"] is not None and not last["target_ok"]
    assert "CU: 期望 CU2610/3 实际 CU2610/99" in last["detail"]
    assert not pa.state_consistency(b2)["ok"]
    # 注入 2:把被挡的 AL 腿改成 filled → 成交累计多出 AL,但日志里没有;目标也对不上
    j["positions"]["CU"][1] = 3.0
    lp.write_text(json.dumps(j), encoding="utf-8")
    fp = root / "fills" / f"{DAYS[2].date()}.csv"
    f = pd.read_csv(fp)
    f.loc[f["symbol"] == "AL", "status"] = "filled"
    f.to_csv(fp, index=False)
    p3 = pa.reconcile_positions(pa.load_book(root, "champ", "champion"), DAYS[0], DAYS[-1])
    row = p3[p3["date"] == DAYS[2]].iloc[0]
    assert not row["fills_ok"] and row["target_ok"] is not None and not row["target_ok"]
    assert "AL: 期望 AL2610/2 实际 无" in row["detail"]


def test_slippage_calibration_units_and_missing_quotes(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    specs = load_instruments()
    cu = specs["CU"]
    assert cu.exchange == "SHFE"
    root = _book(tmp_path, "champ", DAYS)
    b = pa.load_book(root, "champ", "champion")
    # 只给第 2 天写行情:开盘 = 成交价 − 1 跳(买入腿按账本假设成交),均价 = 开盘;上期所成交额单位万元
    d = DAYS[1]
    open_ = 70000.0 - cu.tick
    vol = 100.0
    qdir = tmp_path / "data" / "exchanges" / "SHFE" / "quotes" / str(d.year)
    qdir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "date": d,
                "exchange": "SHFE",
                "symbol": "CU",
                "contract": "CU2610",
                "open": open_,
                "volume": vol,
                "turnover": open_ * vol * cu.multiplier / pa.TURNOVER_UNIT["SHFE"],
                "settle": open_,
            }
        ]
    ).to_parquet(qdir / f"{d.strftime('%Y%m%d')}.parquet", index=False)
    legs, summ = pa.slippage_calibration(b, DAYS[0], DAYS[-1], tmp_path / "data" / "exchanges", specs)
    assert len(legs) == 3 and legs["vwap"].isna().sum() == 2
    r = legs[legs["date"] == d].iloc[0]
    assert (
        r["side"] == 1.0 and abs(r["open_vs_vwap_ticks"]) < 1e-9 and abs(r["fill_vs_open_ticks"] - 1) < 1e-9
    )
    assert abs(r["fill_vs_vwap_ticks"] - 1) < 1e-9 and abs(r["open_vs_vwap_bp"]) < 1e-9
    assert len(summ) == 1 and summ.iloc[0]["n"] == 3 and summ.iloc[0]["n_missing"] == 2
    assert abs(summ.iloc[0]["fill_open_ticks_mean"] - 1) < 1e-9  # 缺行情的腿是 NaN,不计入均值
    assert pa.TURNOVER_UNIT == {"SHFE": 1e4, "INE": 1e4, "DCE": 1.0, "CZCE": 1.0}
    bk = pa.slippage_by_book(legs)
    assert len(bk) == 1 and bk.iloc[0]["n"] == 3


def test_historical_failures_and_code_drift_from_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "src" / "cta").mkdir(parents=True)
    (repo / "src" / "cta" / "x.py").write_text("a = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("r\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "A")
    sha_a = _git(repo, "rev-parse", "--short", "HEAD")
    # 失败日:FAILED.json 提交后被删除(成功重放);一条在新目录,一条在旧目录名(= 标签)下
    (repo / "paper" / "v03").mkdir(parents=True)
    (repo / "paper" / "v03" / "FAILED.json").write_text(
        json.dumps({"date": str(DAYS[1].date()), "stage": "settle", "error": "boom"}), encoding="utf-8"
    )
    (repo / "paper_v01r").mkdir()
    (repo / "paper_v01r" / "FAILED.json").write_text(
        json.dumps({"date": str(DAYS[2].date()), "stage": "orders", "error": "old dir"}), encoding="utf-8"
    )
    (repo / "elsewhere").mkdir()
    (repo / "elsewhere" / "FAILED.json").write_text(
        json.dumps({"date": str(DAYS[1].date())}), encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "paper: failed")
    _git(repo, "rm", "-q", "paper/v03/FAILED.json", "paper_v01r/FAILED.json", "elsewhere/FAILED.json")
    _git(repo, "commit", "-q", "-m", "paper: replayed")
    (repo / "README.md").write_text("r2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "B docs only")
    sha_b = _git(repo, "rev-parse", "--short", "HEAD")
    (repo / "src" / "cta" / "x.py").write_text("a = 2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "C code")
    sha_c = _git(repo, "rev-parse", "--short", "HEAD")

    dirs = {"paper_v03": "paper/v03", "paper_v01r": "paper/v01r"}
    h = pa.historical_failures(repo, dirs, DAYS[0], DAYS[-1])
    assert sorted(h["book"]) == ["paper_v01r", "paper_v03"] and h["source"].str.startswith("git ").all()
    assert set(h["stage"]) == {"settle", "orders"}
    assert pa.historical_failures(tmp_path, dirs, DAYS[0], DAYS[-1]).empty  # 不是仓库 → 空表,不报错
    assert pa.historical_failures(repo, dirs, DAYS[3], DAYS[3]).empty  # 窗口外
    # 合并:有权益行且无 FAILED.json → 已修复
    book_root = _book(repo, "champ", DAYS, git_shas=[sha_a, sha_a, sha_b, sha_c])
    b = pa.load_book(book_root, "paper_v03", "champion")
    m = pa.merge_failures(b, pa.failures(b, DAYS[0], DAYS[-1]), h[h["book"] == "paper_v03"])
    assert len(m) == 1 and m.iloc[0]["status"] == "已修复(重放补齐)"

    proto = pa.load_protocol(_protocol(repo, extra=""))
    d = pa.drift(b, DAYS[0], DAYS[-1], proto, root=repo)
    g = d[d["field"] == "git_sha"]
    assert list(g["date"]) == [DAYS[2], DAYS[3]]
    dec, note = dict(zip(g["date"], g["declared"], strict=True)), dict(zip(g["date"], g["note"], strict=True))
    assert dec[DAYS[2]] and "仅非账本路径" in str(note[DAYS[2]])
    assert not dec[DAYS[3]] and "src/cta/x.py" in str(note[DAYS[3]])
    # 不给 root → 保持旧行为:两次都未声明
    d0 = pa.drift(b, DAYS[0], DAYS[-1], proto)
    assert not d0[d0["field"] == "git_sha"]["declared"].any()
    # 清单里 from → to 声明后 → 已声明(短 sha 前缀即可)
    proto2 = pa.load_protocol(
        _protocol(
            repo / "p2",
            extra=f"  - {{from: {sha_b}, to: {sha_c}, fields: [git_sha], note: 已核对的代码切换}}\n",
        )
    )
    d2 = pa.drift(b, DAYS[0], DAYS[-1], proto2, root=repo)
    g2 = d2[d2["field"] == "git_sha"]
    dec2 = dict(zip(g2["date"], g2["declared"], strict=True))
    note2 = dict(zip(g2["date"], g2["note"], strict=True))
    assert (
        dec2[DAYS[3]]
        and "已核对的代码切换" in str(note2[DAYS[3]])
        and "账本路径改动 1 个文件" in str(note2[DAYS[3]])
    )


def test_config_drift_is_reported_and_classified(tmp_path: Path) -> None:
    root = _book(tmp_path, "champ", DAYS, snaps=["cfg0", "cfg0", "cfg1", "cfg1"])
    b = pa.load_book(root, "champ", "champion")
    d = pa.drift(b, DAYS[0], DAYS[-1], pa.load_protocol(_protocol(tmp_path)))
    changes = d[d["field"] == "config_digest"]
    assert (changes["category"] == "策略配置变化").any() and not changes[
        changes["category"] == "策略配置变化"
    ]["declared"].iloc[0]
    assert (d["category"] == "与协议清单不符").sum() == 2  # cfg1 的两天不等于清单预期 cfg0
    assert (d[d["field"] == "secondary_sha"]["declared"]).all()  # 交易所段每日增量视为预期
    d2 = pa.drift(b, DAYS[0], DAYS[-1], pa.load_protocol(_protocol(tmp_path / "p2", declared=True)))
    assert d2[(d2["field"] == "config_digest") & (d2["category"] == "策略配置变化")]["declared"].iloc[0]


def test_preliminary_report_and_pending_drills(tmp_path: Path) -> None:
    _book(tmp_path, "champ", DAYS)
    _book(tmp_path, "chal", DAYS)
    proto = _protocol(tmp_path)
    out = tmp_path / "out"
    rep = tmp_path / "rep.md"
    r = pa.run_acceptance(
        tmp_path,
        DAYS[0],
        pd.Timestamp("2026-12-15"),
        out,
        rep,
        proto,
        holidays=HOL,
        n_boot=50,
        drills_dir=tmp_path / "drills",
    )
    assert r.status == "PRELIMINARY" and r.asof == DAYS[-1] and r.reconciliation_ok and r.completeness_ok
    assert r.positions_ok and list(r.summary["positions_reconciled"]) == [True, True]
    assert list(r.summary["failures"]) == ["0", "0"]
    txt = rep.read_text(encoding="utf-8")
    assert "PRELIMINARY" in txt and "PENDING" in txt and r.drills_status == "PENDING" and "样本量不足" in txt
    assert "## 4. 持仓对账" in txt and "## 8. 滑点校准" in txt and "(验收期内无成交腿)" not in txt
    assert "显著" not in txt
    for f in (
        "paired_differences.csv",
        "completeness.csv",
        "positions_reconciliation.csv",
        "slippage_legs.csv",
    ):
        assert (out / f).exists()
    (tmp_path / "drills").mkdir()
    (tmp_path / "drills" / "2026-10-01_x.json").write_text(
        json.dumps(
            {
                "date": "2026-10-01",
                "book": "champ",
                "injected": "rm quotes",
                "detected": True,
                "recovered": True,
                "outcome": "ok",
            }
        ),
        encoding="utf-8",
    )
    r2 = pa.run_acceptance(
        tmp_path, DAYS[0], DAYS[-1], out, rep, proto, holidays=HOL, n_boot=50, drills_dir=tmp_path / "drills"
    )
    assert r2.status == "FINAL" and r2.drills_status == "DONE" and "DONE" in rep.read_text(encoding="utf-8")
    # 只读:账本文件未被改动
    assert not (tmp_path / "champ" / "FAILED.json").exists() and sorted(
        p.name for p in (tmp_path / "champ").iterdir()
    ) == ["equity.csv", "fills", "log", "orders", "state.json"]
