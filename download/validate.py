"""下载产物校验:逐表检查 schema 与基本不变量,任一项失败退出码非 0。

用法:
  .venv/bin/python download/validate.py            # 全量校验
  .venv/bin/python download/validate.py --quick    # 只查最近写入的文件与结构
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq_common as rc  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


def check_index(path: Path, names: list[str], min_rows: int = 1) -> pd.DataFrame:
    df = pd.read_parquet(path)
    check(list(df.index.names) == names, f"{path.name}: index {df.index.names} != {names}")
    check(len(df) >= min_rows, f"{path.name}: {len(df)} 行 < {min_rows}")
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    root = rc.DATA_ROOT

    uni_file = root / "universe" / "futures_instruments.parquet"
    if not uni_file.exists():
        print("还没有任何下载(universe 不存在);先运行 download_meta.py")
        return 1
    uni = pd.read_parquet(uni_file)
    check(
        {"order_book_id", "underlying_symbol", "exchange", "listed_date", "de_listed_date"}.issubset(
            uni.columns
        ),
        "universe 列缺失",
    )
    print(
        f"universe: {len(uni)} 合约, {uni['underlying_symbol'].nunique()} 品种, {uni['exchange'].nunique()} 交易所"
    )

    # dominant 表
    for name in ("dominant", "dominant2", "dominant3", "dominant_rule1"):
        p = root / "dominant_contracts" / f"{name}.parquet"
        if not p.exists():
            FAILS.append(f"缺 {p}")
            continue
        df = pd.read_parquet(p)
        check(list(df.columns) == ["date", "symbol", "contract"], f"{name}: 列 {list(df.columns)}")
        check(df["contract"].notna().all(), f"{name}: 有缺失合约")
    print("dominant_contracts: ok" if not FAILS else "dominant_contracts: 见失败列表")

    # 合约日线
    n_sym, n_rows = 0, 0
    need = {"open", "high", "low", "close", "volume", "open_interest"}
    for p in sorted((root / "contracts_daily").glob("*.parquet")):
        if p.stem == "metadata":
            continue
        df = check_index(p, ["contract", "date"])
        check(need.issubset(df.columns), f"{p.name}: 缺列 {need - set(df.columns)}")
        if len(df):
            check(bool((df["close"] > 0).all()), f"{p.name}: 存在非正价格")
            check(bool((df["volume"] >= 0).all()), f"{p.name}: 负成交量")
        n_sym += 1
        n_rows += len(df)
        if args.quick and n_sym >= 3:
            break
    print(f"contracts_daily: {n_sym} 个品种 {n_rows} 行")

    meta = root / "contracts_daily" / "metadata.parquet"
    if meta.exists():
        m = pd.read_parquet(meta)
        need = {
            "order_book_id",
            "symbol",
            "underlying_symbol",
            "exchange",
            "listed_date",
            "de_listed_date",
            "maturity_date",
            "margin_rate",
            "contract_multiplier",
        }
        check(need.issubset(m.columns), f"metadata 缺列 {need - set(m.columns)}")
        bad = (
            pd.to_datetime(m["maturity_date"], errors="coerce")
            < pd.to_datetime(m["listed_date"], errors="coerce")
        ).sum()
        check(int(bad) == 0, f"metadata: {bad} 行 maturity<listed")
    else:
        FAILS.append("缺 metadata.parquet")

    for name, cols in [
        ("dominant_daily", {"contract", "settlement", "prev_settlement", "limit_up", "limit_down"})
    ]:
        files = sorted((root / name).glob("*.parquet"))
        check(len(files) > 0, f"缺 {name}/")
        for p in files[: 3 if args.quick else len(files)]:
            df = check_index(p, ["date"])
            check(cols.issubset(df.columns), f"{name}/{p.name}: 缺列 {cols - set(df.columns)}")

    for name, cols in [
        ("exchange_daily", {"open", "close", "settlement", "prev_settlement", "open_interest"}),
        ("trading_parameters", {"long_margin_ratio", "short_margin_ratio", "open_commission"}),
    ]:
        files = sorted((root / name).glob("*.parquet"))
        check(len(files) > 0, f"缺 {name}/")
        for p in files[: 3 if args.quick else len(files)]:
            df = check_index(
                p, ["contract", "date"] if name == "exchange_daily" else ["contract", "trading_date"]
            )
            check(cols.issubset(df.columns), f"{name}/{p.name}: 缺列")

    for name, cols in [
        ("warehouse_stocks", {"date", "on_warrant"}),
        ("member_rank", {"trading_date", "rank_by", "member_name", "rank"}),
        ("continuous", {"front_month", "next_month"}),
    ]:
        files = sorted((root / name).glob("*.parquet"))
        check(len(files) > 0, f"缺 {name}/")
        for p in files[: 3 if args.quick else len(files)][:20]:
            df = pd.read_parquet(p)
            check(cols.issubset(df.columns), f"{name}/{p.name}: 缺列 {cols - set(df.columns)}")

    ry = sorted((root / "roll_yield").glob("*.parquet"))
    check(len(ry) > 0, "缺 roll_yield/")
    for p in ry[:3]:
        df = pd.read_parquet(p)
        check(
            {"type", "date", "from_contract", "to_contract", "yield"}.issubset(df.columns),
            f"roll_yield/{p.name}: 缺列",
        )

    # 5 分钟线抽样
    five = sorted((root / "futures_5minute").rglob("*.parquet"))
    print(f"futures_5minute: {len(five)} 个合约文件")
    for p in five[: 5 if args.quick else min(len(five), 30)]:
        df = check_index(p, ["datetime"])
        check(
            {
                "open",
                "high",
                "low",
                "close",
                "volume",
                "total_turnover",
                "open_interest",
                "trading_date",
            }.issubset(df.columns),
            f"5min {p.name}: 缺列",
        )
        if len(df):
            check(df.index.is_monotonic_increasing, f"5min {p.name}: 索引非单调")

    # 期权 / 宏观 / 现货 / 利率(有则查)
    oc = root / "options" / "contracts.parquet"
    if oc.exists():
        df = pd.read_parquet(oc)
        check(
            {"contract", "underlying", "strike", "option_type", "maturity_date"}.issubset(df.columns),
            "options/contracts 缺列",
        )
        print(f"options/contracts: {len(df)} 个合约")
    for p in sorted((root / "options" / "indicators").glob("*.parquet"))[:3]:
        df = pd.read_parquet(p)
        check({"maturity", "date", "skew"}.issubset(df.columns), f"options/indicators/{p.name}: 缺列")

    for rel, cols in [
        ("indices/commodity_indices.parquet", {"order_book_id", "date", "close"}),
        ("shibor/shibor.parquet", {"ON", "1M", "1Y"}),
        ("econ/macro_factors.parquet", {"factor", "info_date", "value"}),
        ("econ/money_supply.parquet", {"m0", "m1", "m2"}),
        ("econ/reserve_ratio.parquet", {"reserve_type", "effective_date"}),
        ("spot/sge_benchmark.parquet", {"order_book_id", "date", "morning", "noon"}),
    ]:
        p = root / rel
        if p.exists():
            df = pd.read_parquet(p)
            check(cols.issubset(df.columns), f"{rel}: 缺列 {cols - set(df.columns)}")

    if FAILS:
        print("\n校验失败:")
        for f in FAILS:
            print(" -", f)
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
