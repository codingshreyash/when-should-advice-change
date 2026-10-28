# Synthesis of the v2 review: benchmark, annotation and scaffold probe

**Inputs:**

- four independent reports, frozen before cross-review: 01 design, 02 statistics, 03
  literature, 04 offline analysis;
- four cross-reviews in `cross/`;
- the lead's own checks.

No GPU or API calls were made. No frozen data, historical outputs or committed metrics were
changed. The holdout was not opened.

## What we found

1. **The v0 results were thinner than the first synthesis said, in two ways (04, 02).**
   - The pressure ceiling holds only for greedy decoding: temperature-0.7 samples switched
     12/45 times under pressure against 0/45 under a neutral mention.
   - A fixed 4-sample vote scores exactly what premise search scores (0.925). The 0.951 figure
     in the first synthesis was a random-subset average.

   Corrections are appended to `agent_reports/SYNTHESIS.md`, with the original text kept.
2. **"Goal change vs preference" cannot be both reliably labelled and lexically hidden (01).**
   Careful readers separate them only when the user says the new consideration now governs the
   decision, and that is always a phrase. v2's clear items therefore test reading an explicit
   scope statement. The interesting cases sit in an ambiguous stratum, where the right answer is
   to surface the conflict.
3. **The first drafted items leak their labels (lead's audit; 01 and 04 cross-reviews).**
   - On the 48 calibration drafts (written by an AI design agent), a follow-up-only classifier
     recovers the label 54% of the time against 17% chance (permutation p ≈ 0.005).
   - The leaks: colons in every goal change, "now" only in goal changes, length differences.
   - Removing the first five words brings goal vs preference down to about chance (0.56).
   - What is left is built into the labels themselves (source words, hedges, requests aimed at
     the advisor). That is why wording-defined contrasts must be audited on masked text.
4. **The literature leaves v2 a narrow opening at best (03).**
   - Every class has close prior work: BeliefShift, Big-Big-SycoBench, ELEPHANT, SycoBench-600,
     Ma et al.
   - The originally planned model hypothesis (warranted vs unwarranted accuracy differing) was
     near-guaranteed to pass and already published.
   - Two questions only this design can ask replace it: paired-base sensitivity (does a model
     react to a message's consequence, or to its wording?), and whether anti-sycophancy tuning
     costs users their goal changes.
5. **The cross-review caught three real bugs before anything ran.**
   - The gold computation silently returned KEEP when reviewers chose a label without an
     authored reading.
   - The probe crashed on a non-actionable base answer.
   - The probe's sampled readout in S3 drew the wrong turn.

   All three are fixed with regression tests. The design check's verdict on the probe was
   "ready with listed fixes", and every listed fix is in.

## The biggest threat

The construct may not survive operationalisation. If the GOAL_CHANGE / PREFERENCE distinction
fails calibration, or survives only as scope-clause detection, v2 measures something narrower
than "warranted goal change". What remains would be:

- the supported/unsupported contrast, already studied as source reliability;
- an ambiguous stratum scored as "did the model ask".

That is a dataset paper at workshop scale, not the study's original contribution.

## Strongest competing explanation

**For whatever models do on v2:** they react to the wording of a follow-up (a governance
clause, a source phrase, a hedge), not to whether it changes the decision's premises. The
paired-base design (the same string flips one base and not the other) is the one test that
separates the two, which is why it became confirmatory hypothesis H-M1.

## The single next step

**Calibration round B1. No GPU; human time only.**

1. Human authors rewrite the 48 calibration items:
   - shared carriers in every family;
   - no colon or "now" pattern;
   - lengths matched;
   - `marker_span` marked;
   - the cell grid rebalanced toward ≤45% KEEP;
   - `sol-07` fixed.
2. Re-run `v2bench audit` until the masked-text contrasts show no gross cue.
3. Two reviewers label it with the revised guidelines (about 1–2 h each), and the adjudicator
   labels disputed items blind first.
4. Apply the pilot gate (κ ≥ 0.6, no confusion pair > 10%, ambiguous 5–20%), and report the
   GOAL_CHANGE / PREFERENCE confusion on its own.

**Decision rule, fixed now:**

- **Gate passes and GOAL/PREF is not the main confusion:** author the 8 dev families (B2).
- **Gate fails:** revise the guidelines and run 48 new items once.
- **Fails twice on GOAL/PREF:** that distinction is reported as not reliably annotatable. v2 is
  re-scoped without it, and the study decides whether the remaining contrasts justify
  continuing.

The scaffold probe's stage 1 ($2.05 cap, 970 calls, gold-free) is ready to launch on approval.
It can run in parallel because it doesn't depend on B1. It settles one question for v2's
elicitation format: greedy vs sampled readout, and whether a separate decision turn changes
movement.

## Disagreements kept open

- **Audits:** a four-part test on every contrast (02) vs masked text for wording-defined
  contrasts (01). The proposal reports both.
- **Ambiguous items:** excluded from denominators (02) vs scored as HEDGE in their own cell
  (01). The proposal does the latter, kept separate from the primary metric.
- **Test families:** 24–30 for power (02) vs authoring quality binding first (01). Decided at B2.
- **Probe stage 2:** the design check accepts it with the corrected power (about +25–30 pp
  greedy, +15–20 pp sampled). The literature reviewer calls it optional. Its value is internal
  either way.

## Where everything is

| what | file |
|---|---|
| benchmark-v2 proposal | `BENCHMARK_V2.md` |
| protocol v0.2 (draft; probe section fixed) | `PROTOCOL_v0.2.md` |
| reviewer guidelines | `v2/annotation/GUIDELINES.md` |
| coordinator procedure (blinding, gold, adjudication, thresholds) | `v2/annotation/COORDINATOR.md` |
| tooling: rules as code, checks, audits, packets, agreement | `src/warranted_revision/v2bench.py` |
| calibration draft and its audit | `v2/calibration_draft/` |
| scaffold-probe plan, configs, code | `SCAFFOLD_PROBE.md`, `configs/scaffold_probe_*.json`, `scaffold_probe.py`, `probe_analysis.py` |
| evaluator corrections corr-1 (separate from committed metrics) | `src/warranted_revision/corrections.py` |
| cancelled pilot (kept; controller refuses it) | `PILOT_PROPOSAL.md`, `configs/pilot_challenge.json` |
