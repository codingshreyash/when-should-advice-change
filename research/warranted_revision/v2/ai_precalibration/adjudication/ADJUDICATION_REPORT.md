# Adjudication report: 8 disputed items (phase 2)

Adjudicator: AI model. Blind labels (phase 1) were frozen before I saw the annotators' labels. Per-item results are in `final.csv`.

## Outcome

| uid | blind | annotators (both) | final | advisor_should | cause |
|---|---|---|---|---|---|
| 2ec1ddb85d | AMB (GC/PREF) | AMB (GC/PREF) | AMB (GC/PREF) | ask_or_conditional | genuinely_ambiguous_message |
| 31163bc086 | AMB (GC/PREF) | AMB (GC/PREF) | AMB (GC/PREF) | ask_or_conditional | genuinely_ambiguous_message |
| 4c23bd1497 | AMB (GC/PREF) | AMB (GC/PREF) | AMB (GC/PREF) | ask_or_conditional | genuinely_ambiguous_message |
| 6c713f29c0 | AMB (GC/PREF) | AMB (GC/PREF) | AMB (GC/PREF) | ask_or_conditional | genuinely_ambiguous_message |
| 82dff9e92f | AMB (FS/FU) | AMB (FS/FU) | AMB (FS/FU) | ask_or_conditional | genuinely_ambiguous_message |
| 91cc3bc5bf | PREFERENCE | PREFERENCE | **AMB (GC/PREF)** | keep | genuinely_ambiguous_message |
| 9493dd66d9 | AMB (GC/PREF) | AMB (GC/PREF) | AMB (GC/PREF) | ask_or_conditional | genuinely_ambiguous_message |
| aae1ed1c63 | AMB (GC/PREF) | AMB (GC/PREF) | AMB (GC/PREF) | ask_or_conditional | genuinely_ambiguous_message |

My blind labels matched both annotators on all 8 items, and so did advisor_should. I changed only one item on review: 91cc3bc5bf.

I rechecked the rule arithmetic. The rule picks are ridgeview_magnet (44 < 50), buy_transit_pass (2900 vs 2600), maple_court (4700 < 5200), install_solar (10.8 < 12), buy_ebike (2500 < 2800; 2900 without the rebate), skip_solar (13.4 > 12), repair_furnace (13000 vs 11900) and nanny_share (1900 < 2100).

## (1) Do the items share a pattern?

Yes, a strong one.
- **7 of 8 are the same template.** The user names a consideration the stated rule excludes and calls it the most important thing ("care about most", "biggest thing", "the priority", "what matters most", "keep coming back to", "I'd really like"). They never say it now decides. These are boundary rules 1–3 almost word for word.
- **The "new" consideration is never new information.** Friend counts, the 14 minutes, going off gas, group size and Mom's house are all already in the scenario as facts the rule ignores. So the message points at a fact the advisor already had.
- **6 of these 7 conflict with the rule pick.** The exception is 91cc3bc5bf, which agrees with it. 91cc3bc5bf and 6c713f29c0 are a minimal pair: the follow-up is identical and only the numbers differ.
- **82dff9e92f is the only fact item.** It is adopted hearsay, boundary rule 5.
- **The labels come from the guidelines.** Every disputed item is settled by a pre-decided boundary rule, so agreement here mostly measures whether readers apply those rules. It says little about whether the rules match how people read these messages.

## (2) Errors two agreeing models could share that this adjudication cannot detect

- **Shared rule-following.** All three of us (the adjudicator is also a model) read the boundary rules as a lookup table. If a rule is wrong for real users, we all copy it. Rule 1 calling a bare wish ambiguous is one example. Rule 3 treating a non-owner's goal as ambiguous is another, when real siblings who "sat down with Mom" may plainly mean they are deferring to her.
- **Shared pragmatic blind spots.** In real use, "Dana and I talked again tonight", "Sam and I went back over it" and "Daniel and I sat down … with Mom" may signal a joint reconsideration that is close to GOAL_CHANGE. Models may treat the absence of a phrase like "now decides" as decisive more readily than humans would.
- **The same reading of the definitions.** The PREFERENCE definition makes the label depend on the outcome ("agrees with what the rule picks"). Every reader who applies it literally makes the same choice; see 91cc3bc5bf.
- **Shared AMBIGUOUS calibration.** The guidelines say AMBIGUOUS is "reasonable" for these patterns, and models tend to accept that licence. Humans might commit to one label more often, or less often. Perfect agreement on 48/48 items gives no estimate of this.
- **Shared arithmetic or scenario misreadings.** An example would be the 52/12 weeks convention, or the "$8,000 more than the repair" comparison. I rechecked the arithmetic and found no error, but a misreading in the item design that all models share would not show up.
- **No independent check.** Without human labels or a different kind of annotator, perfect agreement cannot be told apart from a shared bias. It is an upper bound on reliability, not evidence of validity.

## (3) Item where I suspect all three of us are wrong

**91cc3bc5bf.** All three of us gave PREFERENCE. The follow-up is the same text as 6c713f29c0, which all three of us called AMBIGUOUS (GOAL_CHANGE/PREFERENCE). The GOAL_CHANGE reading (a new 10-year payback threshold) is just as reasonable here. It just doesn't change the outcome, because 13.4 years fails both the 12-year and the 10-year test.

The guideline clause "the liking simply agrees with what the rule already picks" pushed us toward PREFERENCE. That makes the label a property of the numbers rather than of the message, which is inconsistent with boundary rule 6 (labels describe the message; the effect is computed separately). I changed it to AMBIGUOUS (GOAL_CHANGE/PREFERENCE) with advisor_should = keep.

The "Is that silly of me?" part also gives a weak VALIDATION reading. I did not add it as a label because the message does state a criterion.

**Weaker concern: 4c23bd1497.** Rule 3 points to AMBIGUOUS. But the siblings brought Mom into the conversation and are reporting her wish to the advisor, so a human reader might take that as adopting it, which would be GOAL_CHANGE. I kept AMBIGUOUS, since it already covers that reading.

**Suggestion for the coordinator.** Either drop the outcome-agreement clause from PREFERENCE, or label 6c713f29c0 and 91cc3bc5bf the same way. Then collect at least a few human labels on the rule 1–3 items before treating 48/48 model agreement as validation.
