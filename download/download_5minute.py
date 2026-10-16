"""下载 5 分钟线(逐合约 parquet,断点续跑)。

产物:data/ricecta/data/futures_5minute/<SYM>/<CONTRACT>.parquet
  index datetime(bar 结束时间,含夜盘,夜盘归属下一交易日),列:
  open/high/low/close/volume/total_turnover/open_interest/trading_date
  —— research/scripts/exec_fills.py 直接可读(它用 volume/total_turnover/open/trading_date)。
范围:合约退市日 >= start(默认 2016-01-01)的全部商品合约;生产 22 品种优先。

用量提示:8 个字段时约 15–25 字节/行(全字段约 250 字节/行,务必保留 fields 参数)。
配额不足时干净退出,重跑即续(已存在的文件跳过)。

用法:
  .venv/bin/python download/download_5minute.py                     # 全部商品品种,续跑
  .venv/bin/python download/download_5minute.py --symbols CU,RB     # 只跑部分品种
  .venv/bin/python download/download_5minute.py --limit 3           # 冒烟:只下 3 个合约
  .venv/bin/python download/download_5minute.py --check             # 只统计已有文件,不下载
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

FIELDS = ["open", "high", "low", "close", "volume", "total_turnover", "open_interest", "trading_date"]
OUT_DIR = "futures_5minute"


def contract_path(symbol: str, contract: str) -> Path:
    return rc.DATA_ROOT / OUT_DIR / symbol / f"{contract.upper()}.parquet"


def fetch_batch(rq: Any, contracts: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """一次请求多个合约(降低往返;逐合约返回)。返回 {contract: DataFrame}。"""
    df = rc.retry(
        lambda: rq.get_price(list(contracts), start_date=start, end_date=end, frequency="5m", fields=FIELDS)
    )
    if df is None or len(df) == 0:
        return {}
    if not isinstance(df.index, pd.MultiIndex):  # 单合约返回普通索引
        df = df.rename_axis("datetime")
        return {contracts[0].upper(): _prepare(df)}
    x: pd.DataFrame = df.reset_index()
    out: dict[str, pd.DataFrame] = {}
    for contract, sub in x.groupby("order_book_id", sort=False):
        out[str(contract).upper()] = _prepare(sub.set_index("datetime").drop(columns="order_book_id"))
    return out


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "datetime"
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    for c in ["open", "high", "low", "close", "volume", "total_turnover", "open_interest"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
    return df.sort_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="逗号分隔;默认全部商品品种(生产 22 优先)")
    ap.add_argument("--start", default=rc.DEFAULT_START)
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="最多下载多少个合约(冒烟用)")
    ap.add_argument("--batch", type=int, default=5, help="每次 API 请求合并的合约数(默认 5)")
    ap.add_argument("--check", action="store_true", help="只统计已下载文件与行数")
    args = ap.parse_args()

    uni = rc.load_universe()
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or rc.commodity_symbols(uni)

    if args.check:
        total_files = total_bytes = 0
        for sym in syms:
            paths = sorted((rc.DATA_ROOT / OUT_DIR / sym).glob("*.parquet"))
            total_files += len(paths)
            total_bytes += sum(p.stat().st_size for p in paths)
            if paths:
                print(f"{sym}: {len(paths)} 个合约文件, 最新 {paths[-1].stem}")
        print(f"合计 {total_files} 个文件, {total_bytes / 2**20:.1f} MiB")
        return 0

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    done = skipped = 0
    t_start = time.time()
    try:
        for sym in syms:
            ids = rc.contracts_since(uni, sym, args.start)
            pending = [
                c
                for c in ids
                if not (
                    contract_path(sym, c).exists()
                    and contract_path(sym, c).stat().st_size > 0
                    and not args.force
                )
            ]
            skipped += len(ids) - len(pending)
            rows_sym = 0
            for batch in rc.chunked(pending, max(args.batch, 1)):
                if args.limit and done >= args.limit:
                    raise StopIteration
                guard.tick()
                got = fetch_batch(rq, list(batch), args.start, args.end)
                for contract in batch:
                    df = got.get(contract.upper())
                    if df is not None and len(df):
                        rc.write_parquet(df, contract_path(sym, contract))
                        rows_sym += len(df)
                        done += 1
                if done and done % 20 < len(batch):
                    el = time.time() - t_start
                    print(f"  ... {done} 个已下载, {skipped} 个已存在, 用时 {el / 60:.1f} 分钟", flush=True)
                    rc.record(item="futures_5minute", n_done=done, n_skipped=skipped, seconds=round(el, 1))
            if rows_sym:
                print(f"{sym}: 新增 {rows_sym} 行", flush=True)
    except StopIteration:
        print(f"达到 --limit {args.limit},停止")
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};已下载 {done} 个合约,明天重跑即续")
        rc.record(item="futures_5minute", status="quota", n_done=done)
        return 3
    print(f"done: 新下载 {done} 个合约,跳过 {skipped} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
