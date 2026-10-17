"""下载非量价与规则类数据:仓单、会员持仓排名、交易参数(保证金/手续费/限额)。

产物(data/ricecta/data/):
  warehouse_stocks/<SYM>.parquet   注册仓单 date/on_warrant/exchange/effective_forecast/warrant_units/
                                   contract_multiplier/deliverable(CZCE 有有效预报,SHFE 有可交割量)
  member_rank/<SYM>.parquet        会员排名 long:trading_date/commodity_id/rank_by/member_name/rank/volume/volume_change
                                   (rank_by = volume|long|short;上期所/中金所为合约加总,仓库历史上缺的排名可从这份补)
  trading_parameters/<SYM>.parquet 逐合约逐日交易参数 index (contract, trading_date):
                                   多空保证金率/手续费/平今折扣/限仓/最小下单量等 —— 监管事件层可覆盖大商所
                                   (DCE 2018-12 起)与郑商所(2021-04 起),交易所抓取只到部分所。

用法:
  .venv/bin/python download/download_nonprice.py [--symbols CU,RB] [--start 2016-01-01] [--skip rank,params]
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

RANK_BY = ("volume", "long", "short")


def fetch_warehouse(rq: Any, guard: rc.QuotaGuard, symbol: str, start: str, end: str) -> pd.DataFrame:
    df = rc.retry(lambda: rq.futures.get_warehouse_stocks(symbol, start_date=start, end_date=end))
    if df is None or len(df) == 0:
        return pd.DataFrame()
    x: pd.DataFrame = df.reset_index()
    x["date"] = pd.to_datetime(x["date"])
    return x.sort_values("date").reset_index(drop=True)


def fetch_rank(rq: Any, guard: rc.QuotaGuard, symbol: str, start: str, end: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for rank_by in RANK_BY:
        guard.tick()
        df = rc.retry(
            partial(rq.futures.get_member_rank, symbol, start_date=start, end_date=end, rank_by=rank_by)
        )
        if df is not None and len(df):
            x = df.reset_index()
            x["rank_by"] = rank_by
            frames.append(x)
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x["trading_date"] = pd.to_datetime(x["trading_date"])
    return x.sort_values(["trading_date", "rank_by", "rank"]).reset_index(drop=True)


def fetch_params(
    rq: Any, guard: rc.QuotaGuard, uni: pd.DataFrame, symbol: str, start: str, end: str
) -> pd.DataFrame:
    ids = rc.contracts_since(uni, symbol, start)
    frames: list[pd.DataFrame] = []
    for batch in rc.chunked(ids, 20):
        guard.tick()
        df = rc.retry(partial(rq.futures.get_trading_parameters, batch, start_date=start, end_date=end))
        if df is not None and len(df):
            frames.append(df.reset_index())
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True).rename(columns={"order_book_id": "contract"})
    x["trading_date"] = pd.to_datetime(x["trading_date"])
    return x.set_index(["contract", "trading_date"]).sort_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--start", default=rc.DEFAULT_START)
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--skip", default="", help="逗号分隔:warehouse,rank,params")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    uni = rc.load_universe()
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or rc.commodity_symbols(uni)
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    jobs: dict[str, tuple[str, Callable[[str], pd.DataFrame]]] = {
        "warehouse": ("warehouse_stocks", lambda sym: fetch_warehouse(rq, guard, sym, args.start, args.end)),
        "rank": ("member_rank", lambda sym: fetch_rank(rq, guard, sym, args.start, args.end)),
        "params": ("trading_parameters", lambda sym: fetch_params(rq, guard, uni, sym, args.start, args.end)),
    }
    try:
        for key, (dirname, fetch) in jobs.items():
            if key in skip:
                continue
            for sym in syms:
                out = rc.DATA_ROOT / dirname / f"{sym}.parquet"
                if out.exists() and not args.force:
                    continue
                t0 = time.time()
                df = fetch(sym)
                rc.write_parquet(df, out)
                print(f"{dirname}/{sym}: {len(df)} 行 ({time.time() - t0:.0f}s)", flush=True)
                rc.record(item=f"{dirname}/{sym}", rows=len(df))
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};已下载的文件保留,明天重跑即续")
        return 3
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
