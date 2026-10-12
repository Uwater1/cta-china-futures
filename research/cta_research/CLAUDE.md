# research/cta_research: research code

May import production (`cta`); production never imports this package, except the lazy MSF plug-in in `cta.pipeline._extra_factors_of`.

- `factor_mining/`: stage 2, candidate factors, research signals and evaluators (see its CLAUDE.md).
- `altdata/`: alternative-data pipelines (rainfall, ENSO, news tone, exchange inventory, PM2.5, commodity options). Each writes `data/external/alt/<source>/` with a pre-registered availability day. Run with `python -m cta_research.altdata.<module>`.
- `legacy/engine_legacy.py`: the engine before the 2026-09-22 execution unification; only reproduces old reports.

## Rules

- Every new hypothesis gets a committed prereg (`docs/research/<topic>_prereg.md`, commit message `PREREG: …`) before any returns are computed, and counts as a trial in `docs/design_log.md`.
- Per-round scripts are in `research/scripts/` and write `results/<name>/` (gitignored) and `docs/research/<name>.md`. Full runs of the newer diagnostics cover the 2022–2026 window and count as trials; their smoke modes write to the same default outputs, so pass scratch paths. `quarterly_walkforward_diagnostic.py` and `adaptive_quarterly_v1.py` default to `--mode smoke`; a bare `quarterly_walkforward_diagnostic.py` run replaces `results/quarterly_walkforward/equity_B_S3.csv` (needed by `research/tests/test_adaptive_quarterly.py` and read by `adaptive_quarterly_v1.py`) with a 2022Q1–Q2 stub; `altdata/options/fundamental_signal_diagnostic.py` take `--smoke`.
- Hand-written text survives a rerun only inside `<!-- narrative-top/bottom -->` (the altdata/fundamental_signal/options diagnostics, `adaptive_quarterly_v1.py`) or `<!-- human:start/end -->` (`msf_demo.py` only; `ewmac_base.py history` writes empty human markers but overwrites them on rerun); every other generator rewrites its whole doc.
- Frozen evaluations are replayed from their commit, not from HEAD: the ewmac base trial (61) uses `research/scripts/ewmac_base.py` at commit 5626548 in its own worktree.
