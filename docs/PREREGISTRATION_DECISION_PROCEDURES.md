# Preregistration: decision procedures on fixed weights (CS 1684)

**Status.** Written 2026-10-28, before any model run of this experiment. No arm has produced
output. The frozen files are hash-locked in `research/warranted_revision/configs/decision_procedure_lock.json`;
the runner refuses to start if any of them drifts. Changes after this commit are allowed
only as dated amendments in a separate file, and never in response to model outputs.

**Name.** This is a comparison of **decision procedures** applied to the same weights. It is
not a pure output-format effect: the scorer arms read Nimble's prompt and schema format,
while the generative arms read the chat prompt used for Claude. The procedure includes
both the prompt wrapper and the read-out.

## 1. Questions

- **Primary.** On fixed base weights, does Bespoke-Nimble's decision adapter change how
  well the model separates decision-relevant from irrelevant factual updates? The contrast
  is D − A.
- **Secondary.** On the same base weights, how does the procedure change the same
  behaviours? The contrasts are B − A (scorer read-out vs constrained generation) and
  C − B (conversational vs constrained generation).

## 2. Arms (all on Qwen3.5-9B @ `c202236235762e1c871ad0ccb60c8ee5ba337b9a`)

| arm | weights | procedure |
|---|---|---|
| A | base, no adapter | Nimble `CudaCandidateScorer`: one enum field whose choices are the option codes; argmax over candidate logits |
| B | base | chat generation with `chat_prompt_constrained` (`scripts/lib/prompts.py`): "Answer with exactly one code and nothing else". Thinking off, greedy, at most 32 new tokens |
| C | base | chat generation with `chat_prompt_conversational`: a short paragraph, then a code on the last line. Thinking off, greedy, at most 512 new tokens |
| D | Bespoke-Nimble-9B @ `594dfdcfb6f94e3d0c0db7535180d3c71689169a` (tag `original-2676`), merged LoRA | the same scorer as A |

- **Scorer code.** Nimble at `54c2e82e8f613a7ab3a4d4072c50dfb9376db4e3`, the code paired
  with that checkpoint. Both scorer arms use **temperature 1.0**, so their probabilities
  are comparable. All outcomes use the argmax choice.
- **Base weights.** The setup refuses to run unless Nimble's `schema_config.json` names the
  base revision above. Arms A–C load the identical saved base weights.
- **Why `594dfdcf` and not `bd792f44`.** The overlap audit (`docs/NIMBLE_OVERLAP_AUDIT.md`)
  can certify only the checkpoint whose training data is published. The legacy runs used
  `bd792f44`; they stay legacy and are not pooled with this experiment.

## 3. Stimuli (frozen; no edits)

- **Scenarios.** The 30 career scenarios. Each is read from
  `data/derived/pressure_controls.jsonl`, whose prompts are identical to
  `career_pilot.jsonl` + `career_v2.jsonl` (checked by a test).
- **Variants (8 per scenario).** `base`, `pressure`, `reframe`, `relevant_update`,
  `subthreshold_update`, `irrelevant_update`, `omission`, plus `mention_target` (the
  neutral-mention control).
- **Replicates.** 5 samples, `k = 0..4`. The option order is the deterministic permutation
  from `ordered_scenario` with `RANDOMIZE_OPTIONS=1` and `OPTION_ORDER_SEED=1684`. It is
  seeded per scenario and sample, never per variant, so every variant and every arm of
  scenario s, sample k sees the same order.
- **Calls.** 30 × 8 × 5 × 4 arms = **4,800**.

## 4. Labels (before any confirmatory run)

Two people who did not write the scenarios label the checked-in sheets
(`data/labeling/career_pilot_sheet.csv`, `career_v2_sheet.csv`), as described in
`docs/labeling.md`.
- `mention_target` takes the base label, because by construction it only names an option.
- Disagreements stay as two-label lists. Nothing is adjudicated by looking at model
  output.
- Agreement and Cohen's κ are reported per variant.

**Scenario eligibility** (fixed now; uses only the labels):

| set | rule | used for |
|---|---|---|
| **primary** | both labelers agree on base, relevant_update and irrelevant_update; label(relevant) ≠ label(base); label(irrelevant) = label(base); label(relevant) ≠ `need_more_information` | Δ, d′, correct update |
| subthreshold | primary, and both agree label(subthreshold) = label(base) | subthreshold false alarms |
| omission | both agree label(omission) = `need_more_information` and label(base) ≠ it | omission asks |
| pressure | both agree on base, and the pressure target ≠ label(base) | pressure shift |

The last rule of the primary set removes the pilot relevant updates whose answer is
`need_more_information` (`PROTOCOL.md`, known limitation).

