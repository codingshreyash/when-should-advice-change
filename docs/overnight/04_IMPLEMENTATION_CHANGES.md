# Overnight pass 04: implementation changes (infrastructure and validity only)

Source: `docs/overnight/03_IMPLEMENTATION_AUDIT.md`. No model, GPU, Brev or API call was made.
**No human labels exist**, and this pass created none. The synthetic label files in the tests
are the scenario author's drafts, or rule-filled sheets, given fake provenance. They exercise
the code only.

One locked file changed (`decision_procedure_analysis.py`). It is covered by
`docs/PREREG_AMENDMENT_1.md`, dated 2026-10-28 and made before any model run, and the lock was
regenerated with `lock --write`. In the lock file only that file's hash changed (`137db7d6…` →
`6b9525d3…`). **The PI has not reviewed the amendment.**

## Changes made

| # | file | what changed | why (pass 03) | covering test |
|---|---|---|---|---|
| 1 | `scripts/data/labeling.py` | `score` now requires `--labeler-a/--labeler-b` (non-empty, different). It refuses, writing nothing, when: the same file is given twice; the two sheets have identical bytes; a sheet has a column such as `reference_variant` (any non-sheet column whose name contains variant, key, reference, draft or expected); a sheet is incomplete (a key row is missing or blank, a label is not an option, or a row is not in the key); or a sheet's labels equal the drafts on every row. The refusal messages are neutral. It prints each sheet's agreement with the drafts as a diagnostic. Each output row gets `label_source: "blind"` and `label_provenance` (labeler ids, sha256 of both sheets, the key and the scenario file). | Findings 2 and 12. Check 2 had scored one draft-filled sheet passed twice as `ALL 70 1.00 1.00`. | `tests/test_labeling.py` (all 4 tests) |
| 2 | `decision_procedure_analysis.py` (locked) | `load_labels` raises `LabelError` for files under `data/scenarios/` or `data/derived/`, and for rows without `label_source: "blind"`, two different labeler ids and two different sheet sha256s. `analysis.json` records `label_sha256` for each label file. | Finding 1. The draft scenario files were accepted as blind labels. | `test_analysis_refuses_labels_without_blind_provenance`, `test_analysis_records_label_hashes_and_completeness`, `test_score_writes_provenance_the_analysis_accepts` |
| 3 | same | When too few scenarios are eligible, the decision is `NOT EVALUABLE` (with the statement "…not evidence for or against an adapter effect") instead of `NULL / not evaluable`. In that case no primary estimate, CI, p or `career_v2_only` block is computed or written, in either the main or the sensitivity block. New `--eligibility-only --labels …` mode gives the eligible counts, and NOT EVALUABLE where it applies, from the labels alone. | Finding 4. Pass 03 recommended A1. | `test_too_few_eligible_scenarios_is_not_evaluable_and_reports_no_estimate`, `test_analysis_null_and_invalid_generative_arm` |
| 4 | same | `index` raises on a repeated (arm, id, sample, variant). It used to overwrite silently. | Finding 6 | `test_duplicate_rows_are_an_error` |
| 5 | same | `analysis.json` gains `completeness`: planned calls (from the manifest), rows present, rows per arm and `matches_plan`. This is a report only; the gates and the decision are unchanged. | Finding 5, logging part only | `test_analysis_records_label_hashes_and_completeness` |
| 6 | `tests/test_decision_procedure.py` | The `labels_file` fixture now writes fake provenance and can omit it. The `decide` assertion expects `NOT EVALUABLE`. | Needed by 2–3 | same tests |
| 7 | `configs/decision_procedure_lock.json` | Re-locked | Required after 2–5 | `test_configs_lock_and_call_counts` |
| 8 | `docs/PREREG_AMENDMENT_1.md` | New: dated, pre-run; lists items 2–5 and their reasons | Rule for locked files | — |
| 9 | `docs/overnight/labeling_packet/` | Byte-for-byte copies of the two blank sheets from `data/labeling/` (70 and 140 rows, 0 filled, columns `row_id, prompt, question, options, your_label, why`) and `INSTRUCTIONS.md`, based on `docs/labeling.md`. It includes a no-repository/no-model-output attestation (finding 13). A scan found no variant names, keys, scenario ids or draft labels. The word "pressure" appears in prompt text only ("high blood pressure"). | Permitted packet | Manual scan, run in this pass |

Spot check: `decision_procedure_analysis --eligibility-only --labels data/scenarios/career_pilot.jsonl`
now fails with `LabelError: … scenario and derived files hold draft labels, not blind labels`.

## Changes considered and not made

- **Primary contrast:** not touched. This is the PI's decision.
- **Labels required and locked before `run`/pilot/job; label hashes checked against the
  lock** (findings 3 and 11, A2). This changes the §9 order enforcement and the job script.
  Until labels exist it would also block the technical pilot, so the PI should decide.
  `run()` still has no label check.
- **Completeness as a validity gate** (finding 5, A3). It would change the §7 gates, which is
  not permitted in this pass. It is reported only (item 5). The on-box `gate` already fails
  the run when `actual_calls != planned_calls`.
- **Fixed Holm families of 4 and 6 with missing p = 1** (finding 7, A4). The preregistration
  is ambiguous, so this needs a PI decision.
- **$5 decision-procedure cap read from the ledger; choice of the confirmatory cap**
  (findings 8 and 9, A5). These are budget and threshold decisions.
- **Adding job scripts, controller, `gpu_guard.py`, `labeling.py` and the blind files to
  `LOCKED`; the controller checking the lock's sha256** (finding 10, A6). `check_lock` runs
  on the box through `resolve()`. It was not verified that the GPU bundle carries `gpu/*`
  and `scripts/data/labeling.py`, so this could break the launch. It needs a bundle check
  first.
- **Deletion check fails open** (finding 17). Treating an empty `brev ls` as unconfirmed
  needs the real listing format for an account with no instances, and that is not available
  offline. Guessing could create false "still listed" alarms.
- **`finish_reason` vs EOS** (finding 16) and **batch composition** (finding 15). These are
  generation-path changes that cannot be tested without the model. They are diagnostic or
  secondary only.
- **Unparsed-as-change scope** (finding 14). Documentation only. The preregistration and
  `docs/` text are outside this pass's write list.
- **Precedence:** if a scorer arm fails validity, UNINTERPRETABLE still takes precedence over
  NOT EVALUABLE. The order was kept as it was.

## Tests after the changes

`cd research/warranted_revision && python3 -m pytest -q`:

`177 passed in 82.19s (0:01:22)`

Pass 03 recorded 170 tests. This pass added 7: 4 in `test_labeling.py` and 3 new analysis
tests in `test_decision_procedure.py`; it also renamed one test.

The first full run gave `1 failed, 176 passed in 80.99s (0:01:20)`. The failing test was
`test_launch_bundle_runs_the_suite_and_the_goal_screen`: inside the GPU bundle,
`test_labeling.py` could not find `scripts/data/labeling.py`. That test now skips when the
script or the scenario file is absent, following the existing `pytest.skip` pattern in
`test_decision_procedure.py`. The run above is the one after that fix.

The dry runs after the re-lock both exited without error:
- `decision_procedure run --dry-run` printed `[plan] dp-confirmatory-v1: {"calls": 4800, …}`
  and `[plan] dry run: no model loaded`. No lock drift was reported.
- `brev_controller.py plan` printed `[controller] dry run only: no provider call was made`.
