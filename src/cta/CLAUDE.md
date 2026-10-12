# src/cta: production

Everything the daily paper job, `cta.cli live` and `scripts/*.py` run. Research code lives in `research/` and never enters here by import.

## Stage order

1. `data/`: sources, exchange store, continuous contracts (roll).
2. Factor mining is research only: `research/cta_research/factor_mining/`.
3. `factor_library/`: the adopted factors the books trade.
4. `factor_combination/`: factor signals to target exposure.
5. `execution/`: sizing, fills and marking, and the drivers (backtest, live orders, paper books).
6. `analysis/`: read-only metrics, statistics, attribution, acceptance report.

`pipeline.py` wires 1 → 3 → 4 → 5 (`build_panels` → `compute_signals` → `run_backtest`); `execution/live` and `execution/paper` call the same functions as of a date. Each stage folder has its own CLAUDE.md.

## Rules

- Never import or write the name of the research package anywhere under `src/cta` (comments and docstrings included). The only exception is the lazy MSF import inside `pipeline._extra_factors_of`. `tests/test_boundaries.py` scans the raw text.
- Do not move `cli.py` (the daily job runs `-m cta.cli`), `pipeline.py` (boundary-test key), `config.py` or `instruments/specs.py` (their default paths are file-relative).
- Stage direction is enforced by `tests/test_stage_layout.py`: data, factor_library and factor_combination never import later stages or `pipeline`.
- Acceptance window to 2026-12-15: behaviour must stay bitwise identical. A refactor here needs the golden runs and the paper replay to match old code byte for byte (design log 29 describes both).
- Verify with `.venv/bin/python -m pytest -rs` from the repo root with local data, plus `.venv/bin/python -m cta.cli --help`.
