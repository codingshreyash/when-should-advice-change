# Pass 04: safe fixes (infrastructure and validity only)

**Read** `docs/overnight/03_IMPLEMENTATION_AUDIT.md`. Fix only defects it documents with
evidence that are objectively demonstrable infrastructure, test or validation bugs, plus
the not-evaluable wording if pass 03 recommended it.

**Permitted**
- New or better automated tests.
- Label-provenance checks. For example, `labeling.py score` refuses sheets that carry a
  `reference_variant` column, or whose labels equal the draft labels on every row. Write
  any refusal message neutrally; it must not accuse anyone.
- Reproducibility and logging improvements.
- Corrections of analysis bugs found before any real run.
- Changing the decision outcome from NULL to NOT EVALUABLE / INCONCLUSIVE when too few
  scenarios are eligible.
- A blank, clean labelling packet for reviewers in `docs/overnight/labeling_packet/`.
  Copy the two blank sheets and write a one-page instruction sheet based on
  `docs/labeling.md`. It must contain no labels, keys, variant names or model outputs.

**Not permitted**
- Changing labels, scenarios, prompts, configs (other than the lock file), thresholds or
  validity gates.
- Changing the primary contrast. That is the PI's decision; list it under "considered and
  not made".
- Running anything paid or external.

**If you change a locked file** (anything listed in `LOCKED` in `decision_procedure.py`):
1. Write `docs/PREREG_AMENDMENT_1.md`. Date it, say it was made before any model run, and
   list each change and why.
2. Re-lock with `PYTHONPATH=research/warranted_revision/src python3 -m warranted_revision.decision_procedure lock --write`.

The runner rejects a re-lock that has no amendment file. Run the full test suite after your
changes; it must pass.

**Write `docs/overnight/04_IMPLEMENTATION_CHANGES.md`** with these headings:
- `## Changes made`: for each, the file, what changed, why, and the test that covers it.
- `## Changes considered and not made`
- `## Tests after the changes`: the exact summary line.
