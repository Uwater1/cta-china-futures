"""下载利率、宏观与现货数据。

产物(data/ricecta/data/):
  shibor/shibor.parquet            上海银行间同业拆放利率 index date,列 ON/1W/2W/1M/3M/6M/9M/1Y(百分数)
  econ/macro_factors.parquet       米筐全部 4006 个宏观因子 long:factor/info_date/start_date/end_date/value
                                   (含 info_date 发布时点,可做点时回测)
  econ/money_supply.parquet        货币供应量(含同比)
  econ/reserve_ratio.parquet       存款准备金率(含 info_date/effective_date)
  spot/sge_daily/<INST>.parquet    上金所现货日线(黄金/白银/铂金等 19 个合约)
  spot/sge_benchmark.parquet       AU9999/AG9999/PT9995 的早盘价/午盘价

宏观因子名单来自米筐公开的 econ_get_factors.xlsx(缓存到 data/ricecta/econ_get_factors.xlsx,不进 git)。

用法:
  .venv/bin/python download/download_macro.py [--skip shibor,econ,spot] [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from functools import partial
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

FACTORS_XLSX = "https://assets.ricequant.com/vendor/rqdata/econ_get_factors.xlsx"
FACTORS_CACHE = rc.DATA_ROOT.parent / "econ_get_factors.xlsx"
BENCHMARK_SPOTS = ["AU9999.SGEX", "AG9999.SGEX", "PT9995.SGEX"]


def factor_names() -> list[str]:
    if not FACTORS_CACHE.exists():
        FACTORS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FACTORS_XLSX, FACTORS_CACHE)  # noqa: S310 - 米筐公开文档链接
    names = pd.read_excel(FACTORS_CACHE).iloc[:, 0].tolist()
    return [str(n) for n in names[1:] if str(n).strip()]  # 第一行是表头


def fetch_macro(rq: Any, guard: rc.QuotaGuard, start: str, end: str) -> pd.DataFrame:
    names = factor_names()
    print(f"宏观因子 {len(names)} 个")
    frames: list[pd.DataFrame] = []
    for i, batch in enumerate(rc.chunked(names, 40)):
        guard.tick()
        df = rc.retry(partial(rq.econ.get_factors, batch, start_date=start, end_date=end))
        if df is not None and len(df):
            frames.append(df.reset_index())
        if (i + 1) % 10 == 0:
            print(f"  ... {min((i + 1) * 40, len(names))}/{len(names)}", flush=True)
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x["info_date"] = pd.to_datetime(x["info_date"])
    return (
        x.drop_duplicates(["factor", "info_date"]).sort_values(["factor", "info_date"]).reset_index(drop=True)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--skip", default="", help="逗号分隔:shibor,econ,spot")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    try:
        if "shibor" not in skip:
            out = rc.DATA_ROOT / "shibor" / "shibor.parquet"
            if not out.exists() or args.force:
                s = rc.retry(lambda: rq.get_interbank_offered_rate(args.start, args.end))
                s.index = pd.to_datetime(s.index)
                rc.write_parquet(s, out)
                print(f"shibor: {s.shape} -> {out}")

        if "econ" not in skip:
            if not (rc.DATA_ROOT / "econ" / "macro_factors.parquet").exists() or args.force:
                t0 = time.time()
                mf = fetch_macro(rq, guard, args.start, args.end)
                rc.write_parquet(mf, rc.DATA_ROOT / "econ" / "macro_factors.parquet", index=False)
                print(f"macro_factors: {mf.shape} ({time.time() - t0:.0f}s)")
                rc.record(item="econ/macro_factors", rows=len(mf))
            for name, fn in [("money_supply", "get_money_supply"), ("reserve_ratio", "get_reserve_ratio")]:
                out = rc.DATA_ROOT / "econ" / f"{name}.parquet"
                if out.exists() and not args.force:
                    continue
                df = rc.retry(partial(getattr(rq.econ, fn), start_date=args.start, end_date=args.end))
                if df is not None and len(df):
                    df = df.reset_index()
                    for c in ("info_date", "effective_date"):
                        if c in df:
                            df[c] = pd.to_datetime(df[c])
                    rc.write_parquet(df, out, index=False)
                    print(f"{name}: {df.shape}")

        if "spot" not in skip:
            insts = rc.retry(lambda: rq.all_instruments(type="Spot"))
            ids = insts["order_book_id"].tolist()
            bench_frames = []
            for inst in ids:
                out = rc.DATA_ROOT / "spot" / "sge_daily" / f"{inst.replace('.', '_')}.parquet"
                if not out.exists() or args.force:
                    guard.tick()
                    df = rc.retry(
                        partial(rq.get_price, inst, start_date=args.start, end_date=args.end, frequency="1d")
                    )
                    if df is not None and len(df):
                        df = df.reset_index()
                        df["date"] = pd.to_datetime(df["date"])
                        rc.write_parquet(df, out, index=False)
                if inst in BENCHMARK_SPOTS:
                    guard.tick()
                    bp = rc.retry(partial(rq.get_spot_benchmark_price, inst, args.start, args.end))
                    if bp is not None and len(bp):
                        b = bp.reset_index()
                        b["date"] = pd.to_datetime(b["date"])
                        bench_frames.append(b)
                print(f"spot {inst} ok", flush=True)
            if bench_frames:
                b = pd.concat(bench_frames, ignore_index=True)
                rc.write_parquet(b, rc.DATA_ROOT / "spot" / "sge_benchmark.parquet", index=False)
                print(f"sge_benchmark: {b.shape}")
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};已下载的文件保留,明天重跑即续")
        return 3
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
