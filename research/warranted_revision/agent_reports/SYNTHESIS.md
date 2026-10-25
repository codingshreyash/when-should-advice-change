# Synthesis: what the review found and what to do next

Analysis commit `06c8fc7`. Five independent reports (01–05) were written and frozen first. Then
came four cross-reviews (`cross/`). I re-ran three load-bearing checks myself:
- the template-only policy (`analysis_02/cues.py`): 280/320 v0, 200/200 challenge_v1;
- best-of-N vote subsampling (`prototypes_03/subsample.py`);
- the "only if" → `iff` gold rule (`families.py:87-91, 296-311`).

All three reproduce. No GPU or API calls were made. No frozen data, historical outputs or
manifests were changed. Everything below is exploratory: one model (Qwen3.5-9B), 7 dev cases in
the informative runs, rule-generated labels with no human review.

## A. Research status

- **Built:** the benchmark, five arms, the scorer, the evaluator, and the GPU path with cost
  guards.
- **Real-model data:** dev-set data from three runs (smoke-003, smoke-004, format-001). Every
  committed metric reproduces exactly (04).
- **No data yet:**
  - nothing from the current instrument (seeded tie-break, strict `satisfied`);
  - nothing on challenge_v1;
  - nothing on the holdout (untouched).
- **Approved but not run:** the challenge pilot. It is on hold.
- **format-002:** failed in the on-box suite. The run is logged. The test is now fixed properly:
  totals are checked on a self-contained log, and a missing repo log is an error everywhere
  except inside a launch bundle (`788357e`).

## B. Strongest finding

**Premise search adds nothing detectable beyond sampling plus a majority vote. Its "verifier"
does not verify premises.**

- **Best-of-N vote is as good or better in every usable run** (03, 04).
  - Follow-up turns: smoke-004 39/40 vs search 37/40; format-001 16/16 vs 12/16. The format-only
    ablation scored 11/16.
  - Reranking against a plain vote over the same candidates: 4 gains and 1 loss in 96 turns,
    sign test p≈0.38.
- **Search behaves like a 4-sample vote** (03, 05). 5 of its 9 calls never produce a decision,
  and its 4 leaves are correlated. Best-of-N cut to k=4 scores 0.951; search scored 0.925.
- **The score measures self-consistency, not correctness** (01, 03, 04, 05; code
  `scoring.py:62-142`).
  - A wrong reading gets the maximum score in 32/40 and 16/16 turns.
  - The model says `SUPPORTED: yes` to 52–70% of wrong readings.
  - The arithmetic check passes invented totals (84,000 > 64,000 when the true value is 52,800).
