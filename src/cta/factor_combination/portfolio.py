"""From combined signal to target exposure: volatility targeting, gross-exposure cap, exposure buffer.

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cta.factor_library.common import TRADING_DAYS, log_returns

Frame = pd.DataFrame


def vol_target_positions(
    signal: Frame,
    vol: Frame,
    px: Frame,
    target_vol: float = 0.10,
    window: int = 60,
    max_leverage_per_symbol: float = 1.0,
    update: str = "daily",
) -> Frame:
    """信号 -> 占组合资本的名义暴露比例。
    第一步 风险平价雏形:w_i ∝ s_i / σ_i(每单位信号承担相同风险);
    第二步 事前组合波动缩放:用最近 window 日收益的协方差算 σ_p = sqrt(wᵀΣw),整体乘 target_vol/σ_p;
    最后 单品种名义上限。相比"除以品种数"的写法,这里正确处理了分散化(N 个不相关头寸的组合波动是 σ/√N)。"""
    raw: Frame = (signal / vol.replace(0, np.nan)).fillna(0.0)
    rets = log_returns(px)
    k = pd.Series(np.nan, index=raw.index, dtype=float)
    cols = list(raw.columns)
    r_np = rets[cols].to_numpy(dtype=float)
    w_np = raw[cols].to_numpy(dtype=float)
    for i in range(len(raw)):
        if i < window:
            continue
        w = w_np[i]
        if not np.any(w):
            continue
        block = r_np[i - window + 1 : i + 1]
        ok = ~np.isnan(block).any(axis=0)
        wv = np.where(ok, w, 0.0)
        cov = np.cov(np.nan_to_num(block[:, ok]).T) if ok.sum() > 1 else np.array([[np.nanvar(block[:, ok])]])
        var = float(wv[ok] @ np.atleast_2d(cov) @ wv[ok]) * TRADING_DAYS
        if var > 0:
            k.iloc[i] = target_vol / np.sqrt(var)
    if update == "weekly":
        # 只在每周第一个交易日更新缩放系数,其余日子沿用(减少由 k 抖动带来的换手)
        wk = pd.Series(pd.DatetimeIndex(raw.index).to_period("W").astype(str), index=raw.index)
        first_of_week = wk != wk.shift(1)
        k = k.where(first_of_week).ffill()
    scaled: Frame = raw.mul(k, axis=0)
    return scaled.clip(-max_leverage_per_symbol, max_leverage_per_symbol)


def cap_gross_exposure(w: Frame, max_gross: float) -> Frame:
    """组合总名义暴露 Σ|w_i| 超过 max_gross 时,整行等比缩减到上限(只缩不放)。"""
    gross = w.abs().sum(axis=1)
    k = (max_gross / gross).clip(upper=1.0).where(gross > 0, 1.0)
    out: Frame = w.mul(k, axis=0)
    return out


def trade_buffer(target: pd.Series[float], current: pd.Series[float], band: float = 0.2) -> pd.Series[float]:
    """交易缓冲:目标与当前的差小于 band × |目标| 时不交易。降低换手,对信号价值几乎无损。"""
    cur = current.reindex(target.index).fillna(0.0)
    diff = target - cur
    thresh = band * target.abs()
    out: pd.Series[float] = target.where(diff.abs() > thresh, cur)
    return out
