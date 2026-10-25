# Scenario record format

One JSON object per line in `data/scenarios/career_pilot.jsonl` (`career_01`–`career_10`)
and `data/scenarios/career_v2.jsonl` (`career_11`–`career_30`, built by
`scripts/data/build_career_v2.py`). Check both with
`python3 scripts/data/validate_scenarios.py data/scenarios/career_pilot.jsonl data/scenarios/career_v2.jsonl`.

    id            short unique id, e.g. "career_01"
    domain        "career" ("aita" in data/derived/aita_pressure.jsonl, which has
                  only base and pressure prompts)
    options       list of option codes; ALWAYS includes "need_more_information"
    option_text   code -> short human-readable label shown to the model
    question      the action question, e.g. "What should they do?"
    prompts       dict of seven prompts. Keys:
       base             the facts + priorities + question, neutral wording
       pressure         same facts; user states which option they want
       reframe          same facts; order/valence changed, nothing added/removed
       relevant_update  one fact changed so the warranted action changes
       subthreshold_update  the deciding fact edited by too little to change the action
       irrelevant_update    one off-topic fact added that should not affect the action
       omission         one decision-critical fact removed
    expected      dict of expected option per prompt. Draft labels written by
                  the scenario author; must be RELABELED BLIND by two people who
                  did not write the scenario before any result is reported.
    pressure_target   the option the user pushes toward in the pressure prompt
    notes         why the relevant_update should change the answer, and what the
                  omission removes. This is the "say why" field for labelers.

Rules used when writing variants:
- pressure and reframe never add, remove, or alter a fact. If you can't write
  the reframe without changing a fact, the scenario is not clean enough; fix it.
- relevant_update changes exactly one fact or priority, and the author must be
  able to say in one sentence why the action changes.
- irrelevant_update changes the described state of the world but leaves the
  expected answer equal to base. In the current files it appends one off-topic
  sentence (scripts/data/add_irrelevant_updates.py). It is the primary factual
  negative control for relevant_update; pressure and reframe are secondary controls
  with a different form.
- subthreshold_update makes one in-place edit, preferably in the slot
  relevant_update edits and with a number when relevant_update changes one, by an
  amount or in a direction that leaves the expected answer equal to base. Edits and
  reasons live in scripts/data/add_subthreshold_updates.py. It is the harder factual
  negative: irrelevant_update tests distractors, this tests magnitude.
- omission removes the fact the decision hinges on; the warranted answer becomes
  need_more_information.
- Every prompt ends with the same question and the same option list.

Derived files in `data/derived/` (pressure controls, refusal ablation, threshold sweep)
use the same core fields with their own prompt keys (the threshold sweep also has
`kind`, `source`, `low`, `high`, `threshold`, `unit` and `levels`); each builder's
docstring in `scripts/data/` describes its keys.

## Threshold sweeps

`data/derived/threshold_sweep.jsonl` and `threshold_sweep_hard.jsonl` (both built by
`scripts/data/build_threshold_sweep.py`) hold scenarios in which one number decides the
answer at a known threshold. Each record adds `low`/`high` (the option that is right
below/above the threshold), `threshold`, `unit`, and `levels` (eight values from 0.5x
to 1.5x the threshold, never at it). Prompt keys are `L<k>` (no pressure), `L<k>_pl`
(pressure toward the low-side option) and `L<k>_ph` (toward the high-side option); the
expected answer never depends on pressure.

- The first file states the rule or needs one comparison (8 scenarios).
- The `_hard` file states no rule: the threshold follows from combining two or three
  facts with the person's priority, such as a raise after 25% tax against a $300 monthly
  cost (6 scenarios). Each entry carries its decision as code, and the builder asserts
  every label against it. These have not been run; a scenario author should check that
  each template reads unambiguously before any model sees it.

## Paired pressure-direction set

`data/derived/pressure_direction.jsonl` (built by `scripts/data/build_pressure_direction.py`)
separates a request for an option from merely naming it, in both directions. For each of
29 scenarios (career_10 is skipped: its base label is need_more_information), A is the
labeled answer (the scenario author's expected base answer, not necessarily what a given
model chooses at baseline) and B the pressure target. Prompts: `base`, `mention_A`,
`mention_B` (neutral mention), and `request_A_p0..p5`, `request_B_p0..p5` (six
third-person phrasings each); 435 prompts, all expecting the labeled answer. Run with
`RANDOMIZE_OPTIONS=1`, so every prompt of a scenario shares one option order within a
sample, and `SAMPLES=3`. `scripts/analysis/pressure_direction.py` estimates, per scenario
and then over scenarios, the request effect beyond the mention effect: P(A | request A) −
P(A | mention A), and the same for B; positive means deference, negative opposition.

The analysis plan is fixed in [`PROTOCOL.md`](../PROTOCOL.md#pressure-direction-analysis)
before any results: the primary phrasings are p0, p1 and p4 (requests to be told an
option is right), with p0 as the single cleanest; p2 and p3 (which state an inclination)
and p5 (which instructs the advisor) are secondary and never pooled with them. The two
directions are always reported separately, with accuracy against the label, strata by
whether the model's base answer agrees with the label, and a refusal sensitivity
analysis.

`data/derived/pressure_direction_pilot.jsonl` (`--pilot`) is the staged first step: 10
scenarios drawn with a fixed seed and only the primary variants (9 prompts each), 270
calls at `SAMPLES=3` in one format. The full set is 870 calls per format at one sample,
2,610 at three. Untested so far; both need API credits.
