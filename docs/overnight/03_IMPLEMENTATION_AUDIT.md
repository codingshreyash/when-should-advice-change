# Overnight pass 03: implementation audit of the four-arm decision-procedure experiment

Scope: code, configs, lock, `scripts/data/labeling.py` and the preregistration
(`docs/PREREGISTRATION_DECISION_PROCEDURES.md`). No code was modified. No model, GPU, Brev or
API call was made. **No human labels exist.** The only labels in the repository are the
scenario author's drafts (`expected`). Some checks below use those drafts, but only to show
what the code *accepts*. Those counts are not eligibility estimates.

Reproduction script: `docs/overnight/analysis/03_audit_checks.py`. It is CPU-only and
writes only to a fresh temp directory. Run it from the repo root with
`PYTHONPATH=research/warranted_revision/src`. Its printed output is quoted below as "check N".

## Tests and dry runs executed

| command (from the rules) | exact summary line(s) |
|---|---|
| `cd research/warranted_revision && python3 -m pytest -q` | `170 passed in 72.98s (0:01:12)` |
| decision-procedure `run --dry-run` (full config) | `[plan] dp-confirmatory-v1: {"calls": 4800, "per_arm": {"D": 1200, "A": 1200, "B": 1200, "C": 1200}, "generation_batches": {"B": 134, "C": 134}}` / `[plan] preflight: {"calls": 64, "per_arm": {"D": 16, "A": 16, "B": 16, "C": 16}, "generation_batches": {"B": 2, "C": 2}}` / `[plan] dry run: no model loaded` |
| `brev_controller.py plan --hourly 1.06 --max-usd 3 ...` | `[controller] decision_procedure estimate: 99 min on the box for 4864 calls; --est-seconds-per-call 6.0 ignored`; budget `permitted_hours 2.264`, `run_deadline_minutes 105`, `est_run_minutes 99.0`, `worst_case_usd 2.4`; `[controller] dry run only: no provider call was made` |

The lock check inside the dry run passed: it raised no drift error. Two extra offline plans
were run: `--max-usd 15 --hourly 1.06` gave `worst_case_usd 4.24`, and `--max-usd 15 --hourly
2.0` gave `worst_case_usd 8.0`. Both exited 0.

## Findings

