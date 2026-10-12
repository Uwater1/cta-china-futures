"""Combining factor signals into one signal per symbol: sector/symbol menus, equal or inverse-vol weights, sqrt(n) normalization.

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

from functools import reduce

import numpy as np
import pandas as pd

Frame = pd.DataFrame


def menu_masks(
    factors: list[str],
    symbols: list[str],
    sector_of: dict[str, str],
    sector_menu: dict[str, list[str]],
    symbol_menu: dict[str, list[str]],
) -> dict[str, pd.Series[bool]]:
    """每个因子一条 品种 → 是否允许 的布尔序列。品种级覆盖优先;板块未列出 = 全部允许(design_log 十二 12.2)。"""
    out: dict[str, pd.Series[bool]] = {}
    for f in factors:
        allowed = []
        for s in symbols:
            if s in symbol_menu:
                allowed.append(f in symbol_menu[s])
            elif sector_of.get(s) in sector_menu:
                allowed.append(f in sector_menu[sector_of[s]])
            else:
                allowed.append(True)
        out[f] = pd.Series(allowed, index=symbols, dtype=bool)
    return out


def inverse_vol_weights(
    signals: dict[str, Frame], window: int = 252, min_periods: int = 126
) -> dict[str, pd.Series[float]]:
    """因子权重 w_f(t) ∝ 1/σ_f(t),σ_f = 该因子信号在全部品种上池化的滚动均方根(信号本身近似零均值),取 t−1 及之前。
    只用信号的离散度,不用收益,因此不可能拟合历史收益(design_log 十二 12.3)。"""
    inv: dict[str, pd.Series[float]] = {}
    for f, s in signals.items():
        ms = (s**2).mean(axis=1)  # 每日横截面均方
        sigma = np.sqrt(ms.rolling(window, min_periods=min_periods).mean()).shift(1)
        inv[f] = 1.0 / sigma.replace(0, np.nan)
    total = reduce(lambda a, b: a.fillna(0.0) + b.fillna(0.0), inv.values())
    return {f: (w / total.where(total > 0)) for f, w in inv.items()}


def combine(signals: dict[str, Frame], weights: dict[str, float] | None = None, sqrt_n: bool = True) -> Frame:
    """等权(或给定权重)合成,缺失的信号不参与分母。
    sqrt_n:按活跃因子数归一 —— k 个弱相关标准化信号的平均值幅度约为单个的 1/√k,若不归一,因子少的品种会被机械放大
    (design_log 12.5 记录的缺陷,13.2 修正)。合成 = mean(s_f) × √(n_active / n_max),n_max = 因子总数;全因子可用的品种不受影响。"""
    names = list(signals)
    w = {k: 1.0 for k in names} if weights is None else weights
    num = reduce(lambda a, b: a + b, [signals[k].fillna(0.0) * w[k] for k in names])
    den = reduce(lambda a, b: a + b, [signals[k].notna().astype(float) * w[k] for k in names])
    mean: Frame = num / den.where(den > 0)
    if sqrt_n and len(names) > 1:
        n_active = reduce(lambda a, b: a + b, [signals[k].notna().astype(float) for k in names])
        mean = mean * np.sqrt(n_active / float(len(names)))
    out: Frame = mean.clip(-1, 1)
    return out


def combine_tv(signals: dict[str, Frame], weights: dict[str, pd.Series[float]]) -> Frame:
    """时变权重合成:Σ w_f(t)·s_f / Σ w_f(t)·1[s_f 非空];某日权重缺失时该因子不参与。"""
    names = list(signals)
    num = reduce(
        lambda a, b: a + b, [signals[k].fillna(0.0).mul(weights[k].fillna(0.0), axis=0) for k in names]
    )
    den = reduce(
        lambda a, b: a + b,
        [signals[k].notna().astype(float).mul(weights[k].fillna(0.0), axis=0) for k in names],
    )
    out: Frame = (num / den.where(den > 0)).clip(-1, 1)
    return out
