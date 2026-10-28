# Preregistration amendment 1: decision-procedure experiment

**Date:** 2026-10-28. **Status:** made before any model run of this experiment. No labels,
no technical pilot and no confirmatory run exist. `results/warranted_revision/` has no
decision-procedure run directory, and neither `PROJECT_LEDGER.md` nor `RUN_LOG.md` records one.
No change below responds to model output, because none exists.

Source of the defects: `docs/overnight/03_IMPLEMENTATION_AUDIT.md` (findings 1, 4, 5, 6).
The changes were made by an unattended overnight pass (04). **The PI has not reviewed them yet.**
The PI should confirm item 1 or revert it before labelling begins.

**Unchanged:** the primary contrast (D − A on Δ), the arms, stimuli, prompts, configs,
thresholds (15 primary scenarios, SESOI 0.10), the eligibility rules, the §7 validity gates,
the Holm families, the decision conditions and the budget.

## Changes to locked files

The only locked file that changed is
`research/warranted_revision/src/warranted_revision/decision_procedure_analysis.py`.

1. **NOT EVALUABLE outcome (§4, §8 wording).** Pass 03 recommended this as amendment A1.
   - **Before:** with fewer than 15 primary-eligible scenarios, or fewer than 15 paired primary
     scenarios, the code returned `decision: "NULL", kind: "not evaluable"`, and still wrote
     a primary estimate, CI and p-value.
   - **Now:** it returns `decision: "NOT EVALUABLE"` with the statement "the primary contrast
     was not evaluated; this is not evidence for or against an adapter effect". No primary
     estimate, CI or p-value is computed or written (`primary: {"evaluated": false}`).
   - **Why:** both NULL kinds in §8 are statements about a CI. With too few scenarios there
     is no CI, so the label "NULL" invites a reading of no effect.
   - **Labels-only check:** a new `--eligibility-only --labels ...` mode gives the same
     outcome from the labels alone, so it can be checked before any launch. Using it is not
     yet enforced before launch; that part of A1/A2 is left to the PI.
   - The 15-scenario threshold, the "no relabelling, no new items" rule and the precedence of
     UNINTERPRETABLE are unchanged.
2. **Label provenance (§4).** Finding 1: draft labels were accepted as blind labels.
   - **Now:** the analysis refuses any label file under `data/scenarios/` or `data/derived/`,
     and any row that lacks the provenance `scripts/data/labeling.py score` now writes:
     `label_source: "blind"`, two different labeler ids and two different sheet sha256s.
   - The sha256 of each label file is written into `analysis.json` (`label_sha256`).
3. **Duplicate rows (finding 6).** A repeated (arm, scenario, sample, variant) row used to
   overwrite the earlier one silently. It now raises an error.
4. **Completeness reported (finding 5, partly).** `analysis.json` now records the planned
   calls, the rows present per arm, and whether the two match.
   - This is a report only. The §7 gates and the decision are unchanged.
   - Making completeness a validity gate (pass 03's A3) is left to the PI.

## Not a locked file, changed alongside

`scripts/data/labeling.py score` now:
- requires two labeler ids;
- refuses the same sheet twice, identical sheets, incomplete or invalid sheets, sheets with a
  variant/key/reference/draft column, and sheets whose labels equal the draft labels on every
  row;
- writes the provenance above into the blind file.

## Re-lock

The lock was regenerated with
`PYTHONPATH=research/warranted_revision/src python3 -m warranted_revision.decision_procedure lock --write`.
Only the hash of `decision_procedure_analysis.py` changed. Previous hash:
`137db7d69a1db9c12fc169eb2aa3568b0dae6725bd610ac8f89a644c2ca68213`.
The new hash is in `research/warranted_revision/configs/decision_procedure_lock.json`.
