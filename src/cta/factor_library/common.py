"""Shared helpers for factor definitions: trading-day count, log returns, realized volatility, cross-sectional z-score.

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

Frame = pd.DataFrame


TRADING_DAYS = 243  # 中国期货市场每年约 243 个交易日(不含夜盘日切)


def log_returns(px: Frame) -> Frame:
    out: Frame = cast(Frame, np.log(px)).diff()
    return out


def realized_vol(px: Frame, window: int = 40, min_periods: int = 20) -> Frame:
    """年化已实现波动率(EWMA 也可,此处用简单滚动便于审计)。"""
    out: Frame = log_returns(px).rolling(window, min_periods=min_periods).std() * np.sqrt(TRADING_DAYS)
    return out


def zscore_xs(x: Frame, eligible: Frame) -> Frame:
    """每日横截面 z-score(只在可投品种内),clip ±2 再 /2 → [-1, 1]。"""
    r = x.where(eligible.reindex_like(x).fillna(False).astype(bool))
    z = r.sub(r.mean(axis=1), axis=0).div(r.std(axis=1).replace(0, np.nan), axis=0)
    out: Frame = (z.clip(-2, 2) / 2.0).where(x.notna())
    return out
