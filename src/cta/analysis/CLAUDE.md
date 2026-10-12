# src/cta/analysis: stage 6, read-only analysis

Nothing here changes positions or orders.

- `metrics.py`: `perf_stats`, `drawdown`, `yearly`. Monthly Sharpe comes from month-end resampling, so a slice that starts on the first trading day of a month drops that month: start an out-of-sample slice at 2021-12-31, not 2022-01-04 (design log 27).
- `stats.py`: Newey–West mean, block bootstrap, `paired_summary` (challenger − champion; the day before `start` is used as the denominator).
- `attribution.py`, `loo.py`: per-symbol net attribution, breadth, leave-one-out reruns (`scripts/portfolio_diagnostics.py`).
- `paper_acceptance.py`: the acceptance report for the paper books (`scripts/paper_acceptance.py`, protocol `configs/paper_protocol.yaml`).
- `report.py`: report figures and tables (`cta.cli report`). Keep `matplotlib.use("Agg")` before the pyplot import.
