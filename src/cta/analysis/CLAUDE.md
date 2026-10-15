# src/cta/analysis: stage 6, read-only analysis

Nothing here changes positions or orders.

- `metrics.py`: `perf_stats`, `drawdown`, `yearly`. Monthly Sharpe comes from month-end resampling, so a slice that starts on the first trading day of a month drops that month: start an out-of-sample slice at 2021-12-31, not 2022-01-04 (design log 27).
- `stats.py`: Newey–West mean, block bootstrap, `paired_summary` (challenger − champion; the day before `start` is used as the denominator).
- `attribution.py`, `loo.py`: per-symbol net attribution, breadth, leave-one-out reruns (`scripts/portfolio_diagnostics.py`).
- `paper_acceptance.py`: the acceptance report for the paper books (`scripts/paper_acceptance.py`, protocol `configs/paper_protocol.yaml`; sections 0–10). Read-only, but besides `paper/` it reads git history (commits that added `FAILED.json`; `git diff` between snapshot shas over `BOOK_CODE_PATHS` to tell book-affecting code changes from doc or paper-data commits) and the exchange daily quote files for slippage (`TURNOVER_UNIT`: SHFE/INE turnover is in 万元). `--strict` covers equity and position reconciliation (design log 31).
- `report.py`: report figures and tables (`cta.cli report`). Keep `matplotlib.use("Agg")` before the pyplot import.
