"""下载与商品期货相关的指数行情(中证 CFCI/CFI 系列、商品期货策略指数等)。

产物(data/ricecta/data/indices/):
  index_list.parquet            命中的指数清单:order_book_id/symbol/listed_date/de_listed_date/base_date/base_point
  commodity_indices.parquet     日线 long:order_book_id/date/open/high/low/close/volume/total_turnover
用途:板块级 regime/中性化参考、与南华 NHCI 的交叉验证;自带策略指数(动量/趋势配置/短中期期限)
可做基准比较。默认取 2010 年起(指数基日更早,流量很小)。

用法:
  .venv/bin/python download/download_indices.py [--start 2010-01-01] [--force]
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

PATTERN = "商品期货|CFCI|原油期货|期货成份|期货综合"


def select_indices(rq: Any, guard: rc.QuotaGuard) -> pd.DataFrame:
    inst: pd.DataFrame = rc.retry(lambda: rq.all_instruments(type="Index"))
    hit = inst[inst["symbol"].astype(str).str.contains(PATTERN, regex=True, na=False)].copy()
    cols = [
        c
        for c in [
            "order_book_id",
            "symbol",
            "listed_date",
            "de_listed_date",
            "base_date",
            "base_point",
            "status",
        ]
        if c in hit.columns
    ]
    return hit[cols].drop_duplicates("order_book_id").sort_values("order_book_id").reset_index(drop=True)


def fetch_prices(rq: Any, guard: rc.QuotaGuard, ids: list[str], start: str, end: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for batch in rc.chunked(ids, 20):
        guard.tick()
        df = rc.retry(partial(rq.get_price, batch, start_date=start, end_date=end, frequency="1d"))
        if df is not None and len(df):
            frames.append(df.reset_index())
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x["date"] = pd.to_datetime(x["date"])
    return x.sort_values(["order_book_id", "date"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    out_dir = rc.DATA_ROOT / "indices"
    try:
        lst_path = out_dir / "index_list.parquet"
        if lst_path.exists() and not args.force:
            lst = pd.read_parquet(lst_path)
        else:
            lst = select_indices(rq, guard)
            rc.write_parquet(lst, lst_path, index=False)
        print(f"商品相关指数 {len(lst)} 个")

        px_path = out_dir / "commodity_indices.parquet"
        if not px_path.exists() or args.force:
            t0 = time.time()
            px = fetch_prices(rq, guard, lst["order_book_id"].tolist(), args.start, args.end)
            rc.write_parquet(px, px_path, index=False)
            rc.record(item="indices/commodity_indices", rows=len(px))
            print(f"commodity_indices: {len(px)} 行 ({time.time() - t0:.0f}s)")
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};明天重跑本脚本")
        return 3
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
