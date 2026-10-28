# Morning brief, overnight run 2026-10-28

Sources: `.overnight/RUN_STATUS.md` (authoritative), `docs/overnight/00`–`04`, the ledger.
Shell access was denied to this pass, so I did not run `git log`, `git show` or the tests. The
commit IDs below come from the run status and the `git log` read at the start of this pass.
**No human labels exist.** Every accuracy or eligibility figure uses the scenario author's
draft labels (`expected`).

## 1. Completed overnight
Passes 01–04 are `done` after 1 attempt each, and the runner committed each one. Pass 05
(this brief) is `running`. No pass failed or was retried.
- 01: an independent research verdict.
- 02: legacy 9B evidence, recomputed from raw rows.
- 03: an audit of the four-arm implementation.
- 04: fixes to infrastructure and validity code, plus a labeling packet.

## 2. New findings supported by evidence
All of these are exploratory: one sample, a fixed option order, draft labels, Nimble at `bd792f44`.
- Every 9B cell in `docs/findings.md` §2 and §4.1 reproduces from raw rows. However, §2's stated
  source script does not print "base correct" or the d′ CIs (`02_EXISTING_EVIDENCE.md`).
- No 9B model has `mention_target` or `irrelevant_update` rows. Qwen "deference" therefore
  cannot be told apart from lexical priming (`02`, `01` claim 1).
- When the choice held under pressure, P(pressure target) still rose: Nimble 19/19, Qwen 9/11.
  For reframes the reference rates are 18/27 and 10/18. There is no neutral-mention control
  (`02`).
- Qwen asks `need_more_information` at similar rates on omission (10/30), complete base (8/30)
  and reframe (12/30) prompts. Nimble never asks (0/150) (`02`).
- Several claims are overstated: README and midterm "deference", Haiku "opposition", Sonnet's
  "exact" boundaries, and novelty statements (`01`). None of the cited papers could be opened.
  All are **unverified** (`01`).
- The implementation has 3 blocking defects. Draft labels were accepted as blind labels. Two
  identical sheets were scored as two labelers. Labels are neither required nor locked before a
  run (`03` findings 1–3).
- At the $3 cap, the on-box gate would refuse the full run by the code's own estimates:
  66.2 min left against 90.3 needed (`03` finding 9).

## 3. Tests run
- Pass 01: "**170 passed**".
- Pass 03: `170 passed in 72.98s (0:01:12)`.
- Pass 04, first run: `1 failed, 176 passed in 80.99s (0:01:20)`. The failure was the bundle
  test; `test_labeling.py` now skips when the script is absent.
- Pass 04, final run: `177 passed in 82.19s (0:01:22)`.
- Dry runs (passes 01, 03, 04): 4,800 confirmatory calls plus a 64-call preflight, "no model
  loaded", no lock drift. The plan's worst case is `worst_case_usd 2.4`, and it reports "no
  provider call was made".

## 4. Files changed and commits
- `d39c705` 01: `01_RESEARCH_VERDICT.md`.
- `7e668fd` 02: `02_EXISTING_EVIDENCE.md` and `analysis/legacy_9b_reanalysis.py`.
- `b4fa517` 03: `03_IMPLEMENTATION_AUDIT.md` and `analysis/03_audit_checks.py`.
- `aaa8827` 04 (files as listed in `04`):
  - `scripts/data/labeling.py`;
  - `decision_procedure_analysis.py` (locked; re-locked in `decision_procedure_lock.json`);
  - `tests/test_decision_procedure.py` and the new `tests/test_labeling.py`;
  - the new `docs/PREREG_AMENDMENT_1.md`;
  - `docs/overnight/labeling_packet/` (2 blank sheets and `INSTRUCTIONS.md`).

I could not confirm per-commit file lists with `git show`. The lists above are from the pass
reports.

## 5. Problems and blockers
- `run()`, the pilot and the job still do not require locked labels (`03` findings 3 and 11;
  not fixed in `04`). The pilot could print outputs before labelling.
- The $5 cap is not enforced in code. The $3 plan likely cannot pass the on-box gate (`03`
  findings 8–9).
- Amendment 1 changed a locked file and the §8 vocabulary (NOT EVALUABLE). **The PI has not
  reviewed it.**
- The literature remains unverified. Arxiv and ACL fetches were refused (`01`).

## 6. Is the four-arm experiment defensible
Yes, as a labels-gated course study. It is not defensible as a publication.

**Agree with `00`:**
- labels are the highest-value step;
- D vs A is largely predictable, and D vs B is the more useful contrast (a PI decision);
- the likely outcome is "inconclusive at this precision";
- no GPU overnight.

**Disagree with `00`, or need to qualify it:**
- `00` calls the probability shift "real" and "the most robust" result. `02` supports only the
  held-choice counts, without a neutral-mention control and with a non-trivial reframe base
  rate, so it stays exploratory.
- `00`'s "8/30 complete base prompts" is 7 unneeded asks if the draft label for `career_10`
  holds (`02`).
- `00` missed two things:
  - D uses checkpoint `594dfdcf`, not `bd792f44`, so D − A does not replicate the legacy
    result (`01`);
  - the code accepted draft labels as blind labels, and $3 likely cannot complete the run
    (`03`).

## 7. Needs human input
- **Labels:** two non-author labelers fill the sheets in `docs/overnight/labeling_packet/` and
  sign the attestation. Nothing confirmatory can happen without them.
- **PI decisions:**
  - review Amendment 1;
  - A2: require locked labels before any run, the pilot included;
  - A4: fixed Holm families;
  - A5: the $5 cap and the confirmatory cap, set from the pilot's timing;
  - whether D vs B becomes primary (pre-run);
  - verify the cited papers;
  - correct the overstated claims in the README and the midterm.

## 8. Single next action
The PI decides A2 and reviews Amendment 1. Then the labeling packet goes to two non-author
labelers. This costs $0.

## 9. Budget
The run status shows no GPU, Brev or paid API calls tonight.
- Ledger: ≈ $90.78 of $95 remains, provided no unrecorded prior spending counts. The cost of
  the earlier Claude API calls is **unknown**.
- The $5 decision-procedure allocation is unspent.

## 10. Verdict
GO, for the course study only, gated in the stated order: PI decisions, then labels, then the
pilot, then the full run.

The stop conditions in `00` and `01` apply:
- labels are not complete within 7 days or before the report draft;
- the pilot gate fails twice;
- the run needs more than $5;
- fewer than 15 eligible scenarios gives NOT EVALUABLE, and the study is written up as it
  stands.

VERDICT: GO
