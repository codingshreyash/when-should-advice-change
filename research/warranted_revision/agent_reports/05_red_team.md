# 05 — Methodology and reproducibility red team (Agent 5)

Analysis commit `06c8fc7`, branch `research/warranted-revision-v1`. I read the docs, the code, the
format-001 and smoke-003/004 artifacts and the challenge_v1 gold. I did not open the holdout
files, run a GPU or change any source.
Scratch files are in `agent_reports/redteam_05/`: `power_sim.py` and `test_redteam_05.py`
(2 pass, 1 strict xfail). The repo suite gives 77 passed.

## Reviewer verdict (one paragraph)

If this went to a venue tomorrow, I would reject it. The headline comparison, premise search
against matched-budget best-of-N, does not test search. Two facts drive that. First, the depth-1
beam picks readings almost at random. Second, both arms' final pick works out to a majority vote:
over 9 samples for best-of-N, over only 4 for search. The ablation changes the answer in about 1
turn in 18. The pilot is too small to detect that difference, or any realistic one. On this
evidence the null is the most likely result: the method adds nothing beyond sampling, and in
fact gives the search arm fewer sampled votes. The pilot as configured cannot tell that null
apart from a modest real effect.

## The three most important issues

### 1. Critical: "search" is close to random reading injection, and selection is close to voting

- **Ties make depth-1 pruning nearly random.** I took the follow-up traces with the current JSON
  ledger template (format-001) and counted top-score ties: 3 to 5 of the 5 readings tie in
  15 of 16 turns. In smoke-004 the figure is 24 of 40. The new seeded tie-break
  (`conditions.py:273-334`) removes the old order bias. It does not add any signal. I replayed
  the seeded rule on format-001 scores: the beam keeps the true reading with probability about
  0.45 to 0.67 per class, and pressure follow-ups sit at 0.50 to 0.53. Chance is 2/5 = 0.40.
  The tie-break fixes a coding bias, not the science, because the hypothesis score has nothing
  to rank on: the self-reported `SUPPORTED: yes` plus a verbatim quote is satisfied by every
  reading (FINDINGS.md §1, 32 of 40 wrong readings got the top score).
- **The prompt pushes change-licensing readings.** Each depth-1 prompt is in the user's voice:
  "Consider this reading of my latest message: changed_goal" (`prompts.py:74-80`). The decide
  call then gets that draft (`prompts.py:82-86`). About 60% of beams on a pressure turn
  therefore show the model a draft that says the goal changed. Best-of-N never sees such a
  draft. This difference has nothing to do with provenance, and it could raise false updates.
- **The final pick is a vote.** `select()` (`conditions.py:163-179`) sends score ties to a vote.
  In smoke-004 the heuristic rerank changed the answer relative to a plain vote in 0 of 40
  best-of-N turns and 2 of 40 search turns (FINDINGS.md §3). Search spends 5 of its 9 calls on
  calls that give no decision, so it votes over 4 candidates against best-of-N's 9.
  `SELECTION_COMPARISONS` describes `premise_search:vote` vs `best_of_n:vote` as "equal (vote)
  footing" (`evaluate.py:52-59`). The footing is not equal: 4 votes against 9.
- **Competing explanation.** If best-of-N comes out ahead, the cause is ensemble size. If search
  comes out ahead, the cause may be the extra draft-and-revise step, which is also extra tokens
  (see issue 3). Neither result would show that provenance matters.
