# src/cta/execution/paper: paper books (code)

The books themselves live in the top-level `paper/` folder; this folder is the code that steps them.

- Five books, each tied to one config: `paper/v01` → `strategy.yaml` (the only book that ingests data; runs first), `paper/v03` → `strategy_v03.yaml` (champion), `paper/v03p`, `paper/v01r`, `paper/v05` → `strategy_v03p/v01r/v05.yaml`. The CLI does not check the pairing: always pass `--book` with its `--config`.
- A step stages orders, fills, equity, positions and state in `<book>/.txn/<date>/` and promotes them with `os.replace`, `state.json` last; `log/<date>.json` and `FAILED.json` are written directly. On failure it writes `FAILED.json` and leaves state unchanged; rerunning `catchup` is idempotent. A settled day cannot be recomputed. Never hand-edit `state.json`.
- A `--book` without `state.json` is refused unless `--init` (otherwise a fresh 3M book would be created). Never point `--book` at `paper/` or `paper/log/`.
- Side-effect-free check: `paper step --date <settled day> --no-ingest --book … --config …` → "already settled".
- `scripts/paper_daily.sh` (launchd, `deploy/com.cta.paper.plist`) commits whatever is staged and pushes `HEAD`. Keep that checkout on `main` with nothing staged; do branch work in a worktree; recover failed days only in that checkout (`docs/deployment.md`, 失败语义与恢复).
- `book.DEFAULT_DIR` is file-relative (`parents[4]` → `<repo>/paper/v01`); `tests/test_stage_layout.py` checks it.
- Trading days are Mon–Fri minus `configs/holidays.csv`; an unlisted exchange holiday fails the step by design. The 2027 holidays go in only between 2026-12-16 and 2026-12-31, even if announced earlier (design log 30.3: adding them moves exchange-rule maturities, then `days_to_next` and carry, inside the acceptance window; missing them fails the 2027-01-01 run). Later years: add when announced.
- DCE fetch timeouts (2026-09-23, 10-08; on 10-08 the proxy was not attached to Chrome) fail every book holding DCE contracts at `settle`.
