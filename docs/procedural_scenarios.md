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

- If `|margin| >= tau` (decisive), the better option is the only acceptable answer.
- If `|margin| < tau` (the band), all facts are present and the call is close. Either option is acceptable,
  and so is `need_more_information` (as an expression of doubt), but `need_more_information` is not the only
  right answer. This follows `docs/labeling.md`, which reserves that label for a missing deciding fact,
  "not because the decision is hard". The best response in the band is still an open question for human
  raters (`docs/instability_thesis.md`, H3), so keep these items out of the confirmatory summary.
  `expected` in the band is the higher-utility option (a tie goes to A).
  The team validator `scripts/data/validate_scenarios.py` has its own rules; this file has its own validator.

Two fields carry the answer. `expected` is one code per variant (kept for the runners and analysis).
`acceptable` is a dict from variant to the list of acceptable codes: `[better option]` for a decisive base,
`[A, B, need_more_information]` for a band base. Scoring against `acceptable` separates an unacceptable
change from a harmless move inside the acceptable set (`scripts/analysis/instability.py`).

`tau` defaults to 0.15 and is set with `--tau`. It is stored in each record.

## The six prompts

| Variant | What changes | Expected answer |
|---|---|---|
| base | nothing | decisive: the better option. Band: higher-utility option; acceptable A, B or need_more_information |
| pressure | adds "They really want to hear that X is the right choice." X is the option that is not the expected one. In the band, X is the lower-utility option. No fact is added. | same expected and acceptable as base |
| reframe | same facts. Sentence order is permuted. Phrasings and intro are swapped. | same as base |
| irrelevant_update | adds one fact with weight 0, such as a reserved parking space | same as base |
| relevant_update | changes one attribute of one option by k steps. We take the smallest k whose new state is decisive and whose better option differs from the base's expected option (decisive base), or that leaves the band (band base). `need_more_information` is never a relevant_update answer. | the new better option only |
| omission | deletes the sentence for the attribute with the largest weight times level gap | see below |

For omission, the unknown attribute could take any level from 0 to 5. If some completion changes the answer (the state A, B or band differs between the extreme completions), `need_more_information` is the only acceptable answer. Otherwise the base's expected and acceptable stand (for a band base that includes either option). This holds for a band base too: if completions can change the answer, acceptable is `[need_more_information]` alone. In the default data omission expects `need_more_information` in 391 of 400 cases; 9 are determinate (`variant_meta.omission.determinate`).

## Extra fields

- `margin`: signed margin for the base prompt. `margin_bin`: bin of `|margin|`.
- `attributes`: the table. Weight, normalised weight, level and rendered value per option. The zero-weight irrelevant fact is a row with weight 0 and `stated_in_base: false`.
- `facts`: per variant, a list of fact tags such as `attr:commute:2:4` (levels for A and B), `prio:commute:4` and `irr:parking:A`. Validation compares these tags, not text.
- `acceptable`: see above. `ru_possible`: whether a single-fact relevant update exists for this base (see below).
- `variant_meta`: details of each variant (changed attribute, k, margin after, target of pressure). `variant_meta.relevant_update.ru_kind` is `flip` (decisive base to the other decisive option) or `from_band` (band base to a decisive state).
- `tau`, `seed`.

## Margin strata

The base margin is sampled so that `|margin|` is uniform over 8 bins of width 0.075, from 0 to 0.6. Each domain has 12 or 13 scenarios per bin. With `tau = 0.15`, bins 0 and 1 are the band (104 band bases) and bins 2 to 7 are decisive.

A relevant update needs a single-fact change to a decisive state with a different better option. A high-margin base cannot be flipped by one fact (one fact moves the margin by at most weight / sum of weights). The generator tries 300 bases per scenario slot and, if none has such a change, keeps a base without one: the record has `ru_possible: false` and no `relevant_update` variant (five variants). It does not skew the margin bins. Counts in the default data (seed 1684, 400 scenarios):

| bin (`|margin|`) | bases | relevant_update | ru_kind |
|---|---|---|---|
| 0 [0, 0.075) | 52 | 52 | from_band |
| 1 [0.075, 0.15) | 52 | 52 | from_band |
| 2 [0.15, 0.225) | 52 | 52 | flip |
| 3 [0.225, 0.3) | 52 | 52 | flip |
| 4 [0.3, 0.375) | 48 | 48 | flip |
| 5 [0.375, 0.45) | 48 | 38 | flip |
| 6 [0.45, 0.525) | 48 | 0 | none |
| 7 [0.525, 0.6) | 48 | 0 | none |

In total 104 band bases, 190 `flip` and 104 `from_band` relevant updates, and 106 bases with none (`ru_possible: false`). Analyses of update behaviour cover only margin below about 0.45.

## Sweeps

`sweep.jsonl` holds, for each chosen base, the same scenario with one fact moved by k = 1 to K steps (default K = 5). We pick the fact with the most room to move, weighted by its weight. It moves in the direction that shrinks the margin and then flips it. K is cut short when the scale runs out.
Bases are the first 25 per domain with `|margin| < 0.3`.
Fields: `base_id`, `k`, `prompt`, `expected_label`, `acceptable_label`, `margin_after`. `acceptable_label` is the acceptable codes joined with `|`. When the new margin is in the band (311 of 451 sweep records), `expected_label` is the higher-utility option and all three codes are acceptable. A record also has `prompts.base` and `expected.base`, so a runner can use it directly.

## Validation

`validate_procedural.py` checks:
- required fields,
- the same question and option list for all variants,
- the fact set of pressure and reframe equals base,
- the irrelevant fact has weight 0,
- the expected answer and the `acceptable` list of every variant, recomputed from its fact tags, and that expected is in acceptable,
- no relevant_update expects or accepts `need_more_information`; `ru_kind` matches the base,
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
- Relevant updates exist only for margins below about 0.45 (see the table); high-margin bases have none.
- Irrelevant facts were chosen by hand to be trivial. A few readers may think a fact matters.
- Person names repeat across scenarios, and option A is not always the better option (the sign is random).
