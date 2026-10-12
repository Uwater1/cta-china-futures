"""Term-structure factor: annualized roll yield (carry) and its bounded signal (Koijen et al. 2018).

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

Frame = pd.DataFrame


def carry(near_px: Frame, next_px: Frame, days_between: Frame) -> Frame:
    """期限结构展期收益(年化):(近月 - 次近月)/次近月 × 365/两合约交割间隔天数。
    正值 = 现货升水(backwardation)= 做多有展期收益。Koijen-Moskowitz-Pedersen-Vrugt (2018)。"""
    raw: Frame = (near_px / next_px - 1.0) * (365.0 / days_between.clip(lower=15))
    return raw


def carry_signal(carry_ann: Frame, scale: float = 0.20) -> Frame:
    """把年化展期收益压到 [-1,1]:tanh(carry/scale),scale=20% 年化时 carry=20% 对应约 0.76 的强度。"""
    out = cast(Frame, np.tanh(carry_ann / scale))
    return out
