# Confirmatory protocol: warranted decision updating

This protocol supersedes the exploratory five-variant runs. Existing results remain
useful for hypothesis generation but should not be presented as confirmatory evidence
for the primary factual-discrimination claim.

## Primary question

Can a model distinguish a decision-relevant factual change from a factual change that
should not affect the decision?

- Positive condition: `relevant_update`
- Negative condition: `irrelevant_update`
- Primary choice metric: d′ from answer changes relative to `base`
- Primary distribution metric: AUROC of base-to-variant total-variation distance
- Secondary diagnostics: pressure shifts, reframe changes, omissions, and refusals

The scenario is the unit of analysis. Replicates and option permutations are repeated
measurements, not independent scenarios; uncertainty intervals must resample scenarios.

## Before model runs

1. Freeze all six prompts for each scenario.
2. Generate fresh six-variant blind-label sheets with `scripts/labeling.py make`.
3. Obtain two independent labels from people who did not author the scenarios.
4. Resolve or retain disagreements according to the existing labeling instructions.
5. Record the dataset commit, model revision, scoring-code revision, and run date.

Do not inspect new model outputs while revising prompts or labels.

## Confirmatory runs

Use five replicates and deterministic option permutations:

```sh
RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SAMPLES=5 \
  SCENARIOS=data/career_v2.jsonl python3 scripts/run_nimble.py

RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SAMPLES=5 \
  SCENARIOS=data/career_v2.jsonl python3 scripts/run_chat.py
```

Run the pilot and `career_v2` separately so output files cannot overwrite one another.
Preserve every `sample` and `option_order` field in the raw result files.

## Reporting order

1. Relevant versus irrelevant factual updates (`d_fact`, `auc_f`)
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