| # | severity | defect | evidence | proposed fix |
|---|---|---|---|---|
| 1 | **blocking** | The analysis accepts the author's draft labels as "blind" labels. `load_labels` reads `expected` from any JSONL file. It checks no provenance and records no label-file hash. | `decision_procedure_analysis.py:56-68`. Check 2b: `--labels data/scenarios/career_pilot.jsonl data/scenarios/career_v2.jsonl` loads without error and yields `{'primary': 24, 'subthreshold': 24, 'omission': 29, 'pressure': 30}`. These counts come from **draft** labels. | Accept only files that carry provenance written by `labeling.py score`: labeler IDs, the sha256 of each sheet, and `label_source: "blind"`. Refuse anything under `data/scenarios/` or `data/derived/`. Write the label sha256s into `analysis.json`. |
| 2 | **blocking** | `labeling.py score` turns two copies of the draft labels into a `*_blind.jsonl`. It does not check that the two sheets differ, and it records no labeler identity. | `scripts/data/labeling.py:55-80`. Check 2: both sheets were filled from `expected`, and the **same file was passed twice**. `score` exited 0 and printed `ALL 70 1.00 1.00` (pilot) and `ALL 140 1.00 1.00` (v2). The analysis accepted the output, with the same counts as 1 (`identical to 2: True`). | Refuse identical sheet paths or contents. Require `--labeler-a/--labeler-b` IDs. Write the sheet hashes and the IDs into the output. Report each labeler's agreement with the draft as a diagnostic. |
| 3 | **blocking** | Labels are neither required nor frozen before the confirmatory run. `run()` has no label check. The job runs and prints the raw calls even when no labels are bundled. The blind files are not in `LOCKED`. Labels could therefore be written or changed after the outputs are seen, which breaks §4 ("before any confirmatory run") and §9 (labels at step 4). | `decision_procedure.py:520-583` (no label check), `:728-734` (`LOCKED` excludes `CS1684_LABELS`). `decision_procedure_job.sh:75-83`: on missing labels it only prints `DP ANALYSIS SKIPPED` and still runs `emit --calls`. Check 7: `career_*_blind.jsonl: locked=False`. | For a non-pilot config, `run`, `build_plan` and the job must refuse unless both blind files exist and their sha256s are in the lock. The analysis must check the label hashes against the lock. |
| 4 | should-fix | A not-evaluable study is labelled `NULL`, and the primary estimate and CI are still computed and written. | `decision_procedure_analysis.py:295-300` and `:361-363`. `evaluable` is used only at `:384`. Check 6: `{'decision': 'NULL', 'kind': 'not evaluable', ...}`. | See the next section and amendment A1. |
| 5 | should-fix | Validity does not check completeness. A scorer arm missing most of its rows passes, and the analysis never compares the row count with `planned_calls`. Invalid or missing calls can disappear without notice. | `decision_procedure_analysis.py:262-284`. Check 3: `arm A rows kept 40 of 1200; passed = True`. | Require exactly one row per (arm, id, sample, variant) and a total equal to `manifest.planned_calls`. Otherwise the run is UNINTERPRETABLE. |
| 6 | should-fix | Duplicate rows silently overwrite each other. | `decision_procedure_analysis.py:98-103`. Check 4: `duplicate row silently overwrites -> b`. | Raise on duplicate keys. |
| 7 | should-fix | The Holm family shrinks when contrasts are not evaluable or have no p-value. The preregistration says "Holm across 6" (and across 4). | `decision_procedure_analysis.py:367, 379`. Check 5: raw p = 0.01 becomes 0.06 with m = 6 but 0.03 when three contrasts drop out (m = 3). | Fix m at 4 and 6 by design and count missing contrasts as p = 1. This needs an amendment because the preregistration is ambiguous (A4). |
| 8 | should-fix | The $5 experiment cap is not enforced. The controller accepts `--max-usd` up to 15 for this config, and nothing reads the ledger or adds up the pilot and confirmatory launches. | `gpu_guard.py:21` (`FIRST_RUN_CAP_USD = 15.0`), `:67`. Searching for `ledger\|cumulative\|spent` in the controller, `gpu_guard` and `decision_procedure` finds nothing. Plan at `--max-usd 15 --hourly 2.0`: exit 0, `worst_case_usd 8.0`. | Add a decision-procedure cap: $5 minus the decision-procedure spend recorded in `PROJECT_LEDGER.md`. Refuse larger caps. |
| 9 | should-fix | At the `--max-usd 3` plan in the rules, the on-box gate would refuse the full run **by the code's own estimates**. Preparation and preflight would be paid for with no confirmatory data. | Check 9: `estimate total 99.0 min = prepare 30 + preflight 8.8 + full run 60.2`. The gate needs `60.2 × 1.5 = 90.3 min`, but only `66.2` minutes would be left out of 105 → `FAIL`. Gate rule: `decision_procedure.py:711`. Pip install and the CPU tests reduce the time left further. These are planning estimates, not measured times. | Use the technical pilot's measured timing to pick a cap where the gate can pass. Otherwise do not launch the full run at $3. This is a budget decision for the PI. |
| 10 | should-fix | The lock certifies itself. `lock --write` regenerates every hash. The lock file, `decision_procedure_job.sh`, `remote_job.sh`, `brev_controller.py`, `gpu_guard.py` and `labeling.py` are not locked. | `decision_procedure.py:873-877`; check 7 (all `locked=False`). | Record the lock file's sha256 and commit in a dated amendment. Have the controller refuse a lock whose sha256 differs. Add the job scripts, controller, guard and `labeling.py` to `LOCKED`. |
| 11 | should-fix | The technical pilot prints raw choices and model text into the job log (`emit --calls`). Nothing stops the pilot from running before labelling, so the outputs for 4 scenarios could be seen before the labels are made. | `decision_procedure_job.sh:57`. No label check in `run()` (finding 3). | Enforce labels → pilot (§9 order), or withhold the pilot's raw rows until the labels are locked. |
| 12 | should-fix | Invalid or blank labeler entries are dropped with only a printed `PROBLEM` line. The scenario then becomes ineligible without notice, or the analysis crashes with a `KeyError` if `base` is missing. | `labeling.py:66-70`; `decision_procedure_analysis.py:66` (`labels["base"]`). | `score` should refuse incomplete sheets and exit non-zero. |
| 13 | should-fix | The "private" answer key can be regenerated. `make` uses a fixed seed, and the drafts are in the repository, so blindness rests entirely on labelers not having repository access. | `labeling.py:30` (`random.Random(1684)`). Check 2 rebuilt the key in a temp directory from public files. | Give labelers the sheet only, and record a written attestation that they did not see the repository or any model output. |
| 14 | minor | The "unparsed = change" sensitivity check covers H, F and Fsub only. Press, Ask and U still drop unparsed pairs. | `decision_procedure_analysis.py:120-153`. Check 4: Press and Ask are `None` under both rules. | Write down that §5's sensitivity rule applies to the change outcomes only. |
| 15 | minor | Generation uses left-padded greedy batches whose composition differs between a base prompt and its variant. This can add numerical noise to B and C (secondary arms only). | `decision_procedure.py:379-417`. | Record it as a limitation, or batch by (id, sample). |
| 16 | minor | `finish_reason` is `"length"` whenever the count of non-pad tokens reaches the limit, even when the output stopped naturally at exactly the limit. | `decision_procedure.py:404-406`. | Compare against EOS. This is diagnostic only. |
| 17 | minor | The deletion check fails open: any `brev ls` output with exit code 0 that lacks the exact name line counts as "deleted". | `brev_controller.py:237-242`. The piped format is marked VERIFIED in `brev_commands.json`. | Treat empty or unparseable listings as unconfirmed. |

