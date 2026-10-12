# src/cta/factor_combination: stage 4, from signals to target exposure

Works in exposure space (fraction of equity). No contracts, no lots; `execution/` turns exposure into orders.

## Contents

- `weighting.py`: `combine` (NaN-aware weighted mean × √(n_active / n_max), clipped to [−1, 1]); `inverse_vol_weights` and `combine_tv` (used when `factor_weighting: inverse_vol`); `menu_masks` (`sector_menu` / `symbol_menu`). Inverse-vol weights and menus are off in every shipped config.
- `portfolio.py`: `vol_target_positions` (risk parity on each symbol's vol, then scale the portfolio to the target using the covariance of the last `vol_window` days), `cap_gross_exposure`, `trade_buffer` (buffers one row against the previous one, band `portfolio.exposure_buffer`; the stateful row-by-row loop is in `pipeline.compute_signals`).

## Rules

- Summation order is part of the output. `pipeline.compute_signals` builds `parts` in the order tsmom, carry, receipts_level, then extra factors in config order; for books with three or more factors (v03, v03p, v05) reordering can change the last bits of the combined signal and break bitwise identity with those paper books. Keep the order.
- The buffer loop in `pipeline.compute_signals` runs from the first day; its state depends on the whole history, so never start it mid-series when comparing runs.
- Currently imports only `factor_library.common`; `tests/test_stage_layout.py` forbids imports of `cta.data`, `cta.execution`, `cta.analysis`, `cta.pipeline` and `cta.cli`.