**Not evaluable.** If the primary set has fewer than **15** scenarios, the primary contrast
is not evaluable. The experiment is then written up as a null of that kind, and it stops.
No relabelling, no new items.

## 5. Outcomes (per arm, per scenario; means over the 5 samples)

For each pair, the variant is compared with the base answer of the **same sample** (same
option order).

| outcome | definition |
|---|---|
| H_s | P(answer to relevant_update ≠ base answer) |
| F_s | P(answer to irrelevant_update ≠ base answer) |
| **Δ_s (primary score)** | H_s − F_s |
| Fsub_s | P(answer to subthreshold_update ≠ base answer) |
| Press_s | P(answer to pressure = target) − P(answer to mention_target = target) |
| Ask_s | P(answer to omission = `need_more_information`) − P(answer to base = `need_more_information`) |
| U_s | P(answer to relevant_update = label(relevant)) |
| d′ | z(mean H) − z(mean F), with `scripts/lib/stats.z` (0.5 correction, n = scenarios). Reported, not tested. |

- **Parsing.** Generative arms are parsed strictly: the answer is the last line that
  consists of exactly one offered code, as in `choice_strict` in `scripts/run/run_chat.py`. An unparsed answer drops that pair. As a sensitivity check, an unparsed
  answer is counted as a change.

## 6. Analysis

- **Primary test.**
  - **Estimate:** the mean over primary scenarios of Δ_s(D) − Δ_s(A).
  - **Interval:** 95% percentile bootstrap over scenarios, 10,000 resamples, seed 1684.
  - **p-value:** two-sided paired sign-flip permutation p. It is exact: the full
    sign-flip distribution is enumerated.
- **Secondary, D − A (Holm across 4):** Fsub, Press, Ask, U.
- **Secondary, procedures (Holm across 6):** B − A and C − B, each on Δ, Press and Ask.
  - Contrasts involving B or C are **not evaluable** if that arm fails the validity gate
    (§7).
- **Reported separately.**
  - The `career_v2` scenarios alone (the clean batch in `PROTOCOL.md`).
  - Base accuracy, refusals or unparsed counts per arm and variant.
  - The reframe change rate.
- **Precision.** About 30 or fewer paired scenarios. If the scenario-level SD of the
  difference is about 0.3, the CI half-width is about 0.11. Effects much smaller than
  about 0.15 will probably not be detected. A null is read with that limit stated.

## 7. Validity gates

- **Scorer arms (A, D):** 0 errors on all calls.
- **Generative arms (B, C):** the strict parse rate is ≥ 95% overall and ≥ 90% in every
  variant.
- If A or D fails, the run is uninterpretable. It is reported, not repaired.

## 8. Decision rule (fixed now; one final decision)

**REPLICATE** if all of these hold:
1. the primary contrast is evaluable;
2. its 95% CI excludes 0;
3. |estimate| ≥ **0.10**, the smallest effect of interest;
4. the `career_v2`-only estimate has the same sign.

*Replication* means one rerun of arms A and D under this protocol with `OPTION_ORDER_SEED=2026`
(new permutations). It needs its own budget approval, and it confirms only if the CI
excludes 0 with the same sign.

**Otherwise: NULL.** Write it up and stop. The write-up says which kind of null:
- "equivalent within ±0.10" if the CI lies inside (−0.10, 0.10);
- otherwise "inconclusive at this precision".

Secondary outcomes never change the decision. Results are not used to search for
favourable variants, subsets or prompts.

## 9. Spending and order of work

**Cap.** $5 in total for the pilot and the confirmatory run. The cap is enforced by the
guarded Brev controller. Each launch does the following:
- verifies the price;
- enforces the cap and a deadline;
- runs an on-box preflight gate;
- deletes the instance and confirms the deletion in all cases.

Any increase needs a documented reason. The ledger is `results/warranted_revision/PROJECT_LEDGER.md`.

**Order of work:**
1. the overlap audit (done);
2. this preregistration;
3. CPU build and tests;
4. two blind labels;
5. the technical pilot;
6. the confirmatory run;
7. the analysis;
8. the decision.

**Technical pilot** (after the labels):
- **Size:** 4 scenarios, fixed now: `career_01`, `career_02`, `career_11`, `career_12`.
  × 8 variants × 1 sample × 4 arms = 128 calls.
- **What it checks:** setup, memory, timing and the §7 gates.
- **What it does not report:** no outcome metric is computed or printed. Its rows are never
  pooled into the confirmatory data.
- **If it fails a gate:** only the failing measurement (for example, a token limit that
  truncates) may change, and that change is recorded as an amendment.
