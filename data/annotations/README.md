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
