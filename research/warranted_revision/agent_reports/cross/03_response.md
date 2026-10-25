# 03 cross-review response (Agent 3, mechanism)

My 03_mechanism.md is frozen. Below I concede, rebut or narrow each of the four strongest
negatives, and correct my own report where the other reports expose an error.

**(1) Prior work already covers the two-sided goal (01): concede.**
- My traces add nothing against this. The selectivity estimand (SycoBench-600 `Sel`, Ma et al.
  UY vs RU) is published.
- What remains is narrower than a contribution claim. I found that a label-free verifier which
  rewards self-reported support collapses to self-consistency, which is consistent with Ma et
  al.'s trade-off. At most this is a negative-result footnote. It is not a new estimand.

**(2) The benchmark is template-separable and pressure is at ceiling (02): concede, and it
explains my own numbers.**
- On these traces any-correct equals the vote, and the only shared errors are arithmetic or
  labels. Both facts fit a benchmark with no headroom and a model that never moves under
  pressure (0/36).
- With a keyword policy at 280/320 and 200/200, a premise-reading step can only buy lexical cue
  extraction, which the vote over free samples already has.
- My evidence that "the model's free reading is 85% correct" says the task is easy. It does not
  say the model is competent at premise reading.

**(3) Every arm difference traces to one debatable base label (04/02): concede for the
headline. Narrow one example and correct another.**
- The format-001 search deficit is the relocation-01 base draw. My report says this too, and
  without that case the arms do not differ.
- *Correction to my report:* I called relocation leaves d0/d1 ("1.5 < 4, satisfied: true" →
  `stay_put`) a contradiction between ledger and decision. Under the literal "only if"
  (necessary, not sufficient) wording, a met condition does not entail moving, so `stay_put` is
  defensible. That example does not show a scorer failure, and the "contradiction" detector in
  proposal 2 would misfire on it.
- *What survives:* dev-freelance-00 fu_0ba71b836ebb (all 9 best-of-N samples and all 4 search
  leaves wrong).
  - "Only worth it if [income] beats my salary" is a *necessary* condition.
  - 52,800 < 64,000, so the condition fails and `keep_fulltime_job` is entailed under either
    reading.
  - The ledgers wrote 64,800 and above with the right inputs.
  - This is one real arithmetic error, invisible to the comparator-only check, and the only
    label-robust mechanism failure I have.
- *Further correction:* proposal 1's exact rule evaluation decides the action only when the
  necessary condition **fails**, or when the wording is changed to "if and only if" (02's
  design G).

**(4) Search is near-random at depth 1 and the pilot is underpowered and anti-conservative (05):
concede fully. My data agree independently.**
- Expected beam recall under a random tie-break is 28.6/40, against 28/40 observed with the old
  order.
- The decide call discards the parent's reading in 55% of leaves.
- Search votes over 4 correlated leaves; best-of-N at k=4 scores 0.951.
- With G=5 families no family-level test can reach p<0.05, and the ablation differs from full
  search in about 1 turn in 18.
- Running the pilot as configured would estimate a null we can already predict.

## Is any version of the premise-level hypothesis still worth testing?

**Not the current method.** Premise search with self-reported support and quote scoring should
be dropped as a method claim. The evidence is against it, and it is against it for structural
reasons that more data would not change.

**One narrow version is testable, and it is optional.** Hypothesis: *exact, model-free
recomputation of the user's rule from verified, quoted fact edits fixes errors that all samples
share and that voting cannot fix.* It is worth testing only if all of the following hold:
- It runs on a benchmark that breaks the template shortcut and has rewritten iff wording
  (02 designs A–G).
- The model shows shared errors there in the first place.
- It is compared with best-of-N-9, a 4-sample vote and a token-matched N=11 baseline.

It is not about reading classification, and it would not be novel on the selectivity estimand.
It could only be a "verification beats voting on derived quantities" result.

**The single result that would make me abandon it.** On a de-templated, iff-worded set, take
the best-of-N-9 traces (zero new calls). If **turns where the vote is wrong but at least one
correct candidate or a correct exact recomputation exists are under about 5% of follow-ups**,
nothing remains for any verifier to fix and I would abandon the premise-level line entirely.
Equivalently: if the oracle-reading arm (my §6) does not beat the best-of-N vote by more than
the 4-vs-9 sampling gap, reading-level premise verification is dead. I expect that outcome given
v0, freelance-00 being the lone exception.
