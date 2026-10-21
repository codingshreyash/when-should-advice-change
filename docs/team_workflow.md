# Team workflow

Everything lives in this repository. Work on a branch, open a pull request into `main`,
and merge once the checks below pass. Never commit straight to `main`.

## Who works where

| Person | Role | Files |
|---|---|---|
| Insiah | scenarios and variants | `data/scenarios/` (the pilot file is edited directly; `career_v2.jsonl` is generated from `scripts/data/build_career_v2.py`), `scripts/data/add_irrelevant_updates.py`, `scripts/data/add_subthreshold_updates.py`, `scripts/data/build_threshold_sweep.py` |
| Haiden | blind labels, agreement, harness | `data/labeling/` sheets (made by `scripts/data/labeling.py make`), `scripts/analysis/` |
| Greg | chat baselines, delivery scoring | `scripts/run/run_chat.py`, `scripts/run/run_pushback.py`, `results/` from Claude runs |
| Shreyash | decision-only pipeline, adapter comparison, writing | `scripts/run/run_nimble.py`, `scripts/run/brev_setup.sh`, `report/`, `docs/findings.md` |

Haiden and Greg also label scenarios they did not write (see [labeling.md](labeling.md)).

## Branches and commits

- Branch names: `<name>/<topic>`, e.g. `insiah/harder-sweep`, `haiden/blind-labels`.
- Commit messages: imperative and specific, e.g. "Add six implied-threshold sweep
  scenarios", not "updates".
- One pull request per change; keep data, code and write-up changes in separate commits.

## Before you open a pull request

- `python3 scripts/data/validate_scenarios.py data/scenarios/career_pilot.jsonl data/scenarios/career_v2.jsonl` prints OK.
- If you changed a builder, rerun it and commit the regenerated file in the same pull request.
- If you changed an analysis script, rerun it and update the matching file in `results/summaries/`.
- Never change a results file by hand. Runners refuse to overwrite existing results
  unless `OVERWRITE=1`; use `RESUME=1` to finish an interrupted run.

## Private files

- Labeling answer keys (`data/labeling/*_key.csv`) are git-ignored. Keep them off GitHub until labeling is scored.
- Filled-in labeling sheets stay with each labeler until both are done.
- API keys go in environment variables (`CS1684_ANTHROPIC_KEY`), never in files.
