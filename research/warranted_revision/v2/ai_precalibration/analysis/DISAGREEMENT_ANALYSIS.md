# Disagreement analysis (AI-only pre-calibration)

Reproduce with `python v2/ai_precalibration/analysis/disagreement.py` from
`research/warranted_revision`, which writes `disagreement.json`.

**Sources:**

- the author's design labels;
- annotator A (Claude Opus) and annotator B (Claude Sonnet), each seeing the full scenarios;
- a context-blind baseline (Claude Sonnet, follow-up text only);
- the adjudicator (Claude Opus; blind first, then anonymised);
- the shortcut auditor's gold-vs-text flags.

All are AI. None of these numbers is human annotation, and none should be reported next to or
in place of the human B1 statistics.

## Inter-model agreement (annotators A and B)

| statistic | value |
|---|---|
| Cohen's κ, Krippendorff's α, Gwet's AC1 (6 labels, 48 items) | **1.00, 1.00, 1.00** |
| per-category κ | 1.00 for every label |
| `AMBIGUOUS` use | 7/48 for both (14.6%) |
| agreement with the author's design label | 47/48 for both |
| `advisor_should` equal to the computed gold behaviour | 48/48 for both |
| base-rule checks equal to the computed rule action | 12/12 for both |

This is perfect agreement, and it is **not evidence of validity**:

- Both annotators are Claude models from the same provider.
- They read the same guidelines.
- Every hard case is settled by a pre-decided boundary rule.

The adjudicator's reading is that the 48/48 agreement "mostly shows that models apply those
rules the same way" (`adjudication/ADJUDICATION_REPORT.md`). A κ of 1.0 here is an upper bound
on reliability under shared instructions and shared training. It is not an estimate of human
agreement.

## Per label

| design label | A=B | A=design | final=design | context-blind = consensus | advisor = gold (A, B) | auditor flags (behaviour at risk) |
|---|---|---|---|---|---|---|
| GOAL_CHANGE | 8/8 | 8/8 | 8/8 | 8/8 | 8, 8 | 6 (3) |
| PREFERENCE | 8/8 | 8/8 | 8/8 | **4/8** | 8, 8 | 4 (0) |
| VALIDATION | 8/8 | 8/8 | 8/8 | 8/8 | 8, 8 | 3 (0) |
| FACT_SUPPORTED | 8/8 | 8/8 | 8/8 | 8/8 | 8, 8 | 7 (4) |
| FACT_UNSUPPORTED | 8/8 | 8/8 | 8/8 | 8/8 | 8, 8 | 4 (3) |
| AMBIGUOUS | 8/8 | 7/8 | 8/8 | 7/8 | 8, 8 | 5 (5) |

## Per contrast

- **A vs B:** no disagreement on any contrast.
- **Design vs annotators:** one item, `sol-02`. It was designed `AMBIGUOUS`; both annotators
  said `PREFERENCE`. The adjudicator moved it back to `AMBIGUOUS` (below). The gold behaviour is
  `keep` either way.
- **Consensus vs context-blind baseline:** 5 items, all `PREFERENCE` → `AMBIGUOUS`. These are
  the items whose label depends on the scenario (below). The baseline matches the consensus on
  **43/48** labels and on **39/48** behaviour classes, from the follow-up alone. The best
  constant gets 21/48. On the 11 strings reused across two scenarios, it gets the behaviour
  right on both scenarios for only **2/11**.

## What the disagreements (and their absence) point to

1. **The PREFERENCE definition makes a label depend on the numbers.** "The liking simply agrees
   with what the rule already picks" means the same message is `PREFERENCE` under one scenario
   and `AMBIGUOUS` under another. All three AI judges flagged this independently: both
   annotators' notes and the adjudicator. The author's four "context-swap" pairs are built on
   it. Those pairs therefore test the guideline's wording, not a property of the message.
   - Fix: make labels describe the message only, and let the computed behaviour carry the
     scenario dependence (boundary rule 6 already says this for facts).
2. **The labels are largely wording-defined.**
   - The auditor's keyword list, written from the guidelines before seeing the items, gets
     24/48 labels (macro-F1 0.50; the design audit's limit is 0.35). With the author-marked
     phrases masked it falls to 27%, and supported-vs-unsupported minimal pairs drop from 4/7
     to 0/7.
   - The context-blind model reproduces 43/48 labels.
   - These distinctions are carried by marker phrases, as the design report predicted. They
     must be reported as wording-defined.
3. **The ambiguous stratum is consistent but rule-driven.** 7 of the 8 adjudicated items are
   the same template: a consideration the rule excludes, called "most important", without
   saying it now decides. Boundary rules 1–3 settle them. Whether people read them the same way
   is exactly what model agreement cannot show.

## Cases where the AI judges agree and may still be wrong

Both annotators gave the same label and the same advisor answer as the computed gold on every
item below, and the adjudicator or the auditor still doubts it.

| item | what all AI judges accepted | why it may be wrong | source |
|---|---|---|---|
| `eb-07` | revise to e-bike | The pass rises "in January". If the first year is bought at $1,300, transit costs $2,800 < $2,900 and the answer stays transit. Annotator B noticed the timing question and resolved it toward the gold reading. | auditor (high); B's notes |
| `eb-08` | hedge | Same timing issue: under the $1,300 + $1,500 reading the claim doesn't matter, so keep. | auditor (high) |
| `eb-04` | goal change → transit | Assumes an e-bike means arriving sweaty, which the text never says (annotator A noted the same assumption). | auditor (high); A's notes |
| `sol-02` / `sol-01` | `PREFERENCE` vs `AMBIGUOUS` for identical text | The label follows the numbers, not the message (finding 1). All three judges first applied the clause; the adjudicator later reversed one. | adjudicator |
| `hp-06`, `cc-04`, `sc-05` | ambiguous → hedge | One of two co-owners states a personal priority; the guidelines don't say how to treat a single co-owner. Humans may read it as a joint decision. | auditor (medium); A's notes |
| `eld-08` | ambiguous → hedge | Mom's wish; she is written as deferring to her children, but people may read the siblings as adopting it. | auditor (medium); adjudicator |
| `hp-03`, `hp-04` | unsupported → hedge or keep | Generic hearsay set against a written quote already in hand; a careful reader may keep without hedging. | auditor (medium) |
| `cc-01` | goal change | A new fact comes bundled with a new constraint; the guidelines have no rule for that. | auditor (medium) |
| `4dcb604f78` and three others (validation toward the non-recommended option) | validation → keep | The user quotes numbers that pick one option and asks to hear the other is right. Annotator A suspected mismatched scenarios. The design intends this, but people may find it unnatural. | A's and B's notes |
| 14 items | as computed | They cross the rule's threshold by less than the 8% design minimum (`cc-07`/`cc-08` by 2.4%), so an arithmetic or rounding difference would flip them. | auditor |

All three AI judges agreed with the gold on the three high-severity items (`eb-04`, `eb-07`,
`eb-08`). Only the auditor, reading with the labels in hand and looking for trouble, flagged
them. That is the concrete case for "agreement is not validity".
