"""下载合约基础信息与主力表(小体量、结构性数据)。

产物(data/ricecta/data/):
  universe/futures_instruments.parquet   全部期货合约基础信息(all_instruments 原样,含上市/退市日、乘数、保证金)
  dominant_contracts/dominant.parquet    主力合约(rule=0,rank=1)——与既有米筐导出口径一致
  dominant_contracts/dominant2.parquet   次主力(rule=0,rank=2)
  dominant_contracts/dominant3.parquet   次次主力(rule=0,rank=3)
  dominant_contracts/dominant_rule1.parquet  最大昨仓即主力(rule=1,rank=1),用于规则敏感性研究
列:date, symbol, contract。

用法:
  .venv/bin/python download/download_meta.py [--symbols CU,RB] [--start 2016-01-01] [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402


def fetch_instruments(rq, force: bool) -> pd.DataFrame:
    path = rc.DATA_ROOT / "universe" / "futures_instruments.parquet"
    if path.exists() and not force:
        print("universe 已存在,跳过(用 --force 重下)")
        return pd.read_parquet(path)
    t0 = time.time()
    df = rc.retry(lambda: rq.all_instruments(type="Future"))
    rc.write_parquet(df, path, index=False)
    rc.record(item="universe/futures_instruments", rows=len(df), seconds=round(time.time() - t0, 1))
    print(f"universe {df.shape} -> {path}")
    return df


def fetch_dominant(rq, symbol: str, rank: int, rule: int, start: str, end: str) -> pd.DataFrame | None:
    s = rc.retry(
        lambda: rq.futures.get_dominant(symbol, start_date=start, end_date=end, rule=rule, rank=rank)
    )
    if s is None or len(s) == 0:
        return None
    df = s.rename("contract").to_frame()
    df.index.name = "date"
    df = df.reset_index()
    df = df[df["contract"].notna()]
    if len(df) == 0:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df["symbol"] = symbol
    return df[["date", "symbol", "contract"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="逗号分隔;默认全部商品品种")
    ap.add_argument("--start", default=rc.DEFAULT_START)
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    uni = fetch_instruments(rq, args.force)
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or rc.commodity_symbols(uni)

    # 逐 (variant, symbol) 存分片,再合并 —— 支持部分品种运行与配额中断续跑
    variants = {"dominant": (0, 1), "dominant2": (0, 2), "dominant3": (0, 3), "dominant_rule1": (1, 1)}
    for name, (rule, rank) in variants.items():
        piece_dir = rc.DATA_ROOT / "dominant_contracts" / "_pieces" / name
        out = rc.DATA_ROOT / "dominant_contracts" / f"{name}.parquet"
        t0 = time.time()
        try:
            for sym in syms:
                piece = piece_dir / f"{sym}.parquet"
                if piece.exists() and not args.force:
                    continue
                guard.tick()
                d = fetch_dominant(rq, sym, rank, rule, args.start, args.end)
                if d is not None:
                    rc.write_parquet(d, piece, index=False)
        except rc.QuotaExhausted as e:
            print(f"[配额] {name}: {e};分片已保留,明天重跑本脚本续跑")
            return 3
        pieces = sorted(piece_dir.glob("*.parquet"))
        if pieces:
            allf = pd.concat([pd.read_parquet(p) for p in pieces], ignore_index=True).sort_values(
                ["symbol", "date"]
            )
            rc.write_parquet(allf, out, index=False)
            rc.record(item=f"dominant_contracts/{name}", rows=len(allf), seconds=round(time.time() - t0, 1))
            print(f"{name}: {len(allf)} 行,{len(pieces)} 个品种分片 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