- **The reading the beam keeps barely matters.** The decide call replaces a wrong parent reading
  with the intended one 75–77% of the time (04's corrected figure). Leaves under wrong readings
  are about as accurate as leaves under true ones (03).
- **The seeded tie-break removes an ordering bias but adds no signal.** Beam recall stays near
  chance (05; 03: 28.6 vs 28 of 40 expected).

The only positive signal is 3 pressure turns where the `supported_edit` penalty picked the one
leaf that didn't give in (04). That is a capitulation veto on top of voting, not premise
verification.

## C. Biggest threat

**The benchmark cannot measure warranted revision, so no method result on it would mean much**
(02, confirmed by me).

- **Template cues give the class away.** A policy that reads only a follow-up's opening words
  scores 280/320 on dev and 200/200 on challenge_v1 when the base answer is correct.
  - Goal change vs pressure, the central contrast, is a keyword test: "My priority is…" against
    pressure text with goal words banned. A goal change always flips the answer.
- **Some gold labels rest on debatable readings.**
  - "I'll only X if…" is scored as "X if and only if…" (14/40 dev cases, 7/20 challenge cases).
  - Certification ignores the stated reimbursement.
  - These two readings explain 2 of the 3 distinct real-model failure points. They also explain
    every arm difference in smoke-004 and format-001, through one case, `dev-relocation-01`
    (04).
  - Measured only on cases where the base answer was correct, greedy `direct` is perfect.
- **Pressure is at ceiling.** There were 0 moves in 36 pressure turns. The options list and
  DECISION instruction are attached to the pressure message itself, which may suppress
  deference.
- **The movement metrics are asymmetric.** Deference counts only a move to the target.
  Opposition counts any change (`evaluate.py:201-214`).
- **Statistics:** 5 families, effective n of 1–4. No two-sided family-level test can reach
  p<0.05. The pilot's percentile intervals have a 13–16% false-positive rate at nominal 5%
  (05's simulation, under stated assumptions).

**Strongest competing explanation for everything observed:** majority voting over temperature-0.7
samples, plus label ambiguity on one case. This needs no premise structure at all. On these data
the method contributes nothing beyond sampling, and it actually gives search fewer votes than
best-of-N.

## D. Novelty assessment

- **The two-sided estimand is published.**
  - SycoBench-600 (Findings ACL 2026) and Ma et al., "Sycophancy Suppression Can Impair Rational
    Updating" (Findings EMNLP 2026), both verified from their repos.
  - Belief-R and SycEval are verified from search snippets only.
  - Ma et al. already show that mitigations trade one side against the other.
- **The method has no new mechanism.** Label-free self-verification collapsing to
  self-consistency is what Huang et al. (ICLR 2024) predict.
- **The only candidate contribution (01) does not survive in our data (02's cross-review):** a
  legitimate goal-change class distinct from pressure. It would need:
  - minimal pairs with matched wording;
  - goal changes that keep the same answer;
  - goal words used without any goal change;
  - human labels.
- **What an ACL/EMNLP submission would need:** a dataset where those contrasts are not
  lexically separable and labels are human-validated, with 20+ families, at least two models,
  and inference valid at the family level. On top of that, either:
  - a real finding that "deciding whether a message changes the decision's premises" fails in a
    way existing selectivity benchmarks miss; or
  - a method that beats vote-k and token-matched best-of-N on it.

  Neither exists yet. The honest current scale is a short negative or diagnostic note:
  "label-free premise verification reduces to self-consistency".

## E. Next experiments, ranked by information

**1. Pressure-scaffold probe (red team's C, recommended).**
- *Design:* `direct` only, on challenge_v1. Pressure follow-ups are run two ways:
  - as now, with options and DECISION attached;
  - unscaffolded: free reply first, decision in a separate turn.
- *Also included:* 3 turns of repeated pushback and 3 option-order replicates.
- *Metric:* switching away from the model's own base answer, against neutral mention. It needs
  no gold labels, so the label defects don't touch it.
- *Calls:* 2,220. Expected about $3.1, cap $5. One instance.
- *Stop if:* final-turn validity falls below 95%, or the planned and made call counts differ.
- *Question it settles:* is the ceiling caused by our prompt scaffold or by the model? That
  gates every arm comparison.
- *Before launch:* needs a small CPU-side change, an unscaffolded follow-up mode and a gold-free
  movement metric, plus your approval.
- *Decision rule:* if switching beyond neutral is under 5% even unscaffolded, drop the stability
  axis for this model.

**2. Human relabeling (no GPU).**
- About 350 flagged items: the "only if" positives, the certification items, missing-info items
  under necessary-condition rules, and insist/authority pressure.
- Two blinded reviewers, about 12 person-hours. Report kappa and keep an "ambiguous" stratum.
- This blocks every accuracy claim, and PROTOCOL already requires it.

**3. Oracle-reading diagnostic (01's E, 440 calls, ≤$2).** Run only on items the reviewers agree
on. It asks whether errors come from misreading the message, misreading the priority, or
arithmetic (three-way, per 02's cross-review). Before relabeling it would mostly report label
defects.

The 1,800-call gold-reading diagnostic (03) is not ranked. The analyst's cross-review and the red
team argue that on the current set it is biased toward a null by the ceiling and the label
ambiguity. Run it only on turns where best-of-N's vote is wrong or split.

## F. Implementation plan

**Now (CPU, small):**
- Map the legacy `premise_search_noprov` into the evaluator's ablation comparisons, so format-001
  re-evaluates faithfully (04).
- Make deference and opposition symmetric, report NMI and invalid outputs separately, and gate
  the v0 attack metric on a correct base. Do this as a new metric version alongside the old one,
  not a silent change.
- Add derived selectors `best_of_n:vote4` and a token-matched comparison.
- Report family discordance counts and exact sign-flip p in place of percentile CIs when G < 6.
- Fix stale docs (README status, the PILOT_PROPOSAL `noprov` text). Write a protocol v0.2 that
  records every deviation from the frozen v0.1.

**Wait (needs approval or labels):**
- the scaffold probe and its unscaffolded mode (E1);
- relabeling (E2);
- a de-templated, iff-worded dev set built from 02's designs A–I. It would be a new versioned set;
  v0 and challenge_v1 stay frozen.

**Never (on this evidence):**
- new search or verifier algorithms on the current benchmark;
- the premise-diff, comparative-reading or dispersion scorers before relabeling (the premise-diff
  kill test is circular against the generator's rule, per 04's cross-review);
- running the holdout, which shares the templates and the "only if" wording;
- presenting any current number as a method effect.

## G. Go / no-go on the pilot

**No-go as configured.** Every report and cross-review agrees, except 01, which would run it only
as a test of the negative thesis.

- It would sit at the pressure ceiling, with labels whose ambiguity decides the base turns.
- It has 5 families, about 0.4 power at +8 pp and anti-conservative intervals. Its 4 shards are
  each a single label cell.
- Expected result: a null we can already predict, for $9–16.

**Frozen design vs separately versioned.** Keep the approved pilot config and PROTOCOL v0.1
exactly as they are. Do not run them, and do not edit them to fix the problems. Any new run (the
scaffold probe, a relabeled set, a revised pilot) gets its own config, its own version
(`challenge_v2`, protocol v0.2) and its own freeze.
- The cost: the old pilot's preregistration is spent without data, and nothing later can claim
  to be "the preregistered pilot".
- The benefit: nothing gets quietly re-labelled as the original instrument, which matters more.

## Disagreements left open

1. **Does the reading matter at all?**
   - 03 says no: leaf accuracy is the same under true and wrong parent readings.
   - 04 says the pooled figure hides the one class where it could matter. On pressure_for_incorrect,
     true-reading parents gave 6/6 correct leaves against 11/14 for wrong-reading parents, on 20
     leaves.
   - Unresolved; needs a set where pressure moves the model.
2. **Is there headroom for any reranker?**
   - 03 says no, because best-of-N's errors are unanimous.
   - 04 says search's own candidates have any-correct above vote (38 vs 37; 12 vs 10), and
     smoke-003 best-of-N had 35 vs 30.
3. **The first spend.**
   - 05: the scaffold probe.
   - 01: the pilot, as a negative-result test.
   - 04: wait for pilot traces, then a targeted diagnostic.
   - 03: only a recomputation test, on a rebuilt benchmark.
4. **Novelty.**
   - 01: the goal-change class is the surviving contribution.
   - 02: it doesn't exist in our data until the wording shortcut is removed.
5. **dev-relocation-01.** 03 first called it a decision contradicting its own ledger, then
   retracted that: under literal "only if" wording `stay_put` is defensible. 02 and 04 treat it as
   a label problem. Human review decides it.
