"""可选:tick 快照抽样下载(默认不跑 —— 流量极大,按合约日计)。

用途:成交价/价差/微观结构的现场校准(exec 层),不是全历史因子数据。
只下"主力合约 × 指定窗口",每个 (合约, 交易日) 一个 parquet。

产物:data/ricecta/data/futures_tick/<SYM>/<CONTRACT>/<YYYY-MM-DD>.parquet
  index datetime,列 last/volume/total_turnover/open_interest/a1/b1/a1_v/b1_v/trading_date

成本参考:单合约日 ≈ 1–3 MiB 传输(7–8 个字段下略低);22 品种 × 60 个交易日 ≈ 1.5–4 GiB,
超过试用账户一天配额,务必用 --max-days 分批。

用法:
  .venv/bin/python download/download_tick.py --start 2026-09-01 --end 2026-09-30 --max-days 20
  .venv/bin/python download/download_tick.py --symbols CU,AU --start 2026-10-01 --end 2026-10-15
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

FIELDS = ["last", "volume", "total_turnover", "open_interest", "a1", "b1", "a1_v", "b1_v", "trading_date"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="起始交易日(必填,防止误跑)")
    ap.add_argument("--end", required=True)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--max-days", type=int, default=50, help="本次最多下载的合约日数(安全阀)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    dm = pd.read_parquet(rc.DATA_ROOT / "dominant_contracts" / "dominant.parquet")
    dm["date"] = pd.to_datetime(dm["date"])
    dm = dm[(dm["date"] >= args.start) & (dm["date"] <= args.end)]
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or sorted(dm["symbol"].unique())

    tasks = []
    for sym in syms:
        sub = dm[dm["symbol"] == sym]
        for _, r in sub.iterrows():
            tasks.append((sym, str(r["contract"]), r["date"]))
    if not tasks:
        print("窗口内没有主力合约记录")
        return 0
    print(f"共 {len(tasks)} 个合约日,本次上限 {args.max_days}")

    n = 0
    t0 = time.time()
    try:
        for sym, contract, day in tasks:
            if n >= args.max_days:
                break
            out = rc.DATA_ROOT / "futures_tick" / sym / contract.upper() / f"{day.strftime('%Y%m%d')}.parquet"
            if out.exists() and not args.force:
                continue
            guard.tick()
            df = rc.retry(
                lambda c=contract, d=day: rq.get_price(
                    c, start_date=d, end_date=d, frequency="tick", fields=FIELDS
                )
            )
            if df is None or len(df) == 0:
                continue
            if isinstance(df.index, pd.MultiIndex):
                df = df.droplevel(0)
            df.index = pd.to_datetime(df.index)
            df.index.name = "datetime"
            if "trading_date" in df.columns:
                df["trading_date"] = pd.to_datetime(df["trading_date"])
            rc.write_parquet(df.sort_index(), out)
            n += 1
            if n % 5 == 0:
                print(f"  ... {n} 个合约日,{time.time() - t0:.0f}s", flush=True)
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};已下载 {n} 个合约日,明天重跑即续")
        return 3
    print(f"done: {n} 个合约日")
    return 0


if __name__ == "__main__":
    sys.exit(main())
