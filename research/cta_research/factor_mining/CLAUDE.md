# research/cta_research/factor_mining: stage 2, factor mining

Where candidate factors are defined and tested. Nothing here is traded; adopted factors are re-implemented in `src/cta/factor_library/`.

## Contents

- `candidates/`: the candidate catalogue (`catalog.py`, one definition per id, windows fixed; `REGISTRY` with `FactorInputs` and `standardize` in `base.py`), new-data factors (`newdata.py`) and the multi-source composite MSF (`composite.py`, plugged into production only through `signals.weights: {msf: …}`).
- `signals/`: point-in-time builders for fundamental (PMI etc.), alternative-data and commodity-option signals.
- `evaluation/`: the quick factor evaluator (`evaluate.py`), the three-arm candidate evaluator (`candidate_eval.py`: candidate alone / production baseline / 50-50 blend, same engine and costs), walk-forward and quarterly adaptive tools.

## Rules

- Importing anything under `candidates/` runs `candidates/__init__`, which registers every catalogue factor; `register()` raises on a duplicate, so never import the catalogue under a second name or add compatibility aliases.
- Keep `factor_mining/__init__.py` import-free (the subpackages import each other).
- `candidate_eval.build_context` raises if the rebuilt baseline does not match production, but stores the reference-equity match in `baseline_matches_reference` without raising: stop on False yourself, and treat None as a failed precondition. Its R0–R14 verdict is mechanical; preregs decide what it means.
- Release-based factors must pass `target_rule="on_or_after"` to `signals.fundamental_signals.releases_to_daily`; the default `"legacy"` books weekend releases on the previous Friday (night-session products then fill before publication) and only reproduces trials 50/51.
- A factor whose sign comes out opposite to its preregistered direction is dropped, never flipped. Only `factor_{screen,combo,newdata,reg,global,spotbasis}.py` and `exec_trials.py` in `research/scripts/` gate the 2022–2026 window behind `--confirm-holdout`.
