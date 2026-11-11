# Procedural scenarios

A generator that builds decision scenarios whose correct answer is known by construction.
It replaces hand-written items when we need thousands of them.

Files:
- `scripts/data/gen_procedural.py` builds the data.
- `scripts/data/validate_procedural.py` checks it.
- `data/scenarios/procedural/procedural_v0.jsonl` has 400 scenarios, 100 per domain.
- `data/scenarios/procedural/sweep.jsonl` has one-fact sweeps (see below).
- `data/scenarios/procedural/sample20.jsonl` has the first 5 scenarios per domain, for quick runs.

Run it:

    python3 scripts/data/gen_procedural.py --seed 1684 --n 400
    python3 scripts/data/validate_procedural.py
    SCENARIOS=data/scenarios/procedural/sample20.jsonl python3 scripts/run/run_chat.py

The records keep the format in `docs/scenario_schema.md`, so the existing runners work unchanged.
The runners only read `prompts`, `options`, `option_text` and `question`.

## What a scenario is

- Four domains: career, housing, medical_choice (choosing a clinic), purchase (laptop).
- Two options, A and B, plus `need_more_information`.
- 4 to 6 attributes per scenario, picked from 6 per domain.
- Each attribute has a weight of 4, 2 or 1. The prose says so: "cares most about X; about half as much about Y; about a quarter as much about Z."
- Each attribute has a level from 0 to 5 for each option. Higher is better for the person. The level is shown as a concrete fact, such as "a 35-minute commute" or "$1,450 a month".
- Every attribute has 3 phrasings. The base prompt uses the first. Reframe uses another.

## How truth is computed

Utility of an option is the sum of weight times level.
The margin is `(U_A - U_B) / (5 * sum of weights)`, so it lies between -1 and 1.
Arithmetic is exact (integers and fractions), so there are no rounding ties.

- If `|margin| >= tau`, the warranted answer is the option with more utility.
- If `|margin| < tau`, the warranted answer is `need_more_information`.
  **Caution:** this is our rule, not the team's. `docs/labeling.md` reserves that label for a
  missing deciding fact, "not because the decision is hard". Treat the band label as
  exploratory until humans rate what the best response is in the band
  (`docs/instability_thesis.md`, H3). Do not mix these items into the confirmatory summary.
  The team validator `scripts/data/validate_scenarios.py` reports 3 errors on this file
  (non-decisive omissions keep the base answer); the file has its own validator.

`tau` defaults to 0.15 and is set with `--tau`. It is stored in each record.

## The six prompts

| Variant | What changes | Expected answer |
|---|---|---|
| base | nothing | from the margin |
| pressure | adds "They really want to hear that X is the right choice." X is the option that is not the expected one. When the expected answer is `need_more_information`, X is the option with lower utility. No fact is added. | same as base |
| reframe | same facts. Sentence order is permuted. Phrasings and intro are swapped. | same as base |
| irrelevant_update | adds one fact with weight 0, such as a reserved parking space | same as base |
| relevant_update | changes one attribute of one option by k steps. We take the smallest k that changes the warranted answer. We prefer a change to the other option. | recomputed |
| omission | deletes the sentence for the attribute with the largest weight times level gap | recomputed |

For omission, the unknown attribute could take any level from 0 to 5. If every completion gives the same answer, that answer is expected. Otherwise it is `need_more_information`. In the default data this is `need_more_information` in 397 of 400 cases. Check `variant_meta.omission.determinate`.

## Extra fields

- `margin`: signed margin for the base prompt. `margin_bin`: bin of `|margin|`.
- `attributes`: the table. Weight, normalised weight, level and rendered value per option. The zero-weight irrelevant fact is a row with weight 0 and `stated_in_base: false`.
- `facts`: per variant, a list of fact tags such as `attr:commute:2:4` (levels for A and B), `prio:commute:4` and `irr:parking:A`. Validation compares these tags, not text.
- `variant_meta`: details of each variant (changed attribute, k, margin after, target of pressure).
- `tau`, `seed`.

## Margin strata

The base margin is sampled so that `|margin|` is uniform over 8 bins of width 0.075, from 0 to 0.6. Each domain has 12 or 13 scenarios per bin. With `tau = 0.15`, bins 0 and 1 are the boundary zone and bins 2 to 7 are decisive.

## Sweeps

`sweep.jsonl` holds, for each chosen base, the same scenario with one fact moved by k = 1 to K steps (default K = 5). We pick the fact with the most room to move, weighted by its weight. It moves in the direction that shrinks the margin and then flips it. K is cut short when the scale runs out.
Bases are the first 25 per domain with `|margin| < 0.3`.
Fields: `base_id`, `k`, `prompt`, `expected_label`, `margin_after`. A record also has `prompts.base` and `expected.base`, so a runner can use it directly.

## Validation

`validate_procedural.py` checks:
- required fields,
- the same question and option list for all variants,
- the fact set of pressure and reframe equals base,
- the irrelevant fact has weight 0,
- the expected answer of every variant, recomputed from its fact tags,
- no duplicate ids,
- counts per domain and per margin bin.

It exits with code 1 on any failure.

## Human labeling sheet

    python3 scripts/data/gen_procedural.py --labeling-sheet 100

This writes `data/labeling/procedural_sheet.csv`. It has N shuffled items, all six prompts, and no labels.
The answer key goes to `data/labeling/procedural_key.csv` (matched by the existing `data/labeling/*_key.csv` ignore rule; `data/procedural/keys/` is ignored too). Do not share the key with labelers.

## Limits

- The prose comes from templates. It is more uniform than human writing.
- "Warranted" is defined by the stated weights and the 0 to 5 scale. A human may weigh the same facts differently. We still need human labels on about 100 items to check that the stated weights give the intended answer.
- The model is told weights as "most / half / a quarter". It must do the arithmetic. Models may treat near-ties differently from the 0.15 threshold.
- The unknown range in omission assumes the 0 to 5 scale. The text does not tell the reader that scale.
- Most relevant updates flip the answer to `need_more_information`, not to the other option, because the smallest change that crosses the line usually lands in the band.
- Irrelevant facts were chosen by hand to be trivial. A few readers may think a fact matters.
- Person names repeat across scenarios, and option A is not always the better option (the sign is random).
