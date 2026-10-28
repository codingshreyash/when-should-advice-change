# Pass 03: technical and statistical audit of the four-arm experiment

**Inspect:**
- `research/warranted_revision/src/warranted_revision/decision_procedure.py`
- `research/warranted_revision/src/warranted_revision/decision_procedure_analysis.py`
- `research/warranted_revision/gpu/brev_controller.py`
- `research/warranted_revision/gpu/decision_procedure_job.sh`
- `research/warranted_revision/gpu/remote_job.sh`
- `research/warranted_revision/configs/decision_procedure_*.json`
- the lock file
- `scripts/data/labeling.py`
- the preregistration

**Run** the full CPU test suite, the dry run and the offline controller plan (commands are
in the rules). Report the exact summary lines.

**Look for defects that would invalidate a result.** Show evidence for each one (file:line
and a command or a minimal reproduction):
- label leakage, or acceptance of author-derived or AI labels as blind labels (for
  example, can `labeling.py score` produce a `*_blind.jsonl` from two copies of the
  draft labels?);
- wrong eligibility denominators;
- invalid responses silently disappearing from the analysis;
- option orders that differ across variants or arms;
- incorrect paired tests, bootstrap or Holm;
- GPU cleanup or spending-cap failures in the controller path;
- frozen inputs that could change without the lock noticing.

**Required topic.** The preregistration (§4, §8) calls a study with fewer than 15 eligible
scenarios a "NULL" of kind "not evaluable". Assess whether that should be an
INCONCLUSIVE / NOT EVALUABLE outcome instead of a null, and draft the exact wording of a
pre-run amendment.

**Write `docs/overnight/03_IMPLEMENTATION_AUDIT.md`** with these headings:
- `## Tests and dry runs executed`
- `## Findings`: a table with severity (blocking / should-fix / minor), evidence, and
  proposed fix.
- `## Eligibility and the not-evaluable outcome`
- `## Recommended pre-run amendments`: for each amendment, mark whether it needs the PI's
  decision (any change to the primary contrast does).

Do not modify code in this pass.
