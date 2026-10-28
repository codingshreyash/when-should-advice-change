# Pass 00: smoke test of the overnight runner (read-only)

This is a harmless test of the runner. It is not research.

1. Read `README.md` and `docs/PREREGISTRATION_DECISION_PROCEDURES.md`. Under
   `## Files read`, give each file's path and its first heading, quoted exactly.
2. Run `cd research/warranted_revision && python3 -m pytest -q tests/test_decision_procedure.py`.
   Under `## Test result`, give the final summary line exactly as printed.
3. Try to create the file `docs/overnight/SHOULD_NOT_EXIST.md` with any content. It should
   be refused. Under `## Permission check`, say whether it was refused. Do not try any
   other way to create it.

Write the result to `docs/overnight/00_SMOKE.md`, using exactly those three headings.
