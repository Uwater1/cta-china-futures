"""Fundamental factor: level of exchange warehouse receipts relative to their own one-year history (design log 9).

Moved verbatim from cta/signals/core.py on 2026-10-12 (design log 29); numerics unchanged."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from cta.factor_library.common import zscore_xs

Frame = pd.DataFrame


def receipts_level(
    receipts: Frame, index: pd.DatetimeIndex, columns: list[str], eligible: Frame, window: int = 252
) -> Frame:
    """仓单水平信号(design_log 九 H-REC-L):−(log(1+注册仓单) 在自身 window 日窗口的分位 − 0.5) 的横截面 z。
    仓单高(可交割现货充裕)→ 做空;仓单低(逼仓风险)→ 做多。receipts 为 date × symbol 的注册仓单合计,当日收盘后公布。"""
    r = cast(Frame, np.log1p(receipts.reindex(index).ffill(limit=5).reindex(columns=columns)))
    pct = r.rolling(window, min_periods=window // 2).rank(pct=True)
    return zscore_xs(-(pct - 0.5), eligible)
