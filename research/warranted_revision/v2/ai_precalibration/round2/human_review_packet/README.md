# Proposed small human review (not sent; awaiting approval)

23 items from candidate_v2:

- 13 **difficult**: every item the AI adjudicator saw, plus every item the AI auditor flagged at
  high or medium severity;
- 10 **controls**: drawn at random (seed 20261026) from the rest, stratified by label.

The selection rule was committed (`round2/analysis/compare.py`, commit 3e00f8f) before the
auditor's findings were read. Reviewers are not told which items are which.

**Status:** approved to prepare (2026-10-26); ready to send.

**What to send.** Send only `send_to_reviewer_A.zip` or `send_to_reviewer_B.zip`, one per
person, and do not give reviewers access to this repository: it contains the AI annotations,
the key and the audits. Each zip holds `START_HERE.md`, the guidelines, `base_checks.csv` and
`items.csv`, and asks reviewers not to use AI assistants.

**Scoring** (after both return):

1. `python -m warranted_revision.v2bench agree --key <this dir>/coordinator/key.json --a … --b …
   --out …` gives agreement and the blind-first adjudication files for a **human** adjudicator.
2. `python v2/ai_precalibration/round2/human_review_packet/score_humans.py --a … --b … --out …`
   compares the human answers with the gold and, separately, with the AI judgements.

Earlier text: Send each person only their own folder (`human_reviewer_A/` or
`human_reviewer_B/`, each holding the items, base checks and `GUIDELINES_v0.2.md`). Keep
`coordinator/key.json` private; its sha256 is in each `PACKET.txt`. Reviewers must not see any
AI annotation, adjudication or audit file.

**Effort.** About 45–60 minutes per reviewer, plus about 15 minutes for an adjudicator on the
disagreements (`v2bench agree` writes the blind-first adjudication files).

**What it answers** (questions AI agreement cannot):

1. On the 7 items where every AI judge agreed with a gold answer the AI auditor doubts
   (`eld-08`, `cc-06`, `hp-05`, `eb-10`, `sol-07`, `sol-01`, `cc-03`), do people side with the
   gold or with the auditor's alternative?
2. On the ambiguous and co-owner items, do people use `AMBIGUOUS` and `ask_or_conditional`
   where the models did, or do they commit to one reading?
3. On the controls, do people reproduce the computed gold? If not, the problem is wider than the
   flagged items.
4. Do reviewers' own `advisor_should` answers on unsupported claims endorse the hedging stance?

**Decision rule (fixed now).**

- If people disagree with the gold on more than 2 of the 10 controls, the item-writing process,
  not just the flagged items, needs revision before any B1.
- If they side with the auditor on most of the 7 shared-error candidates, those boundary
  principles in GUIDELINES_v0.2 need rewriting.

This is a small diagnostic, not B1's calibration gate.
