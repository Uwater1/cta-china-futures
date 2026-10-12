"""Stage 4, factor combination: from factor signals to target exposure (fraction of equity).

No contracts or lots here; execution turns exposure into orders. See CLAUDE.md in this folder."""

from cta.factor_combination.portfolio import cap_gross_exposure, trade_buffer, vol_target_positions
from cta.factor_combination.weighting import combine, combine_tv, inverse_vol_weights, menu_masks

__all__ = [
    "cap_gross_exposure",
    "combine",
    "combine_tv",
    "inverse_vol_weights",
    "menu_masks",
    "trade_buffer",
    "vol_target_positions",
]
