"""下载商品期权数据:合约表、主力月份、衍生指标(PCR/IV/skew),可选希腊字母。

产物(data/ricecta/data/options/):
  contracts.parquet            全部商品期权合约:contract/underlying/underlying_symbol/strike/option_type/
                               listed_date/maturity_date/exercise_type
  dominant_month/<SYM>.parquet 期权主力月份 long:date/rank/contract(rank 1=主力,2=次主力)
  indicators/<SYM>.parquet     逐到期月逐日衍生指标:maturity/date/AM_PCR/OI_PCR/VL_PCR/
                               iv_025_dela/iv_minus_025_dela/skew
  greeks/<SYM>.parquet         (--greeks)逐合约逐日 iv/Delta(结算价口径,implied_forward 模型;流量大)
用途:补上交易所文件缺失的大商所期权(design_log 23.4 记录的数据缺口),以及 2025-2026 增量。

用法:
  .venv/bin/python download/download_options.py                    # 合约+主力月份+指标
  .venv/bin/python download/download_options.py --greeks           # 另加希腊字母
  .venv/bin/python download/download_options.py --symbols CU,M    # 只跑部分标的
"""

from __future__ import annotations

import argparse
import sys
import time
from functools import partial
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

# 商品期权标的(交易所上市列表,doc/rqdata_python_options-mod.md §支持的期权品种;不存在的品种会被跳过)
UNDERLYINGS = [
    "CU",
    "RU",
    "AU",
    "ZN",
    "AL",
    "AG",
    "RB",
    "BR",  # SHFE
    "SC",  # INE
    "M",
    "C",
    "I",
    "PG",
    "V",
    "L",
    "PP",
    "P",
    "B",
    "Y",
    "A",
    "EB",
    "EG",  # DCE
    "SR",
    "CF",
    "MA",
    "TA",
    "RM",
    "ZC",
    "OI",
    "PK",
    "PX",
    "SH",
    "SA",
    "PF",
    "AP",
    "SM",
    "SF",
    "UR",  # CZCE
    "SI",
    "LC",  # GFEX
]

INDICATOR_COLS = ["AM_PCR", "OI_PCR", "VL_PCR", "iv_025_dela", "iv_minus_025_dela", "skew"]


