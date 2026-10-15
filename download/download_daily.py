"""下载日频行情与曲线结构数据(合约级日线、主力连续、交易所日线、展期收益率)。

产物(data/ricecta/data/):
  contracts_daily/<SYM>.parquet      合约级日线 index (contract, date), float32:
                                     open/high/low/close/volume/total_turnover/open_interest
                                     —— RicequantParquetSource.contracts() 直接可读
  contracts_daily/metadata.parquet   合约元数据 index contract:
                                     symbol/exchange/listed_date/de_listed_date/maturity_date/margin_rate/multiplier(+name)
  dominant_daily/<SYM>.parquet       主力连续日线(前复权 prev_close_spread;与既有导出口径一致)index date:
                                     contract/open/high/low/close/settlement/prev_settlement/limit_up/limit_down/volume/open_interest
  exchange_daily/<SYM>.parquet       交易所日线(含官方结算价)index (contract, date):
                                     open/close/high/low/total_turnover/volume/settlement/prev_settlement/open_interest
  continuous/<SYM>.parquet           近月/次月连续合约 date/front_month/next_month
  roll_yield/<SYM>.parquet           展期收益率 long:type/date/from_contract/to_contract/yield/annualized_yield/annualized_yield_trading

用法:
  .venv/bin/python download/download_daily.py [--symbols CU,RB] [--start 2016-01-01] [--force]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

DAILY_FIELDS = ["open", "high", "low", "close", "volume", "total_turnover", "open_interest"]
DOM_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "settlement",
    "prev_settlement",
    "limit_up",
    "limit_down",
    "volume",
    "open_interest",
]
EXCH_FIELDS = [
    "open",
    "close",
    "high",
    "low",
    "total_turnover",
    "volume",
    "settlement",
    "prev_settlement",
    "open_interest",
]


def contracts_daily(rq, guard, uni, symbol: str, start: str, end: str) -> pd.DataFrame:
    ids = rc.contracts_since(uni, symbol, start)
    frames = []
    for batch in rc.chunked(ids, 40):
        guard.tick()
        df = rc.retry(
            lambda b=batch: rq.get_price(
                b, start_date=start, end_date=end, frequency="1d", fields=DAILY_FIELDS
            )
        )
        if df is not None and len(df):
            frames.append(df.reset_index())
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x = x.rename(columns={"order_book_id": "contract"})
    x["date"] = pd.to_datetime(x["date"])
    for c in DAILY_FIELDS:
        x[c] = pd.to_numeric(x[c], errors="coerce").astype("float32")
    return x.set_index(["contract", "date"]).sort_index()


def metadata(uni: pd.DataFrame, symbols: list[str], start: str) -> pd.DataFrame:
    """合约元数据,保持既有导出的原始列名(order_book_id/underlying_symbol/contract_multiplier 等)。

    注意:`RicequantParquetSource.contract_meta()` 依赖这些原始列名做重命名,不要在这里改成
    contract/symbol 之类的规范化列名。
    """
    sub = uni[uni["underlying_symbol"].isin(symbols)].copy()
    for c in ["listed_date", "de_listed_date", "maturity_date", "start_delivery_date", "end_delivery_date"]:
        if c in sub.columns:
            sub[c] = pd.to_datetime(sub[c], errors="coerce")
    sub = sub[sub["listed_date"].notna()]  # 排除合成连续合约(88/888/889/99,无上市日)
    sub = sub[sub["de_listed_date"].isna() | (sub["de_listed_date"] >= pd.Timestamp(start))]
    sub["margin_rate"] = pd.to_numeric(sub["margin_rate"], errors="coerce")
    bad = sub["maturity_date"] < sub["listed_date"]
    if bad.any():  # validate_meta 要求 maturity_date >= listed_date
        print(f"metadata: 丢弃 {int(bad.sum())} 行 maturity<listed 的异常合约")
        sub = sub[~bad]
    return sub.sort_values("order_book_id")


def dominant_daily(rq, guard, symbol: str, start: str, end: str, dm: pd.DataFrame | None) -> pd.DataFrame:
    df = rc.retry(
        lambda: rq.futures.get_dominant_price(
            symbol, start_date=start, end_date=end, adjust_type="pre", fields=DOM_FIELDS
        )
    )
    if df is None or len(df) == 0:
        return pd.DataFrame()
    x = df.reset_index()
    x["date"] = pd.to_datetime(x["date"])
    if dm is not None and len(dm):
        pair = dm[dm["symbol"] == symbol][["date", "contract"]].drop_duplicates("date")
        x = x.merge(pair, on="date", how="left")
    else:
        x["contract"] = pd.NA
    order = ["contract"] + DOM_FIELDS
    return x.set_index("date")[order].sort_index()


def exchange_daily(rq, guard, uni, symbol: str, start: str, end: str) -> pd.DataFrame:
    ids = rc.contracts_since(uni, symbol, start)
    frames = []
    for batch in rc.chunked(ids, 40):
        guard.tick()
        df = rc.retry(
            lambda b=batch: rq.futures.get_exchange_daily(
                b, start_date=start, end_date=end, fields=EXCH_FIELDS
            )
        )
        if df is not None and len(df):
            frames.append(df.reset_index())
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True).rename(columns={"order_book_id": "contract"})
    x["date"] = pd.to_datetime(x["date"])
    return x.set_index(["contract", "date"]).sort_index()


def continuous(rq, guard, symbol: str, start: str, end: str) -> pd.DataFrame:
    out = {}
    for t in ("front_month", "next_month"):
        guard.tick()
        s = rc.retry(lambda tt=t: rq.futures.get_continuous_contracts(symbol, start, end, type=tt))
        if s is not None and len(s):
            s = s.copy()
            s.index = pd.to_datetime(s.index)
            out[t] = s.rename(t)
    if not out:
        return pd.DataFrame()
    return pd.concat(out.values(), axis=1).sort_index()


def roll_yield(rq, guard, symbol: str, start: str, end: str) -> pd.DataFrame:
    frames = []
    for t in ("main_sub", "near_main"):
        guard.tick()
        df = rc.retry(lambda tt=t: rq.futures.get_roll_yield(symbol, start_date=start, end_date=end, type=tt))
        if df is not None and len(df):
            x = df.reset_index()
            x["type"] = t
            frames.append(x)
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True)
    x["date"] = pd.to_datetime(x["date"])
    return x.sort_values(["date", "type"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="逗号分隔;默认全部商品品种")
    ap.add_argument("--start", default=rc.DEFAULT_START)
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument(
        "--skip", default="", help="逗号分隔要跳过的表:contracts,metadata,dominant,exchange,continuous,roll"
    )
    args = ap.parse_args()

    rq = rc.init()
    guard = rc.QuotaGuard(rq)
    uni = rc.load_universe()
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or rc.commodity_symbols(uni)
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    dm = None
    dm_path = rc.DATA_ROOT / "dominant_contracts" / "dominant.parquet"
    if dm_path.exists():
        dm = pd.read_parquet(dm_path)
        dm["date"] = pd.to_datetime(dm["date"])

    if "metadata" not in skip:
        meta = metadata(uni, rc.commodity_symbols(uni), args.start)
        rc.write_parquet(meta, rc.DATA_ROOT / "contracts_daily" / "metadata.parquet", index=False)
        print(f"metadata: {meta.shape}")

    try:
        for sym in syms:
            t0 = time.time()
            if "contracts" not in skip:
                out = rc.DATA_ROOT / "contracts_daily" / f"{sym}.parquet"
                if out.exists() and not args.force:
                    pass
                else:
                    df = contracts_daily(rq, guard, uni, sym, args.start, args.end)
                    rc.write_parquet(df, out)
                    print(f"{sym} contracts_daily {len(df)} 行 ({time.time() - t0:.0f}s)", flush=True)
            if "dominant" not in skip:
                out = rc.DATA_ROOT / "dominant_daily" / f"{sym}.parquet"
                if not out.exists() or args.force:
                    df = dominant_daily(rq, guard, sym, args.start, args.end, dm)
                    rc.write_parquet(df, out)
                    print(f"{sym} dominant_daily {len(df)} 行", flush=True)
            if "exchange" not in skip:
                out = rc.DATA_ROOT / "exchange_daily" / f"{sym}.parquet"
                if not out.exists() or args.force:
                    df = exchange_daily(rq, guard, uni, sym, args.start, args.end)
                    rc.write_parquet(df, out)
                    print(f"{sym} exchange_daily {len(df)} 行", flush=True)
            if "continuous" not in skip:
                out = rc.DATA_ROOT / "continuous" / f"{sym}.parquet"
                if not out.exists() or args.force:
                    df = continuous(rq, guard, sym, args.start, args.end)
                    rc.write_parquet(df, out)
                    print(f"{sym} continuous {len(df)} 行", flush=True)
            if "roll" not in skip:
                out = rc.DATA_ROOT / "roll_yield" / f"{sym}.parquet"
                if not out.exists() or args.force:
                    df = roll_yield(rq, guard, sym, args.start, args.end)
                    rc.write_parquet(df, out)
                    print(f"{sym} roll_yield {len(df)} 行", flush=True)
            rc.record(item=f"daily/{sym}", seconds=round(time.time() - t0, 1))
    except rc.QuotaExhausted as e:
        print(f"[配额] {e};已下载的文件保留,明天重跑本脚本续跑")
        return 3
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
