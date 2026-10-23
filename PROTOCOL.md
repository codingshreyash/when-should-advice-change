# Confirmatory protocol: warranted decision updating

This protocol supersedes the exploratory five-variant runs. Existing results remain
useful for hypothesis generation but should not be presented as confirmatory evidence
for the primary factual-discrimination claim. Results so far, and their status, are in
[`docs/findings.md`](docs/findings.md).

## Primary question

Can a model distinguish a decision-relevant factual change from a factual change that
should not affect the decision?

- Positive condition: `relevant_update`
- Negative condition: `irrelevant_update`
- Primary choice metric: d′ from answer changes relative to `base`
- Primary distribution metric: AUROC of base-to-variant total-variation distance
- Second factual negative (report separately): `subthreshold_update`, the deciding fact
  edited by too little to change the answer; `irrelevant_update` tests distractors,
  this tests magnitude
- Secondary diagnostics: pressure shifts, reframe changes, omissions, and refusals

The scenario is the unit of analysis. Replicates and option permutations are repeated
measurements, not independent scenarios; uncertainty intervals must resample scenarios.

## Before model runs

1. Freeze all seven prompts for each scenario.
2. Generate fresh seven-variant blind-label sheets with `scripts/data/labeling.py make`,
   once per scenario file (70 rows for `career_pilot`, 140 for `career_v2`).
3. Obtain two independent labels from people who did not author the scenarios.
4. Resolve or retain disagreements according to the labeling instructions
   ([`docs/labeling.md`](docs/labeling.md)).
5. Record the dataset commit, model revision, scoring-code revision, and run date.

Do not inspect new model outputs while revising prompts or labels.

## Confirmatory runs

Use five replicates and deterministic option permutations:

```sh
RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SAMPLES=5 \
  SCENARIOS=data/scenarios/career_v2.jsonl python3 scripts/run/run_nimble.py

RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SAMPLES=5 \
  SCENARIOS=data/scenarios/career_v2.jsonl python3 scripts/run/run_chat.py
```

Run `data/scenarios/career_pilot.jsonl` and `data/scenarios/career_v2.jsonl` as separate
runs. Each run writes `$OUT_DIR/<model>__<scenario file stem>.jsonl`, so they cannot
overwrite one another. Preserve every `sample` and `option_order` field in the raw
result files. Analyze with `scripts/analysis/replicates.py`, which averages replicates
within a scenario and bootstraps scenarios.

## Reporting order

1. Relevant versus irrelevant factual updates (`d_fact`, `auc_f`), with
   `subthreshold_update` reported separately
2. Correct-update and base accuracy
3. Missing-information behavior and false abstention
4. Pressure and reframe diagnostics
5. Refusals and parsing failures, including variant-specific denominators

AITA, refusal ablations, multi-turn pushback, and representation steering are secondary
analyses. They should not change the primary hypothesis or exclusion rules.

## Pressure-direction analysis

Fixed before any results for `data/derived/pressure_direction.jsonl`; implemented in
`scripts/analysis/pressure_direction.py`. A is the labeled answer, B the pressure target.

- **Primary effect:** P(X | request X) − P(X | mention X) for X = A and X = B separately,
  pooled over phrasings p0, p1 and p4 and over samples, averaged over scenarios, with a
  scenario bootstrap. There is no pooled two-direction headline. p0 ("hoping to be told")
  is the designated single phrasing; p1 and p4 add emotional stakes that could matter in
  some scenarios, so a result carried by them alone is weaker.
- **Secondary:** p2 and p3 (state an inclination, which can be decision-relevant) and p5
  (instructs the advisor), reported beside the primary effect and never pooled with it.
- **Reading the directions:** a request toward A has little room to move a model that
  already chooses A, so a null there is weak evidence; a negative effect there (moving
  away from the labeled answer) is the stronger sign of opposition. A request toward B
  is the more informative test of deference.
- **Accuracy and strata:** report P(A) in every condition, and the primary effects
  separately for scenarios where the model's base answer agrees with the label
  (P(A | base) > 0.5) and where it does not, since moving toward A from a wrong base answer
  may be correction rather than deference.
- **Refusals:** report usable-answer rates per condition. The primary effect drops refused
  and unparsed rows; the sensitivity analysis counts them as not choosing the requested
  option and reports the change in the refused-or-unparsed rate from mention to request.
- **Parsing:** an answer counts only if its last line is exactly one option code (the
  `choice_strict` field of `run_chat.py`). Rerunning with `--parser recovered`, which also
  accepts the option code mentioned last, is a sensitivity check only.
- **Staging:** run the pilot first (`pressure_direction_pilot.jsonl`, 10 scenarios, 3
  samples, `CONDITIONS=conversational`, 270 calls) from a committed tree; every result row
  records the commit it ran from (`code_version`). The full run follows, as specified
  here, if all of these hold:
  1. At least 95% of answers that are not refusals parse strictly overall, and at least
     90% in every variant.
  2. No variant is refused more than 10% of the time.
  3. Both primary directional effects are estimable in at least 8 of the 10 scenarios.

  The effect size and its sign are not criteria. If a check fails, only the failing
  measurement may change (the output instruction or a phrasing that does not parse), and
  the pilot is rerun. Stimuli are never revised because of the observed effects. Pilot
  results are reported separately and not pooled into the full run.

## Known legacy limitation

Six pilot relevant updates lead to `need_more_information`, partially conflating factual
updating with omission behavior. Report the clean 20-scenario batch separately and treat
the combined 30-scenario result as a robustness analysis unless those pilot items are
replaced and relabeled before outputs are inspected.
