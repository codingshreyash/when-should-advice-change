# Protocol v0.2 (draft): warranted goal and premise changes

**Status: draft, not frozen.**

- The scaffold-probe section (§6) is fixed now, before its first launch, and its rules live in
  `SCAFFOLD_PROBE.md`.
- The benchmark sections (§1–5) freeze, with this file's commit hash recorded, only after
  stage B3 of `BENCHMARK_V2.md`: test families authored, audited and annotated.
- No model may see a v2 test item before that.
- `PROTOCOL.md` (v0.1) stays unchanged as the record of the original plan.

## What changed from v0.1, and why

| v0.1 | v0.2 | reason (source) |
|---|---|---|
| Primary contribution: an inference intervention (structured ledger, premise search) | Primary contribution: **an instrument**. A benchmark for whether models tell legitimate goal and fact changes from preference, validation-seeking and unsupported claims. Premise search is kept only as an experimental baseline. | Search was no better than majority voting over the same samples; its scorer checked self-consistency, not premises (`agent_reports/SYNTHESIS.md` B) |
| Seven contrast classes, rule-generated labels | Six labels (§1 of BENCHMARK_V2.md), gold behaviour computed from human-confirmed readings | v0 labels rested on debatable readings ("only if" as "iff"; an ignored reimbursement) (SYNTHESIS C) |
| Templated follow-ups | Hand-written contrast sets with shared carriers, paired bases and context swaps; shortcut audits must pass first | A keyword rule scored 280/320 and 200/200 on v0 and challenge_v1 (SYNTHESIS C) |
| "Two blinded reviewers where ambiguity exists" (never done) | Two blinded reviewers on **every** item, plus a blinded adjudicator and an explicit ambiguous label | Required, and never implemented in v0 (05_red_team.md) |
| Five dev families, three holdout | 8 dev + 24 test families, new domains | No family-level test could reach p < 0.05 with five families (04_analysis.md; v2 02_stats.md §1) |
| Percentile family bootstrap | Exact sign-flip or t-test on family means; Holm across at most two confirmatory hypotheses | The bootstrap was anti-conservative at small G (02_stats.md §1.4) |
| Calls-matched budgets | Calls *and* tokens reported for any method comparison | v0.1 §3 required tokens too; never enforced (05_red_team.md) |
| Follow-up carries options and the DECISION instruction | Follow-up delivered alone; decision in a fixed separate turn; sampled readout beside greedy | The scaffold and greedy decoding may have produced the pressure ceiling (SCAFFOLD_PROBE.md) |
| v0 holdout to be run once at the end | **v0 holdout retired unused**; it shares v0's templates and "only if" wording | It cannot measure the construct (02_benchmark.md O12) |

## 1. Estimand

On rule-stated decision scenarios, after the model's first recommendation, measure the rate
at which its next recommendation matches the **computed gold behaviour** (revise, keep, or
hedge). Report it by human-confirmed label, together with:

- the credulity rate;
- the dismissal rate;
- the over-hedging rate;
- symmetric movement (deference and opposition) against neutral controls.

Revision metrics count only items whose integrated-state control the model answers correctly
(denominators shown).

**Unit of inference:** scenario family. Bases, strings, option orders and samples are
repeated measurements.

## 2. Hypotheses (benchmark validity first)

- **H-B1 (annotatability).** Two blinded reviewers reach Krippendorff's α ≥ 0.80 (lower 95%
  bound ≥ 0.70) on the six labels, with per-category κ ≥ 0.70 for each substantive label.
  - If GOAL_CHANGE vs PREFERENCE fails twice at calibration, that distinction is reported as
    not reliably annotatable and analysed only as ambiguous.
- **H-B2 (no shortcut).** Every binary label contrast passes the four-part audit (BENCHMARK_V2
  §6), with the margin of 0.12 fixed now.
- **H-M1 (paired-base sensitivity; tested only if H-B1 and H-B2 hold).** On byte-identical
  follow-up strings attached to two bases, a model's revision rate is higher on the base where
  the string changes the computed answer than on the base where it doesn't.
  - Statistic: the family-level paired difference in revision rate, flip-base minus
    no-flip-base, per model.
  - A difference near zero means the model reacts to the message's wording, not to its
    consequence for the decision.
  - Only this design can test it.
- **H-M2 (autonomy cost of anti-sycophancy training).** Models tuned against sycophancy accept
  legitimate goal changes (computed REVISE on GOAL_CHANGE items) less often than their base or
  instruction-tuned counterparts. Pairs of models are chosen at B3.
  - This extends Ma et al.'s finding (that sycophancy suppression impairs rational updating) to
    user autonomy over goals.

The earlier H-M1 (warranted vs unwarranted accuracy differing by ≥10 pp) was dropped. The
literature cross-review showed it is almost guaranteed for any model that leans toward
keeping or toward revising, and the trade-off is already published.

Only H-M1 and H-M2 are confirmatory model hypotheses (Holm). Everything else is descriptive.

## 3. Gold, annotation and audits

- **Gold:** BENCHMARK_V2.md §2.
- **Annotation procedure and thresholds:** `v2/annotation/COORDINATOR.md`.
- **Audits:** BENCHMARK_V2.md §6.
- **Model-generated labels:** never used anywhere in gold.

## 4. Elicitation

BENCHMARK_V2.md §4, amended only by the scaffold probe's result. Any amendment is made and
recorded before B3.

## 5. Splits and freezing

- **Dev families:** used to develop prompts and audits.
- **Test families:** frozen with sha256 hashes at B3. Never used to tune prompts, guidelines or
  items after the freeze.
- **v0 and challenge_v1:** stay frozen and are not used for v2 claims.

## 6. Scaffold probe (fixed now)

Fixed in `SCAFFOLD_PROBE.md`:

- the design, items, gates V1–V6 and the stage-1 branch rules;
- the stage-2 configs and the $5.00 worst-case total.

It is a diagnostic on challenge_v1 scenarios and supports no v2 claim.

## 7. Reporting

Every number is labelled exploratory unless it comes from the frozen test split under §2.
Negative results and failed runs are reported (`results/warranted_revision/runs.json`).
Original v0 metrics stay as committed; corrected quantities come from `corrections.py`
(corr-1) in separate files.
