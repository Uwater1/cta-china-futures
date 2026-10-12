"""Trend factor: time-series momentum (Moskowitz, Ooi and Pedersen 2012).

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from cta.factor_library.common import TRADING_DAYS

Frame = pd.DataFrame


def tsmom(px: Frame, lookbacks: tuple[int, ...] = (21, 63, 126, 252), vol: Frame | None = None) -> Frame:
    """时序动量:各回看期收益的符号(或波动率标准化后的 clip),对**当时可得**的回看期等权平均。
    Moskowitz-Ooi-Pedersen (2012)。vol 给定时用 收益/(vol×sqrt(h/243)) 再 clip 到 [-2,2] 后除 2,否则用符号。"""
    num = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    den = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for h in lookbacks:
        r = np.log(px / px.shift(h))
        s: Frame = (
            cast(Frame, np.sign(r))
            if vol is None
            else (r / (vol * np.sqrt(h / TRADING_DAYS))).clip(-2, 2) / 2.0
        )
        num = num + s.fillna(0.0)
        den = den + s.notna().astype(float)
    out: Frame = num / den.where(den > 0)
    return out.where(px.notna())
