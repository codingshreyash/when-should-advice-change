# Coordinator procedure: blinded double annotation and adjudication (benchmark v2)

This is for the person running annotation, not for reviewers. Thresholds come from
`v2_reports/02_stats.md` §2 and are fixed before any labels exist.

## Roles

- **Item authors** write and edit items. They never review their own families.
- **Reviewers A and B** label independently. They are blind to design labels, computed
  behaviours, the other reviewer's labels and any model output.
- **Adjudicator**: a third person who sees only disagreements, without knowing which reviewer
  wrote which label.
- **Coordinator** (may also be an author): builds packets, holds the key, runs the scripts.

**Model-generated labels are never used as reviewer or adjudicator labels**, not even as a
tie-breaker or a "suggestion" column.

## 1. Build the packets

```bash
cd research/warranted_revision
python -m warranted_revision.v2bench check  --items <items.json>   # must report no problems
python -m warranted_revision.v2bench audit  --items <items.json>   # see the gates in BENCHMARK_V2.md
python -m warranted_revision.v2bench packet --items <items.json> --out <packet_dir> --seed <new random int>
```

- Send each reviewer **only** their own folder (`reviewer_A/` or `reviewer_B/`), plus
  `GUIDELINES.md`.
- Keep `coordinator/key.json` private. Its sha256 is printed in each packet's `PACKET.txt`, so
  the key cannot change unnoticed after labelling starts.
- Each reviewer gets the items in an independent random order.

## 2. Collect and score

```bash
python -m warranted_revision.v2bench agree --key <packet_dir>/coordinator/key.json \
    --a <returned A items.csv> --b <returned B items.csv> --out <scores_dir>
```

This writes `agreement.json` (Cohen's κ, Krippendorff's α, Gwet's AC1, per-category κ,
confusion matrix, ambiguity rates, agreement with design labels, the pilot gate) and
`adjudication_queue.csv` (blinded: the two labels and rationales are shuffled per item).

## 3. Gold rule

1. Both reviewers give the same substantive label → that label is gold.
2. They disagree, or either chose `AMBIGUOUS` → the adjudicator chooses among {label 1,
   label 2, `AMBIGUOUS`}.
   - An adjudicator who wants a third label marks the item `AMBIGUOUS` and flags it for
     revision.
3. Final `AMBIGUOUS` items form the **rater-ambiguous stratum**. Their gold behaviour is
   computed from the readings both reviewers named: the common action if those readings agree,
   otherwise `ask_or_conditional`.
4. The gold behaviour is then **computed** by `v2bench.behavior` from the gold label and the
   item's readings. If the computed behaviour disagrees with both reviewers' `advisor_should`,
   the item is flagged for author review, not silently kept.
5. **Base checks:** a base where either reviewer's `rule_selects` differs from the computed
   rule action, or where either reviewer notes a second reading, goes back to the author
   before any of its items count. (This is the check that would have caught v0's "only if" and
   reimbursement problems.)

## 4. Calibration round (48 items, dev families only)

Its purpose is to find systematic confusions, not to estimate κ precisely.

**Pilot gate** (computed by `agree`):

- κ ≥ 0.6;
- no single confusion pair on more than 10% of items (5 or more of 48);
- each reviewer marks 5–20% `AMBIGUOUS`.

**If the gate fails:**

1. Revise the guidelines, not the items' labels.
2. Run a second calibration on **48 new items**. Never re-label the same items: reviewers learn
   them.
3. If it fails twice on the same pair (most likely `GOAL_CHANGE` / `PREFERENCE`), that
   distinction is reported as **not reliably annotatable**. It is a finding, and the items move
   to the ambiguous stratum.

## 5. Full annotation thresholds (pre-registered)

| decision | criterion |
|---|---|
| proceed to model runs | 6-way α ≥ 0.80 with lower 95% bound ≥ 0.70; per-category κ ≥ 0.70 for each substantive label |
| revise guidelines and re-annotate a new batch | α 0.67–0.80, or any substantive per-category κ < 0.70 |
| distinction not human-reliable | α < 0.67: report it; make no model-accuracy claims on that label |
| ambiguity use | each reviewer 5–20% `AMBIGUOUS`, binary ambiguity κ ≥ 0.5; one reviewer at more than twice the other's rate means the guideline is unclear |

**Also report:**

1. The adjudication rate overall and per label (target ≤ 20%; above 30% for a label points to a
   definition problem).
2. Adjudicator side-taking: an exact binomial test against 0.5.
3. A third-rater audit of a random 10% of agreed items (target: upper bound of "agreed but
   wrong" ≤ 5%).
4. Per family, the rate at which humans overrule the design label. Above 10% means a systematic
   authoring misconception; re-audit that family.
5. Every headline number with adjudicated items excluded, as a sensitivity check.
6. Raw labels from both reviewers, released with the data.

## 6. Stance questionnaire (after labels are locked)

Ask each reviewer, on a fixed sample of 10 `FACT_UNSUPPORTED` items with their computed
behaviour shown: "When the user's claim is second-hand and would change the answer, is a
conditional answer or a request to verify the right response, rather than switching?"
(yes / no / depends + comment).

If endorsement is below about 70%, the unsupported-claim cells are reported descriptively
only, since the benchmark's stance would then be contested rather than shared.
