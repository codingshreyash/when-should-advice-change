# AI-only pre-calibration: report and recommendation

**Scope.** Everything here comes from AI agents (Claude models, one provider). It is not human
annotation. B1's human gate has **not** been run or passed, and nothing here moves the study to
B2 or B3. Inter-model agreement is reported only as a screening signal.

## What was done

1. **Scenario author.** It rewrote the 48 calibration items: `candidate_v1/items.json`, 6 dev
   families, 12 bases.
   - Behaviours: KEEP 44%, REVISE 27%, HEDGE 29%.
   - 11 strings are reused across two bases. The author counts 10 as changing behaviour; the
     auditor counts 9, scoring switch versus stay.
   - Every item marks its decision-relevant phrase (`marker_span`).
2. **Two independent annotators** labelled the items through blinded, independently shuffled
   packets: A on Claude Opus, B on Claude Sonnet. They are different models from the same
   provider; a second-provider annotator needs approval (`PROVIDER_PLAN.md`).
3. **A context-blind baseline** (Claude Sonnet) labelled the follow-ups without their scenarios.
4. **The adjudicator** labelled the 8 disputed items blind (frozen), then saw both anonymised
   annotations and gave a cause for each.
5. **The adversarial auditor** tried to solve the set from surface cues and reviewed every
   item's gold against its text.

Each step's output was committed before the next step could see it. Tooling: `v2bench`
check, packet, agree and audit.

## Isolation check

Isolation was by instruction, not enforced. Every agent's own tool calls were then searched for
forbidden paths (`analysis/isolation_check.py`).

| agent | tool calls | hits | after inspection |
|---|---|---|---|
| annotator A | 8 | 0 | — |
| annotator B | 6 | 0 | — |
| context-blind baseline | 5 | 0 | — |
| adjudicator, blind phase | 5 | 0 | — |
| adjudicator, phase 2 | 8 | 1 ("coordinator") | false positive: the word appears in its report text, not a path |
| auditor | 22 | 3 (AUTHOR_NOTES, audit_run, agreement/) | false positives: its own sentence "I did not read AUTHOR_NOTES.md, the audit_run*.json files", and a regex comment "agreement/reassurance" |

No forbidden file was opened in any tool call. This can't rule out other leakage, and the
substring method produces false positives that have to be inspected by hand.

## Findings

1. **The AI annotators agreed perfectly, and that is the least informative result.**
   - κ = α = AC1 = 1.00 on 48 items.
   - The same 7 items were marked ambiguous.
   - Advisor answers matched the computed gold on 48/48, and every base-rule check was right.

   The adjudicator agreed blind on all 8 disputed items. The agreement comes from shared
   guidelines whose boundary rules settle every hard case, plus a shared model provider. It does
   not show that people would agree, or that the labels capture the construct.
2. **The labels are wording-defined.**
   - A keyword list written from the guidelines alone gets 50% of labels (chance 17%; it fails
     the design audit's keyword limit).
   - A model that never sees the scenario reproduces 43/48 labels and 39/48 behaviour classes
     (best constant 21/48).
   - Masking the author-marked phrases removes most of the signal, and supported vs unsupported
     minimal pairs go from 4/7 to 0/7.

   Supported/unsupported and goal change/preference **are** their marker phrases, as the design
   report predicted. What the set can test about them is whether a model *respects an explicitly
   stated standing*. It can't test whether a model *infers* standing.
3. **What does require context is the decision consequence, and arithmetic carries much of
   it.**
   - On the reused strings, the context-blind model gets both scenarios right on only 2/11.
   - The auditor's best cheap context policy (recompute with any new number, hedge on hearsay
     words or on a message naming the other option) reaches 64.6% overall, against 43.75% for
     the constant.
   - No cheap policy solves more than 5 of the 11 reused strings.
   - So the pairs test "does the answer follow the decision consequence rather than the
     wording": the paired-base sensitivity question (PROTOCOL_v0.2 H-M1). They do this mostly
     through arithmetic and conflict-spotting, because the pairs never vary how well-founded a
     message is.
4. **A guideline defect, found independently by all three AI judges.**
   - The PREFERENCE definition ("the liking agrees with what the rule picks") makes identical
     messages get different labels depending on the numbers.
   - The author's four context-swap pairs are built on that clause.
   - Labels should describe the message, and the computed behaviour should carry the scenario
     dependence.
5. **Item defects the agreement missed.** All AI judges accepted the gold on three items the
   auditor rates high severity:
   - `eb-07` and `eb-08`: timing of a price rise; under a plausible reading the answer stays
     transit;
   - `eb-04`: an unstated assumption that an e-bike means arriving sweaty.

   Eleven more are medium:
   - single co-owners and non-owners stating goals;
   - generic hearsay set against a quote in hand;
   - a fact bundled with a constraint;
   - others.

   14 items also cross their threshold by less than the 8% design minimum. Two cells the design
   requires are missing: large supported changes to quantities outside the rule, and supported
   changes below the threshold. Details are in `analysis/DISAGREEMENT_ANALYSIS.md` and
   `audit/SHORTCUT_AUDIT.md`.

## Recommendation

**Not ready for human validation of the full construct. It is promising enough to justify one
more AI round followed by a small, targeted human check.**

**What survives:**

- The pipeline works end to end: computed gold, blinded packets, blind-first adjudication,
  audits.
- The paired-base design does force the scenario to matter for behaviour.
- An ambiguous stratum can be identified consistently, at least by models.

**What doesn't:**

- The goal/preference and supported/unsupported distinctions can't be tested without their
  marker phrases.
- One guideline clause turns labels into a function of the numbers.
- Three or more gold behaviours depend on assumptions the text doesn't support.

**Before any human time is spent:**

1. **Fix the guidelines.** Drop the outcome clause from PREFERENCE (labels describe the message
   only). Add rules for a single co-owner, a fact bundled with a constraint, and validation
   aimed at the non-recommended option.
2. **Author candidate_v2.**
   - Rewrite or drop the 14 flagged items and widen the thin margins to ≥8%.
   - Add the missing cells.
   - Vary well-foundedness within paired strings, so the pairs need more than arithmetic.
   - Record the wording-defined contrasts as such.
3. **Run the same AI round on v2**, including the second-provider annotator if approved. Keep
   v1's results as they are; do not rewrite prompts until the models agree.

**Then use people only for what AI agreement can't settle:**

- A targeted human check of about 25 items, with two reviewers at about one hour each:
  - the ambiguous stratum;
  - the boundary-rule 1–3 items;
  - the co-owner items;
  - the unsupported-claim stance (blind `advisor_should`).
- If people split where the models agreed, the boundary rules are the problem, and the full B1
  calibration must be redesigned before it runs.

**What the study can now honestly claim to be building.** A benchmark of whether models make
their recommendations follow the *decision consequence* of a message, including recognising and
surfacing genuine ambiguity, rather than its wording. It is not a benchmark of whether models
infer unstated changes of goals or evidential standing; that part is not supported.
