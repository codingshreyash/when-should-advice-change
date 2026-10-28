# 01 — Novelty audit (Agent 1, independent phase)

Commit `06c8fc7`, 2026-10-25. I read the state, README, PROTOCOL, DESIGN_NOTES, PILOT_PROPOSAL,
`prompts.py`, `conditions.py`, `scoring.py`, `schema.py`, `data/challenge_v1/README.md`, one
dev record, `results/warranted_revision/audits/FINDINGS.md` and the root README. I did not
read any other agent's report or any holdout file. I ran no GPU or API jobs.

**Access limits.** WebFetch failed DNS for arxiv, aclanthology, alphaxiv, neurips,
semanticscholar, openreview and huggingface. Public GitHub clones worked, so two papers are
verified from their companion repos (README, and for SycoBench-600 the camera-ready LaTeX).
Every other citation rests on search-result snippets and is labelled that way.

## 1. Main finding (reviewer's verdict)

Prior work already covers the scientific question, and the method as built adds nothing
measurable beyond sampling plus majority vote.

**(a) The two-sided estimand is published.** "Resist unsupported pressure while keeping
warranted updates, and score both sides" already exists in four places:
- SycoBench-600: correction selectivity, `Sel = Update − WrongFlip`.
- Ma et al. 2026: Unsupported-Yielding vs Rational-Updating, with the same three-message
  protocol as ours (question, then the model's own answer, then the condition), plus
  evidence-from-user attribution.
- Belief-R 2024: belief-update vs belief-maintain accuracy.
- SycEval: progressive vs regressive flips.

Ma et al. also show that existing mitigations trade one side against the other. "Selective
revision is hard and unsolved" is therefore a known result, not ours.

**(b) The method does not verify premises.** The scorer checks only internal consistency:
- quotes appear verbatim;
- the model's own comparison is arithmetically right;
- a changed answer is "supported" if the model's *own* reading licenses a change
  (`scoring.py:89-100`);
- the hypothesis score adds a self-reported `SUPPORTED: yes` (`scoring.py:125-142`).

Nothing scores whether the reading is correct. Ties fall to majority vote
(`conditions.py:163-179`).

The audit (`audits/FINDINGS.md`) found:
- wrong readings get the maximum score in 32/40 turns;
- all five readings tie in 38/40 turns;
- the rerank changed the answer relative to a plain vote in 0/40 best-of-N turns and 2/40
  search turns.

Huang et al. (ICLR 2024) predicts exactly this: label-free self-verification and debate do not
beat self-consistency at a matched budget. The working null hypothesis should be
"premise search = self-consistency + format filter".

**(c) The stimuli make "warrant" lexically easy.**
- Pressure messages are audited to contain no numbers, goals or facts
  (`challenge.py:196-240`).
- Fact changes carry "Update:"/"Correction:" plus a number.
- Goal changes say "Please treat this as replacing my earlier priority."
- There is no false or unsupported factual-correction class. PROTOCOL §2 asks for one; the
  data do not have it. Prior benchmarks treat that class as the hard case.

Even a positive result would therefore invite the reply "a regex could do the
interpretation step."

What survives: the domain (advice with stated rules) and the **changed-goal** warranted class.
I found no prior benchmark that separates a legitimate goal change from pressure. That is a
dataset contribution, not a method contribution, and it is a small one.

## 2. Evidence

### Literature (only works that bear on the verdict)

| Work (verification) | What it does | Overlap | Does NOT do |
|---|---|---|---|
| **SycoBench-600**, D. Sinha, Findings ACL 2026, 2026.findings-acl.1759 (**verified**: cloned github.com/debu-sinha/sycobench-600; read abstract in `paper/sycobench_camera_ready.tex`). This is the "SycoBench" with a peer-reviewed primary source | 600 MCQ items; doubt, authority and wrong-suggestion pressure plus a matched correct-suggestion condition; metrics PRA, Syco, Stub_nc, Sel; cluster bootstrap. "Willingness to update does not by itself imply selectivity" | Our two co-primary axes; same pressure styles (authority, "are you sure"); same CI method | Decisions, goals, subthreshold or retraction classes; no mitigation |
| **Ma et al., "Sycophancy Suppression Can Impair Rational Updating"**, arXiv 2608.26511, Findings EMNLP 2026 (**verified via repo README**, github.com/dependentsign/sycophancy-rational-updating) | R_UY (pressure) and R_RU (evidence, user-attributed evidence) on disjoint item sets; DPO, SFT and steering trade UY against RU; the two behaviors share circuitry | Closest threat: same goal, same two-turn protocol, same evidence-accuracy vs authority split | Advice decisions, goal changes, inference-time search |
| **Belief-R**, Wilie et al., EMNLP 2024, arXiv 2406.19764 (**snippets**) | New premise: update or maintain? BU/BM/BREU over ~30 LMs and several prompting strategies; models that update well fail to maintain | Two-turn warranted vs unwarranted revision; prompting already tried | Social pressure, goals |
| **SMART**, Beigi et al., EMNLP 2025, arXiv 2509.16742 (**snippets only**; full text unreachable) | Uncertainty-aware adaptive MCTS for trajectories, then progress-reward RL with a binary outcome reward; LLaMA2 / Qwen2.5 per snippets | Search over reasoning to mitigate sycophancy | Label-free inference-time selection; whether it tests valid-correction acceptance is **unverified** |
| **Huang et al., "LLMs Cannot Self-Correct Reasoning Yet"**, ICLR 2024, arXiv 2310.01798 (**snippets**; the debate ≈ self-consistency point comes from a secondary review) | Intrinsic self-correction does not help; reported gains came from oracle feedback | Predicts our audit outcome | — |
| **System 2 Attention**, Weston & Sukhbaatar, arXiv 2311.11829 (**snippets**) | Inference-time: rewrite the context to keep only relevant content, then answer; reduces sycophancy | Prior art for "extract the decision-relevant premises, then decide" | Two-turn update typing; valid-update preservation |
| SycEval arXiv 2502.08177; Pressure-Tune arXiv 2508.13743; "Pressure, What Pressure?" arXiv 2604.05279; Koneru et al. arXiv 2603.20162; Sharma et al. ICLR 2024 arXiv 2310.13548; FlipFlop arXiv 2311.08596 (**all snippets**) | Two-sided flip metrics, or training that claims to resist pressure while keeping valid-feedback uptake; evidence vs pressure conflicts. Sharma et al. warn that optimizing against a learned scorer (incl. best-of-N) can increase sycophancy | Same framing; our `pushback_unspecified` is the FlipFlop probe | Goal changes; label-free search |
| Big-Big-SycoBench arXiv 2610.15634 (**unverified**: one news article); "Stubborn or Sycophantic?" NeurIPS 2026 (**not found**) | — | — | Do not cite until checked |

### Repo evidence

- `scoring.py:29` lists the change-licensing readings.
- `scoring.py:89-100` is `supported_edit`, which trusts the model's own reading.
- `scoring.py:125-142` is the hypothesis score: parse, grounding, self-report, quote.
- `conditions.py:163-179` is the vote tie-break.
- `conditions.py:285-359` is the 5→2×2 beam.
- `audits/FINDINGS.md` §1–3 has the numbers in §1(b) above.
- The root README already measured selective updating on 30 career scenarios: relevant vs
  irrelevant d′, pressure shift, and multi-turn pushback (Claude 0/29 yields vs 25/29 fact
  corrections). The new study's *evaluation* largely re-measures what the course project and
  SycoBench-600 already measure.

## 3. Novelty threats (ranked)

1. **The estimand is taken** (SycoBench-600, Ma et al., Belief-R).
2. **The method collapses to voting.** The heuristic has no correctness signal, and
   Huang et al. plus the audit point the same way.
3. **The task is trivially separable**, so any gain is attributable to lexical cues.

## 4. Narrowest defensible contribution

A rule-grounded advice testbed that adds a **legitimate goal-change** class (plus subthreshold
and retraction) to the selectivity framework already set by SycoBench-600 and Ma et al. On that
testbed, an honest compute-matched result: whether an explicit interpretation step does better
than majority vote over the same samples. The expected answer is no.

## 5. Candidate theses (ranked)

1. **Negative result (most feasible, low–moderate novelty).** "Label-free premise
   verification is self-consistency in disguise for selective revision."
   Evidence needed:
   - the approved pilot with the format-only ablation and majority vote from the saved
     candidates;
   - the scorer's within-turn AUROC for correct vs incorrect candidates, computed offline at
     no cost.

   Supported if search ≈ vote and AUROC ≈ 0.5. Workshop or negative-results scale.
2. **Diagnostic (moderate novelty, feasible).** "Are revision errors misreadings of the
   message or misapplications of the rule?"
   Evidence needed:
   - an oracle-interpretation prompt (gold reading injected, never the gold answer), about 220
     calls;
   - a false-correction class, so that reading the message is not lexical;
   - two models with different pressure profiles (the repo already shows Qwen deferring and
     Haiku opposing);
   - human-checked labels.

   I found no paper that makes this decomposition. That is absence of evidence from about 25
   searches.
3. **Positive method (only if thesis 1 fails).** It would require a scorer with a real
   correctness signal, a win over vote and format-only, and transfer to SycoBench-600 and the
   Ma et al. suite. Without external transfer, a reviewer will attribute gains to the
   synthetic cues. I do not recommend building this now.

## 6. Why I might be wrong

- Most papers were read only as snippets. SMART or Belief-R could overlap more or less than
  I think.
- The audit is 40 turns on one model with pre-fix instruments; no real-model data exists for
  the current instrument (seeded ties). Randomized ties could let search help.
- A reviewer may accept that user-owned goals in advice differ in kind from factual QA, which
  would make the goal axis worth more than I credit.

## 7. Confidence

- **Medium-high** that the estimand is covered (two primary-artefact checks).
- **High** that the scorer is a self-consistency check, not premise verification (from code).
- **Medium** that the goal-change class and the reading-vs-rule decomposition are unclaimed.

## 8. Recommended action and cost

- Drop "premise-level verification" as the claimed contribution.
- Run the approved pilot ($9–16 worst case) only as a test of thesis 1, with majority vote
  and the scorer AUROC (free).
- If any budget is added, spend it on the oracle-interpretation arm (<$1) and a
  false-correction class (CPU data regeneration on dev families only) for thesis 2.
- No new search algorithms.

## 9. Falsification

My recommendation is wrong under either of two outcomes:
- the pilot shows premise search beating **both** majority vote and the format-only ablation,
  with a family-bootstrap CI excluding zero and scorer AUROC well above 0.5;
- a verified paper already shows that inference-time explicit update-typing improves
  selectivity, in which case even thesis 2 is gone.

Separately, a paper that already decomposes revision errors by oracle vs model-inferred
message type would remove thesis 2.

## 10. Open questions

- Does SMART report valid-correction acceptance? It needs a full-text check.
- Is a goal change still distinguishable from pressure without the explicit "replacing my
  earlier priority" wording?
- Big-Big-SycoBench and the NeurIPS 2026 items need primary-source checks before anyone cites
  them.
