# Pass 05: morning brief

**Read:**
- `docs/overnight/00_INITIAL_ASSESSMENT.md`;
- every `docs/overnight/0*.md` produced tonight;
- `.overnight/RUN_STATUS.md`, the runner's own record of passes, attempts, failures and
  commits. Treat it as authoritative about what ran.
- `git log --oneline -15`.

A pass missing from the run status did not complete; say so. Do not summarise work that was
not done.

**Write `docs/overnight/MORNING_BRIEF.md`** with exactly these headings:
- `## 1. Completed overnight`
- `## 2. New findings supported by evidence`: each with its source file.
- `## 3. Tests run`: the exact summary lines, quoted from the pass reports.
- `## 4. Files changed and commits`
- `## 5. Problems and blockers`
- `## 6. Is the four-arm experiment defensible`: say where you agree and disagree with
  `00_INITIAL_ASSESSMENT.md`.
- `## 7. Needs human input`: the human labels, and any PI decisions.
- `## 8. Single next action`
- `## 9. Budget`: no GPU or API spending happened tonight, unless the run status shows
  otherwise. Give the remaining estimate from the ledger.
- `## 10. Verdict`

The last line of the file must be exactly one of `VERDICT: GO`, `VERDICT: NO-GO` or
`VERDICT: INCONCLUSIVE`:
- **GO** means: finish the course study (labels, then pilot, then full run).
- **NO-GO** means: stop the experiment and write up what exists.
- **INCONCLUSIVE** means: the overnight evidence is not enough to decide. Say what is
  missing.

Keep it to about one page.