- **Test (free, from the pilot's saved candidates).** Add `best_of_n:vote4`, a vote over the first
  4 samples, and compare it with `premise_search:vote` and `premise_search`. Add a
  random-reading control: depth-1 readings drawn uniformly with no scoring, and the same decide
  step. That costs about 1,980 calls, the same as the ablation slot. Report the
  true-reading-in-beam rate against 0.40 for each class.

### 2. Critical for the planned inference: the pilot cannot support any nontrivial conclusion, and its intervals are anti-conservative

- **Effective sample size.** There are 5 families and 20 cases. The joint metric fails every
  follow-up of a case whose base answer is wrong. format-001 shows this: one wrong base answer
  produced 8 of 8 discordant follow-ups. So the effective n is about the number of cases, and
  for inference it is about the number of families. The warranted axis has only 2 items per
  case, 40 in total. With 5 clusters there are only 126 distinct resamples.
- **Simulation.** `redteam_05/power_sim.py` uses the repo's own `stats.paired_diff_ci`. Its
  assumptions are stated in the file: family and case logit sd 0.75, base answers shared across
  arms with probability 0.9, follow-ups coupled with probability 0.7, p_base 0.9.

  | axis (items/case) | true gain (conditional) | power, CI excludes 0 | median CI width |
  |---|---|---|---|
  | pressure "ch" (6), p_fu 0.75 | +8 pp | 0.39–0.54 | 0.12–0.14 |
  | pressure "ch" (6) | +14 pp | 0.71–0.82 | 0.13–0.15 |
  | warranted (2), p_fu 0.85 | +9 pp | 0.30–0.35 | 0.18 |
  | warranted (2) | +11 pp | 0.49–0.52 | 0.18–0.20 |
  | **null**, "ch" | 0 | **two-sided false-positive rate 0.13–0.16** (1,000 sims; nominal 0.05) | |

  The minimum detectable effect at 80% power is about +14 to +18 pp on the pressure axis, and
  above +11 pp on the warranted axis. These numbers are optimistic, because they assume the
  pressure items actually move the model, and the v0 pressure items moved nothing. The
  ablation differed from full search in 1 of 18 turns in format-001, so it is undetectable at
  this size. The percentile cluster bootstrap with G = 5 undercovers. Across roughly 30 reported
  intervals (primary, ablation, 5 selection comparisons, 3 secondary, 3 axes each), several
  will exclude 0 by chance alone.
- **Test.** Rerun `power_sim.py` and check the nominal 5% false-positive rate. For a decision,
  name a single primary contrast. Use a family-level method that stays valid at small G, for
  example a sign test or permutation over families, which with G = 5 can never reach p < 0.05
  two-sided. Otherwise describe the pilot purely as estimation.

### 3. Major: "matched budget" means matched calls, not tokens, compute or decision samples, which departs from PROTOCOL §3

- **Tokens.** Measured per turn in format-001: best-of-N uses 9 × (1,334 + 240) = 14.2k tokens;
  search uses 5 × (1,431 + 264) + 4 × (1,757 + 308) = 16.7k. That is +18% total tokens and +18%
  completion tokens.
- **Latency.** Best-of-N runs at 2.1 s per call and search at 4.0 to 5.0 s per call (two
  sequential rounds, padded batches).
- **Protocol.** PROTOCOL §3 requires "the same number of calls *and token budget*".
  `ConditionConfig.check_budget` (`conditions.py:81-89`) checks calls only.
- **Test.** Report accuracy against tokens and GPU-seconds. Add a token-matched best-of-N arm,
  N = 11, which costs 11/9 of the best-of-N slot.

## Other issues (brief)

**Major**
- **Shard composition matches the label design.** `build_case` assigns priority by `index % 2`
  and the gold side by `(index // 2) % 2` (`generate.py:203-206`). With 4 round-robin shards
  (`runner.py:132-135`), each shard therefore holds a single (priority, gold-side) cell:
  shard 1 has all `*-00` cases, shard 2 all `*-01`, and so on. This is pinned by
  `test_four_shards_are_label_cells`. Each shard runs on its own instance, so any difference
  between instances is confounded with the label. Because shards run one at a time under a stop
  rule, a stop after shard 2 would leave data with only one gold side. Fix: shard by a seeded
  permutation that keeps the cells balanced.
- **The scorer and the reading menu encode how the data were built.** The 6 readings map one to
  one onto the generator's contrast classes. `supported_edit` hard-codes the rule "a
  reassurance reading must not change the answer" (`scoring.py:29-30, 89-100`), which is exactly
  the gold rule for pressure items. Any gain on these rule-built cases may not transfer. The
  menu is also shown to the structured, best-of-N and search arms but not to `direct`.
- **Reproducibility.**
  - The manifest's `git_dirty` is always True on the GPU box (`runner.py:89-90`).
  - The bundle is tarred from the working tree, not from a commit (`brev_controller.py:216-221`),
    and no source-tree hash is recorded.
  - `transformers>=4.57` is unpinned, and `remote_job.sh:15-16` may run `pip install -U`.
  - The optional kernels are installed best-effort for each shard.
  - `aggregate._systems` ignores torch and transformers versions, so shards built on different
    stacks merge without complaint.

  Fix: pin the stack, hash the bundle into the manifest, and have aggregate compare the
  pip-freeze output.
- **The HF backend seeds once per batch with `reqs[0].gen.seed`** (`hf.py:111`). The per-call
  seeds written to `predictions.jsonl` are therefore not the seeds used, and a call's output
  depends on what else is in its batch and on `max_batch`. This is pinned as a strict xfail.
  Negative finding: common random numbers do work in practice. In format-001, 56 of 56 decide
  calls with identical messages and seed in search and its ablation produced byte-identical
  text (`test_ablation_crn_is_deterministic_in_format001`).
- **The ablation does not isolate provenance.** `premise_search_formatonly` removes the whole
  heuristic at once, including the check that the ledger's reading matches the reading asked for
  (`scoring.py:131` vs `:160-165`). With the shared seeds and the shared tie-break, an all-tie
  turn produces the same beam and the same decide outputs in both arms. The ablation then
  reduces to a heuristic rerank of 4 leaves against a vote of 4. That is a test of the rerank,
  which was already shown to be nearly inert (FINDINGS.md §3). It also has no control for a
  plain "stick with the previous answer" prior, which `supported_edit` partly implements.
- **Differences from the frozen PROTOCOL.**
  - Two blinded reviewers are required; there are none.
  - Co-primary axis (ii) needs the subthreshold, irrelevant and pressure_for_* classes; none are
    in challenge_v1, so the pilot's "ch" axis is new and not preregistered.
  - The preregistered structured-vs-direct comparison is dropped, because the pilot has no
    structured arm, so H1 cannot be tested.
  - Stage 2 asks for 3 replicates; the pilot has 1. Option order is rotated across cases instead
    of counterbalanced within case.
  - The token budget is not matched (issue 3).
  - The scoring weights, tie-break and ablation are defined only in PILOT_PROPOSAL and code;
    PROTOCOL was never amended. Its sha `868bf91` is recorded but describes an older design.

**Minor**
- The "ch" axis and `stability_all_styles` pool the authority style (`schema.py:69-80`), although
  the challenge README says authority is analysed separately.
- Deference and opposition are computed only on turns where the base answer was correct
  (`evaluate.py:208-214`). Each arm keeps a different subset, so these rates are not paired.
  Only the joint metrics are.
- Follow-up turns feed each arm its own base reply (`runner.py:328-336`). Direct sees three
  sentences of history; the ledger arms see a full ledger. This matters for comparisons with
  direct, not for the primary.
- The parser counts every case-insensitive `DECISION:` (`parsing.py:221`). Prose such as
  "my decision: …" therefore invalidates longer outputs more often.
- `need_more_information` candidates get the arithmetic point for free (`scoring.py:117`).
- Follow-up ids are hashes of the contrast class (`challenge.py:109-112`), so seeds and tie-break
  keys are deterministic functions of the label. There is no exploitable leak, but say so.
- `pilot_check` does not implement the proposal's "no movement" stop rule, which needs gold
  labels.
- README, PILOT_PROPOSAL and DESIGN_NOTES are stale in places: the README says no model has run,
  and the proposal still names `noprov` and describes 3 shards.
- format-002 failed in the on-box test suite. That is noted only; the lead is handling it.

**Leakage: negative finding.** The runner reads only `*_inputs.jsonl`; backends receive only
messages; the scorer sees only visible text. I found no path from gold labels, contrast classes
or ids into prompts or selection. Gold files are shipped in the bundle to the box but are read
only by `evaluate`.

## Main finding, alternatives, confidence

- **Main finding.** As implemented, the H2 comparison is "vote over 9 independent samples"
  against "vote over 4 samples, each conditioned on a near-random interpretation draft", matched
  on calls only. A difference, if one appears, cannot be attributed to provenance or to search.
- **Alternative explanations.**
  - Ensemble size.
  - The draft-and-revise step and its extra tokens.
  - Priming by user-voiced readings.
  - The scorer's built-in rule that pressure should not change the answer.
  - Family-level noise at G = 5.
- **Confidence.**
  - That the comparison is confounded (issue 1): high.
  - That the pilot is underpowered: high, though the exact numbers depend on my assumptions.
  - That the method adds nothing beyond sampling: moderate. That is the prior I would bet on, and
    it is supported by the 0/40 and 2/40 rerank results and the 1/18 ablation result.

## Falsification test

Pre-register this before any new run. If premise search beats `best_of_n:vote4`, `best_of_n`
(N = 9) and a token-matched best-of-N (N = 11) on pressure stability, by at least 10 pp joint with
no loss on warranted updates, in new families, then search carries signal. If
random-reading search matches full search within ±3 pp, the beam is inert and H2/H3 are
falsified for this design.

## Recommended actions and cost

Prices: L40S at $1.06/h, about 3.9 s per call at present.

1. Free, CPU only:
   - add the `vote4` and token-matched derived selectors;
   - shard by a balanced permutation;
   - name one primary contrast;
   - add a family-level permutation or sign test;
   - pin the software stack and hash the bundle;
   - amend PROTOCOL to v0.2 with a commit hash before launch.
2. Pilot as approved plus a random-reading arm instead of, or alongside, the format-only
   ablation: about 6.2k to 8.1k calls, roughly $9 to $13 expected and at most $16 to $20
   worst case.
3. Confirmatory study: at least 20 to 25 new families with human-reviewed labels, 3 replicates,
   5 arms. That is roughly 100k calls, about 100 GPU-hours, or $100+ with HF generate, which is
   over the balance. vLLM with prefix caching (shared prompts) would cut this several-fold.

## Minimum changes: (a) a credible exploratory pilot

1. Balanced shard assignment, or a single instance.
2. Add `best_of_n:vote4` and report every arm against calls, tokens and GPU-seconds.
3. Replace or supplement the format-only ablation with a random-reading control that keeps the
   decide step and drops scoring.
4. Report the true-reading-in-beam rate against chance (0.40).
5. Declare one primary contrast (premise search vs best-of-N on pressure joint stability,
   excluding authority). Treat every other contrast as descriptive and label all intervals
   "G = 5, anti-conservative".
6. Pin the software stack and record a bundle hash.
7. Record the PILOT_PROPOSAL and PROTOCOL deltas in a committed v0.2 before launch.

## Minimum changes: (b) a conference-quality confirmatory study

1. New, independent families. At least 20 is my estimate for an MDE of about 8 to 10 pp. Labels
   should come from two blinded reviewers, and the holdout should stay frozen.
2. A hypothesis score that can discriminate between readings: for example, contrastive or
   likelihood-based scores, or a verifier that is not the model's own yes. Report its accuracy
   on reading classification before any end-to-end claim.
3. Budget matching on tokens as well as calls. Equal decision-sample voting comparators
   (vote-k at k = 4 and 9). Arms for token-matched best-of-N and for random-reading search.
4. Both co-primary axes, with all protocol classes, including subthreshold, irrelevant and
   missing information. Three replicates with option order counterbalanced within case.
5. Inference at the family level, with a method valid for the number of clusters: mixed-effects
   logistic with family and case effects, or a permutation test. Correct for multiplicity
   across arms and axes.
6. At least a second model, or say plainly that the results are single-model.
7. A frozen, pinned and hashed software environment.
8. A preregistration committed before data collection.

## Open questions

- Does the decide step's "correct the draft" instruction alone (no search, one draft from a
  structured call) explain any gain search shows?
- Do the challenge pressure styles move Qwen3.5-9B at all? If not, the pilot's stop rule ends
  it. Running about 20 direct-only turns first would answer this for about $0.10.
- Should `request_for_reassurance` stay on the menu? It mirrors the pressure label.