**Checked and found correct:**
- **Option orders are invariant across variants and arms.** Check 1: `cells with >1 order 0` of 150 (scenario, sample) cells. The order varies across samples in 30 of 30 scenarios.
- **The exact sign-flip p is correct.** It matches brute force (0.40625 vs 0.40625).
- **Holm is correct for a fixed family.**
- **The bootstrap uses percentile indices 250 and 9749 of 10,000** with seed 1684.
- **`decide()` implements the four §8 conditions.**
- **Eligibility rules match the §4 table.**
- **Scorer errors are recorded, not dropped.**
- **Spending is bounded per launch at $3 and $1.06/h.** I derived this from the code timeouts; it was not run. The run finishes by `t_end` (worth $2.40). Copy-back is limited to 900 s and the delete call to 300 s, so the delete is issued about 20 minutes after `t_end` at most. That adds about $0.35, which stays under $3 (`brev_controller.py:324-357`).

## Eligibility and the not-evaluable outcome

§4 and §8 call a study with fewer than 15 primary-eligible scenarios a "NULL" of kind "not
evaluable". The code returns `decision: "NULL"` (finding 4). **It should be a separate
outcome, NOT EVALUABLE, and not a null.** The reasons:

- **A null is a result about the effect; "not evaluable" means there is no result.** §8's two
  null kinds ("equivalent within ±0.10", "inconclusive at this precision") are both
  statements about the CI. With fewer than 15 eligible scenarios no confirmatory CI is
  computed, so calling the outcome a null invites it to be read as evidence of no effect.
- **The code already has the right precedent.** A failed scorer gate returns
  `UNINTERPRETABLE`, not `NULL`. A too-small eligible set is the same kind of thing: the
  design was not met.
