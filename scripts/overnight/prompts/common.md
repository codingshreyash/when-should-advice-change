# Overnight research pass: rules (read first)

You are running one pass of a finite, unattended overnight queue on the repository
"When Should AI Advice Change?" (University of Pittsburgh CS 1684). Nobody is watching. A
runner script checks your output afterwards and rejects the pass if a rule below is broken.

**Where you are.** You are on a dedicated git worktree and branch made for this run. The
runner commits your work after verifying it; you never commit, push, merge, rebase, reset or
check out branches yourself.

**Hard rules**
1. **No paid or external compute.** No GPU launch, no Brev command, no model API call, no
   GitHub Actions dispatch, no `pip install`. CPU tests and dry runs are allowed.
2. **No changes to research inputs or records.** Never edit anything under `data/`,
   `results/` or `report/`, the scenario prompts, the frozen experiment configs, the
   preregistration, `docs/findings.md`, `PROTOCOL.md`, the negative methods report, or
   `scripts/overnight/`. Write only the files this pass names.
3. **Labels.**
   - No human labels exist. Never say or imply that they do.
   - Never treat AI-written or author-derived labels as human or independent labels.
   - The draft labels in the scenario files (`expected`) are the scenario author's.
4. **No invention.**
   - Every number you report must come from a command you ran in this pass, or from a
     file you cite by path.
   - If evidence is missing, write "not available" and say what would be needed. Do not
     estimate it.
   - Exploratory results are never presented as established findings.
5. **No outcome-driven design.** Do not propose changing scenarios, prompts, labels or
   validity gates because of how a model performed.
6. **Stop rather than guess.**
   - If the task cannot be done with the evidence in the repository, write the required
     output file anyway: say exactly what blocked you and stop.
   - Be skeptical, including of this project's own reports and of earlier overnight passes.
7. **Keep it short and decision-oriented.** Use the required headings exactly as given.
   Write no more than the task needs.

**Useful facts**
- The current experiment's design is in `docs/PREREGISTRATION_DECISION_PROCEDURES.md`.
- Its code is `research/warranted_revision/src/warranted_revision/decision_procedure*.py`.
- Its tests are `research/warranted_revision/tests/test_decision_procedure.py`.
- Run the tests with: `cd research/warranted_revision && python3 -m pytest -q`.
- Dry runs:
  - `PYTHONPATH=research/warranted_revision/src python3 -m warranted_revision.decision_procedure run --config research/warranted_revision/configs/decision_procedure_full.json --dry-run`
  - `python3 research/warranted_revision/gpu/brev_controller.py plan --hourly 1.06 --max-usd 3 --run-id audit --instance-type massedcompute_L40S --config research/warranted_revision/configs/decision_procedure_full.json --state /tmp/overnight_plan.json`
  - Both are offline; neither calls Brev.
- Legacy raw results: `results/career/*.jsonl`. Each row has `model`, `id`, `variant`,
  `choice`, and `probs` (scorer rows).
- Scenarios: `data/scenarios/career_pilot.jsonl`, `data/scenarios/career_v2.jsonl`.
  Pressure and neutral-mention controls: `data/derived/pressure_controls.jsonl`.
- Budget: $95 project total. About $4.22 of GPU spending is known, and the remaining
  ≈ $90.78 assumes no unrecorded spending
  (`results/warranted_revision/PROJECT_LEDGER.md`). $5 is allocated to the
  decision-procedure experiment, unspent.
