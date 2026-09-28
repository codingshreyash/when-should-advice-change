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
