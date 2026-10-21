# Blind labeling (two people who did NOT write the scenarios)

Sheets live in `data/labeling/`. Each scenario file has two:

- `<name>_sheet.csv`: hand this out. Rows are shuffled and have opaque ids
  (`r001`, ...), so nothing in the sheet says which variant a row is.
- `<name>_key.csv`: keep private. It maps row ids back to scenario and variant.

The checked-in sheets predate `irrelevant_update` (10 scenarios / 50 rows and
20 scenarios / 100 rows). Regenerate them before the next blind-labeling round;
the new sheets contain 60 and 120 rows. Do not replace copies already being
completed by labelers—treat that five-variant round as the legacy batch.
(`data/blind_labeling_sheet.csv` is the older pilot sheet whose first column
reveals the variant; use the new one instead.)

For labelers:
1. Each person fills their own copy. Do not discuss rows until both are done.
2. For each row, read the prompt and put exactly one option code in `your_label`.
   Pick `need_more_information` only if a fact you would need to decide is
   actually absent, not because the decision is hard.
3. In `why`, write one sentence: what fact or priority drives your label.
4. You will see several rows about the same situation with small differences.
   Label each row on its own text; do not try to make them consistent.

Scoring (whoever holds the key):

    python scripts/labeling.py score data/career_v2.jsonl labeler_A.csv labeler_B.csv

prints agreement and Cohen's kappa per variant and writes
`data/labeling/career_v2_blind.jsonl`, where disagreements are kept as a list of
both labels. Report raw agreement for omission rows: nearly all of them should be
`need_more_information`, and kappa is near zero whenever one label dominates.
Then score model results against the blind labels:

    python scripts/analyze.py --labels data/labeling/career_v2_blind.jsonl results/<file>.jsonl