- **The eligibility count is known before any GPU spend.** It uses only the labels (§4). The
  check can and should run *before* launch, and if it fails, nothing is spent. Today it runs
  only after the full run (`decision_procedure_analysis.py:384`).
- **No estimate or CI should be written when the outcome is not evaluable.** Today the
  primary block is written anyway (`:361-363`), which invites an underpowered estimate to be
  reported.

The eligible count under the blind labels is **not available**, because no blind labels
exist. It needs two completed blind sheets scored by a hardened `labeling.py` (findings 2 and
12). The draft-label count (24 primary) only shows what the code accepts. It must not be used
to predict eligibility or to set the threshold.

## Recommended pre-run amendments

All of these are to be filed as dated amendments before labelling or any launch, and none of
them is a response to model output (no output exists).

**A1. Not-evaluable outcome.** PI decision: **yes**. It changes the §8 decision vocabulary.
The primary contrast (D − A on Δ) is unchanged. Exact wording:

> *Amendment 1 (dated, pre-run). Sections 4 and 8 are amended as follows. If, after blind
> labelling and before any confirmatory launch, the primary set has fewer than 15 scenarios,
> the outcome is **NOT EVALUABLE**. This is a third terminal outcome, alongside REPLICATE and
> NULL, and is not a kind of null. It is computed from the labels alone. No confirmatory run
> is launched and no GPU money is spent on it. The write-up reports the eligible counts per
> set, agreement and Cohen's κ per variant, and the statement "the primary contrast was not
> evaluated; this is not evidence for or against an adapter effect". No relabelling,
> adjudication, new items or change of threshold follows. The same outcome applies if a
> confirmatory run yields fewer than 15 paired primary scenarios. In both cases no primary
> estimate, CI or p-value is computed or reported. The NULL outcome in §8 keeps only its two
> kinds, "equivalent within ±0.10" and "inconclusive at this precision".*

**A2. Labels before launch, frozen and with provenance (findings 1–3, 11–13).** PI decision:
**yes**, because it amends §4 and §9. The contrast is unchanged.

> *Amendment 2. The blind label files must be produced by `labeling.py score` from two
> different sheets with recorded labeler IDs. They must carry the sheet sha256s, and their
> own sha256s must be added to the lock before the technical pilot. No run, the pilot
> included, starts without them. The analysis accepts only these locked files. Labelers
> receive the sheet only, and each signs that they did not see the repository, the draft
> labels or any model output.*

**A3. Completeness is part of validity (findings 5 and 6).** PI decision: **no**. This applies
§7 as written and does not touch the contrast.

> *Amendment 3. Section 7 is amended so that the run is UNINTERPRETABLE unless there is exactly
> one row per planned (arm, scenario, sample, variant) and the total equals the planned calls.*

**A4. Fixed Holm families (finding 7).** PI decision: **yes**. It concerns the secondary
inference only.

> *Amendment 4. The Holm families have fixed sizes, 4 (D − A) and 6 (procedure contrasts). A
> contrast that is not evaluable enters its family with p = 1.*

**A5. Spending (findings 8 and 9).** PI decision: **yes**. It is a budget decision.

> *Amendment 5. The controller refuses a decision-procedure launch whose `--max-usd` exceeds
> $5 minus the decision-procedure spend recorded in `PROJECT_LEDGER.md`. The confirmatory cap
> is chosen from the technical pilot's measured timing so that the on-box gate (projected × 1.5
> ≤ minutes left) can pass. If no cap within the remaining $5 allows that, the full run is not
> launched.*

**A6. Lock coverage (finding 10).** PI decision: **no**. It does not touch the contrast.

> *Amendment 6. `LOCKED` adds `decision_procedure_job.sh`, `remote_job.sh`,
> `brev_controller.py`, `gpu_guard.py`, `scripts/data/labeling.py` and the blind label files.
> The lock file's sha256 is recorded in this amendment, and the controller refuses a lock with
> a different sha256.*

Findings 14–17 need only documentation or code hygiene, not amendments.
