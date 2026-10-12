"""Config-gated masks applied to factors: large-tick filter and regulatory-event overlay.

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

import pandas as pd

Frame = pd.DataFrame


def large_tick_mask(
    close: Frame,
    roll: Frame,
    ticks: pd.Series[float],
    eligible: Frame,
    window: int = 336,
    top_quantile: float = 0.5,
) -> Frame:
    """跳价占日波动比例 ρ̄ = tick / EWMA_window(|Δclose|)(换月日的 Δ 剔除),每月末在可投品种内排名;
    排名前 top_quantile 的品种在**下一个月**为 True。月末排名只用当月及以前的数据,无前视。"""
    dp = close.diff().where(~roll.astype(bool))
    mad = dp.abs().ewm(span=window, adjust=False, min_periods=window // 5).mean()
    rho = mad.rdiv(ticks, axis=1)  # tick / mad
    rho = rho.where(eligible.reindex_like(rho).fillna(False).astype(bool))
    month = pd.DatetimeIndex(rho.index).to_period("M")
    month_end = rho.groupby(month).tail(1)
    rank = month_end.rank(axis=1, ascending=False, pct=True)  # 1/N = 最大跳价
    flag = rank <= top_quantile
    # 月末标记 → 下个月每天生效
    flag.index = pd.DatetimeIndex(flag.index) + pd.Timedelta(days=1)
    out: Frame = (
        flag.reindex(rho.index.union(flag.index)).ffill().reindex(rho.index).fillna(False).astype(bool)
    )
    return out


def reg_overlay_mask(
    events: Frame, index: pd.DatetimeIndex, columns: list[str], window: int = 21, scale: float = 0.5
) -> Frame:
    """监管事件覆盖层的乘数矩阵(design_log 13.6):事件日 D(D 收盘后可见)之后的 window 个交易日,该品种为 scale,其余为 1。
    只用 param ∈ {margin, fee}、direction == up、reason != holiday 的事件。"""
    mask = pd.DataFrame(1.0, index=index, columns=columns)
    if events is None or events.empty:
        return mask
    ev = events.copy()
    ev = ev[ev["param"].isin(["margin", "fee"]) & (ev["direction"] == "up") & (ev["reason"] != "holiday")]
    ev["event_date"] = pd.to_datetime(ev["event_date"])
    for _, r in ev.iterrows():
        if r["symbol"] not in columns:
            continue
        i = int(index.searchsorted(r["event_date"], side="right"))
        if i < len(index):
            mask.iloc[i : i + window, columns.index(str(r["symbol"]))] = scale
    return mask
