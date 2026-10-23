# Annotations

`pressure_sentence_audit.csv`: each authored `pressure` sentence in the 30 career
scenarios, coded against the study's definition of pressure (a request to endorse an
option that adds no fact and changes no stated priority):

- `request_only`: only asks to be told an option is right (15)
- `inclination`: also states a leaning, e.g. "They're leaning toward..." (5)
- `reason_or_feeling`: also gives a feeling or reason that could be read as
  decision-relevant, e.g. "scared of moving" (10)

This is a single-coder draft and should be checked during blind labeling.
`scripts/analysis/report_tables.py` uses it to show that pressure shifts are not
concentrated in the ambiguous sentences.

`relevant_update_types.csv`: what each scenario's `relevant_update` changes (single-coder
draft, with the edit itself for checking):

- `fact` (24): a fact about the world changes (a salary, a deadline, an offer).
- `priority` (2): the person's stated priority or goal changes (career_11, career_13).
- `plan` (2): the person's own plans change (career_17, career_29).
- `mixed` (2): a priority and a fact change together (career_02, career_16).

Updating for a changed fact and for a changed goal are different abilities; with six
non-fact items the split is descriptive only. `scripts/analysis/metrics.py` prints
relevant-update results by type.
