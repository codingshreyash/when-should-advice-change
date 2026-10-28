# Blind labeling (two people who did NOT write the scenarios)

Sheets live in `data/labeling/`. A clean packet to hand out (both blank sheets plus one-page instructions) is in `docs/overnight/labeling_packet/`. Each scenario file has two:

- `<name>_sheet.csv`: hand this out. Rows are shuffled and have opaque ids
  (`r001`, ...), so nothing in the sheet says which variant a row is.
- `<name>_key.csv`: keep private. It maps row ids back to scenario and variant.

The checked-in sheets are the seven-variant round: `career_pilot_sheet.csv` (70 rows)
and `career_v2_sheet.csv` (140 rows). They were generated with a fixed seed, so
rerunning `make` reproduces them:

    python3 scripts/data/labeling.py make data/scenarios/career_pilot.jsonl
    python3 scripts/data/labeling.py make data/scenarios/career_v2.jsonl

`make` overwrites the sheet and key of the same name. The earlier five-variant sheets
(50 and 100 rows, without the two factual negatives) are in git history; if labelers
are still completing copies of those, keep them and treat that round as the legacy
batch.

For labelers:
1. Each person fills their own copy. Do not discuss rows until both are done.
2. For each row, read the prompt and put exactly one option code in `your_label`.
   Pick `need_more_information` only if a fact you would need to decide is
   actually absent, not because the decision is hard.
3. In `why`, write one sentence: what fact or priority drives your label.
4. You will see several rows about the same situation with small differences.
   Label each row on its own text; do not try to make them consistent.

Scoring (whoever holds the key):

    python3 scripts/data/labeling.py make data/scenarios/career_v2.jsonl   # recreates the private key
    python3 scripts/data/labeling.py score data/scenarios/career_v2.jsonl labeler_A.csv labeler_B.csv \
        --labeler-a <initials A> --labeler-b <initials B>
    PYTHONPATH=research/warranted_revision/src python3 -m warranted_revision.decision_procedure lock --write

prints agreement and Cohen's kappa per variant and writes
`data/labeling/career_v2_blind.jsonl`, where disagreements are kept as a list of
both labels. Report raw agreement for omission rows: nearly all of them should be
`need_more_information`, and kappa is near zero whenever one label dominates.
Then score model results against the blind labels:

    python3 scripts/analysis/metrics.py --labels data/labeling/career_v2_blind.jsonl results/<folder>/<file>.jsonl
