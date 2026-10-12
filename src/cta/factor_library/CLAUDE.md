# src/cta/factor_library: stage 3, adopted factors

Pure functions on date × symbol frames. The signals (`tsmom`, `carry_signal`, `receipts_level`) use positive = long with strength in [−1, 1]; `carry` is the raw annualized roll yield, `realized_vol` is annualized volatility, and `gates.py` returns masks and multipliers. Back-adjusted prices are read only through returns or ratios.

## Status (shipped configs)

| Factor | Module | Used by |
|---|---|---|
| `tsmom` | `trend.py` (its `realized_vol` input is in `common.py`) | all five books |
| `carry`, `carry_signal` | `term_structure.py` | all five books |
| `receipts_level` | `warehouse_receipts.py` | v03 (champion), v03p, v05 |
| `reg_overlay_mask` | `gates.py` | v01r only (`signals.reg_overlay.enabled`) |
| `large_tick_mask` | `gates.py` | implemented, off in every shipped config (`signals.tick_filter`) |

Candidates that were tested and not adopted live in `research/cta_research/factor_mining/candidates/` and `factor_mining/signals/`, and are recorded in `docs/design_log.md` (whose trial count, 61 so far, also includes adopted factors and non-factor trials).

## How a candidate gets here

Pre-register it (`docs/research/<topic>_prereg.md`), pass its adoption rule, record the adoption in the design log, bump the config version, then re-implement it here. Never import it from research. During the acceptance window (to 2026-12-15) nothing is added.

## Rules

- Point in time: a value at date T may use only data available at T close. Add a truncation test for every new factor (cut at T; nothing ≤ T may change).
- These modules import nothing from other stages (`tests/test_stage_layout.py`).
- Function bodies were moved verbatim from `cta/signals/core.py` on 2026-10-12; keep numerics bitwise identical.
