# src/cta/data: stage 1, data layer

Not to be confused with the top-level `data/` folder, which is the gitignored local data store.

## Contents

- `source.py`: `DataSource` protocol and `RicequantParquetSource` (proprietary vendor export in `data/ricecta/data`, 2016-01-04 → 2026-06-05; never commit it).
- `exchanges/`: SHFE, INE, CZCE, DCE downloaders and parsers, the append-only store (`base.Store`), trading calendar, settlement and fee parameters (`params`), `ExchangeSource` and `StitchedSource` (`source.py`). Each exchange module has a CLI: `python -m cta.data.exchanges.<shfe|ine|czce|dce|params> --help`.
- `continuous/roll.py`: dominant-contract selection, the T+1 contract (`sched_next`) and ratio back-adjusted prices (`adj_close`).

## Rules

- `stitched` (default): vendor rows up to the cutover 2026-06-05, exchange rows after. Official settlement prices, receipts and regulatory events come only from the exchange store. With `data.settle: official` a held contract-day without an official settle raises in `build_panels`; it never falls back to close.
- Dominant rule: vendor table up to the cutover; after it, the exchange `max_oi` rule. `oi_1.1x` (only with `--source exchange`) approximates the vendor table. Do not change the paper books' rule during the acceptance window (`docs/research/source_check.md`).
- `--exchange-root` and `--dominant-rule` apply only to `--source exchange`: stitched ignores `--exchange-root`, and other sources reject a non-default `--dominant-rule`.
- The store is append-only (`Store.write_day` refuses to overwrite). Raw downloads are cached under `<EX>/raw/`, and every re-ingest re-parses that cache. To fix an early intraday snapshot, delete the raw file and any parquet already written for that day, then re-ingest.
- After a parser fix: `czce reparse` / `dce reparse`, or `backfill --overwrite` for shfe/ine/params (czce and dce backfill have no `--overwrite`); then delete `quotes_all.{parquet,stamp}`, whose stamp does not notice a reparse. CZCE 2016–2025 quotes were built from annual zips without per-day raw files, so `czce reparse` skips them; rebuild those with `czce.ingest_annual(year, overwrite=True)`.
- `scripts/fetch_exchange_data.sh` backfills quotes and receipts (enough for the v0.3 baseline). Params, which regulatory events and `paper/v01r` need, come from `python -m cta.data.exchanges.params backfill`; positions need the `kinds` argument.
- Empty settlements: SHFE/INE quotes fill isolated gaps but raise `NotFinalError` (and delete their raw) above 5% of traded contracts; DCE quotes fail validation on any; CZCE drops those rows and writes the rest.
- Only the paper runner refuses today's data before 16:30 Beijing; the exchange CLIs have no time guard.
- DCE is fetched through the local Chrome DevTools proxy (`localhost:3456`). Never try to defeat its anti-bot challenge another way.
- Rolls switch only after the dominant candidate holds 3 days, and only forward in maturity. `adj_close` levels are rescaled by every later roll: compare returns, never levels.