def maturities_of(contracts: pd.DataFrame) -> list[str]:
    """到期月份 YYMM 取自标的期货合约代码(CU2503 → 2503);郑商所三位代码按上市年份补十位。

    与 research/scripts/rqdata_export_options.py 保持一致。
    """
    out: set[str] = set()
    for und, listed in zip(contracts["underlying"].astype(str), contracts["listed_date"]):
        digits = "".join(ch for ch in und if ch.isdigit())
        if len(digits) == 3:
            year = pd.Timestamp(listed).year if pd.notna(listed) else pd.Timestamp.today().year
            decade = (year // 10) % 10
            yy = decade * 10 + int(digits[0])
            if yy < year % 100 - 1:
                yy += 10
            digits = f"{yy % 100:02d}{digits[1:]}"
        if len(digits) == 4:
            out.add(digits)
    return sorted(out)


def fetch_contracts(rq: Any, guard: rc.QuotaGuard, underlying: str) -> pd.DataFrame:
    ids = rc.retry(lambda: rq.options.get_contracts(underlying=underlying))
    if not ids:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for batch in rc.chunked(list(ids), 200):
        guard.tick()
        inst = rc.retry(partial(rq.instruments, batch))
        for i in inst if isinstance(inst, list) else [inst]:
            rows.append(
                {
                    "contract": i.order_book_id,
                    "underlying": getattr(i, "underlying_order_book_id", None),
                    "strike": getattr(i, "strike_price", None),
                    "option_type": getattr(i, "option_type", None),
                    "listed_date": getattr(i, "listed_date", None),
                    "maturity_date": getattr(i, "maturity_date", None),
                    "exercise_type": getattr(i, "exercise_type", None),
                }
            )
    df = pd.DataFrame(rows)
    df["underlying_symbol"] = underlying
    df["listed_date"] = pd.to_datetime(df["listed_date"], errors="coerce")
    df["maturity_date"] = pd.to_datetime(df["maturity_date"], errors="coerce")
    return df


def fetch_dominant_month(
    rq: Any, guard: rc.QuotaGuard, underlying: str, start: str, end: str
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for rank in (1, 2):
        guard.tick()
        s = rc.retry(
            partial(rq.options.get_dominant_month, underlying, start_date=start, end_date=end, rank=rank)
        )
        if s is not None and len(s):
            x: pd.DataFrame = s.rename("contract").to_frame()
            x.index.name = "date"
            x = x.reset_index()
            x["date"] = pd.to_datetime(x["date"])
            x["rank"] = rank
            frames.append(x)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["date", "rank"]).reset_index(drop=True)


def fetch_indicators(
    rq: Any, guard: rc.QuotaGuard, underlying: str, contracts: pd.DataFrame, start: str, end: str
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    mats = maturities_of(contracts)
    for mat in mats:
        guard.tick()
        try:
            df = rc.retry(partial(rq.options.get_indicators, underlying, mat, start_date=start, end_date=end))
        except RuntimeError as e:  # 个别到期月无数据/该品种无此月份
            print(f"  {underlying} {mat}: {e}")
            continue
        if df is not None and len(df):
            x = df.reset_index()
            x["maturity"] = mat
            frames.append(x)
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x["date"] = pd.to_datetime(x["date"])
    cols = ["maturity", "date"] + [c for c in INDICATOR_COLS if c in x.columns]
    return x[cols].sort_values(["maturity", "date"]).reset_index(drop=True)


def fetch_greeks(
    rq: Any, guard: rc.QuotaGuard, underlying: str, contracts: pd.DataFrame, start: str, end: str
) -> pd.DataFrame:
    ids = contracts["contract"].tolist()
    frames: list[pd.DataFrame] = []
    for batch in rc.chunked(ids, 50):
        guard.tick()
        g = rc.retry(
            partial(
                rq.options.get_greeks,
                batch,
                start_date=start,
                end_date=end,
                fields=["iv", "Delta"],
                model="implied_forward",
                price_type="settlement",
            )
        )
        if g is not None and len(g):
            frames.append(g.reset_index())
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x = x.rename(columns={"order_book_id": "contract"})
    for c in ("date", "trading_date"):
        if c in x.columns:
            x[c] = pd.to_datetime(x[c])
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="逗号分隔标的;默认全部商品期权标的")
    ap.add_argument("--start", default="2017-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--greeks", action="store_true", help="同时下载逐合约 iv/Delta(流量大)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    underlyings = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or UNDERLYINGS
    out_root = rc.DATA_ROOT / "options"

    all_contracts = []
    try:
        for und in underlyings:
            con_path = out_root / "contracts" / f"{und}.parquet"
            if con_path.exists() and not args.force:
                contracts = pd.read_parquet(con_path)
            else:
                contracts = fetch_contracts(rq, guard, und)
                if len(contracts) == 0:
                    print(f"{und}: 无期权合约,跳过")
                    continue
                rc.write_parquet(contracts, con_path, index=False)
                print(f"{und}: {len(contracts)} 个期权合约")
            all_contracts.append(contracts)

            dm_path = out_root / "dominant_month" / f"{und}.parquet"
            if not dm_path.exists() or args.force:
                dm = fetch_dominant_month(rq, guard, und, args.start, args.end)
                rc.write_parquet(dm, dm_path, index=False)

            ind_path = out_root / "indicators" / f"{und}.parquet"
            if not ind_path.exists() or args.force:
                t0 = time.time()
                ind = fetch_indicators(rq, guard, und, contracts, args.start, args.end)
                rc.write_parquet(ind, ind_path, index=False)
                print(f"{und}: indicators {len(ind)} 行 ({time.time() - t0:.0f}s)", flush=True)
                rc.record(item=f"options/indicators/{und}", rows=len(ind))

            if args.greeks:
                gk_path = out_root / "greeks" / f"{und}.parquet"
                if not gk_path.exists() or args.force:
                    gk = fetch_greeks(rq, guard, und, contracts, args.start, args.end)
                    rc.write_parquet(gk, gk_path, index=False)
                    print(f"{und}: greeks {len(gk)} 行", flush=True)
        if all_contracts:
            rc.write_parquet(
                pd.concat(all_contracts, ignore_index=True), out_root / "contracts.parquet", index=False
            )
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};已下载的文件保留,明天重跑即续")
        return 3
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
