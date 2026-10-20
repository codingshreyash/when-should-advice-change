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

## Known legacy limitation

Six pilot relevant updates lead to `need_more_information`, partially conflating factual
updating with omission behavior. Report the clean 20-scenario batch separately and treat
the combined 30-scenario result as a robustness analysis unless those pilot items are
replaced and relabeled before outputs are inspected.
