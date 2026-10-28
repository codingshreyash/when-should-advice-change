# Primary-set exclusion rule for the goal-change screen (fixed before any v3 annotation)

**The problem this rule addresses.** The AI annotators used in pre-calibration are Claude Opus
and Claude Sonnet, which are also the candidate API subjects of the screen. Excluding items
because those annotators answered "wrongly" would select the primary set toward items the
tested model already handles: optimising items on the tested model's answers by another route.

**Rule.** An item, and its pair partner, leaves the primary comparison if, and only if, one of
these text-based conditions holds:

1. `v2bench check` or `textcheck` reports a problem or a flag for it.
2. The adversarial gold-versus-text review rates it medium or high: the text doesn't establish
   an assumption the gold relies on, or a careful reader could reach a different computed
   behaviour.
3. It is one of the round-2 disputed items, which candidate_v3 leaves out entirely: `hp-05`,
   `cc-03/04`, `eb-10`, `eb-05`, `sol-01/02`, `cc-05/06`, `eld-08`, `sol-07`, `eb-07`.

**Not used for exclusion:**

- the AI annotators' `advisor_should` answers;
- whether they agree with each other;
- whether they agree with the gold.

Their answers are recorded. Items where the two AI annotators disagree on the message-type label
form a separately reported stratum.

**Sensitivity.** Every primary metric is also reported on all v3 items (primary + excluded),
so the effect of the exclusions is visible.

**Items are never edited after any model, annotator or subject, has seen them.** A defect
found later is recorded and the item is excluded by condition 2, with the reason, never
rewritten.
