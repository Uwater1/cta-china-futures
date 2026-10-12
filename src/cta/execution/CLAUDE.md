# src/cta/execution: stage 5, execution layer

Shared by the backtest, the daily order generator and the paper books, so all three trade the same way.

## Sub-layers

1. `plan.py`, sizing: target exposure → whole lots at the T close of the contract held on T+1 → proportional margin cap → `lot_band`. Full closes are never banded.
2. `ledger.py`, fills and marking: absolute targets; fill = T+1 open ± slippage ticks plus fees; roll legs fill together or not at all; legs are pre-checked for missing quotes, empty opens and limit-locks; unfilled targets are not carried over; marking at each contract's official settle (engine non-strict, paper strict).
3. Drivers:
   - `backtest/engine.py`: historical replay.
   - `live/orders.py`: orders as of a date, with an input snapshot (`snapshot.json`).
   - `paper/`: the paper books and the daily step (see `paper/CLAUDE.md`).

## Rules

- Timing: signals at T close, fills at the T+1 open, which for night-session products is calendar-T 21:00. Check any data published after 15:00 against that.
- `tests/test_paths_agree.py` checks on 29 real days that the engine and an as-of loop (`generate_orders` → `ledger.execute_day` → `ledger.mark`) hold identical lots and equal equity (to within 1e-6 CNY). It does not run `PaperBook`; changes to `paper/` need the paper replay check (design log 29).
- `execution.fill` in the config schema has no effect but is part of the config digest; leave it.
