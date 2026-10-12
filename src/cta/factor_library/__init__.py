"""Stage 3, factor library: the adopted factor definitions the production books trade.

Pure functions on date x symbol frames. Sign convention: positive = long; strength in [-1, 1].
Price inputs are ratio back-adjusted continuous prices, used only for returns; sizing uses real contract prices.
See CLAUDE.md in this folder for the status of each factor and how a candidate gets here."""

from cta.factor_library.common import TRADING_DAYS, log_returns, realized_vol, zscore_xs
from cta.factor_library.gates import large_tick_mask, reg_overlay_mask
from cta.factor_library.term_structure import carry, carry_signal
from cta.factor_library.trend import tsmom
from cta.factor_library.warehouse_receipts import receipts_level

__all__ = [
    "TRADING_DAYS",
    "carry",
    "carry_signal",
    "large_tick_mask",
    "log_returns",
    "realized_vol",
    "receipts_level",
    "reg_overlay_mask",
    "tsmom",
    "zscore_xs",
]
