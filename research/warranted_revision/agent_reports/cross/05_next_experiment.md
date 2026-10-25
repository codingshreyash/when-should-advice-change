# 05 cross-review: which next experiment, if any? (Agent 5, red team)

**Common facts.**
- challenge_v1 has 20 cases (5 families × 4), each with 1 base turn and 10 follow-ups: 220 turns, 200 of them follow-ups.
- Cost assumptions: 3.9 s per call on an L40S at $1.06/h, i.e. $1.15 per 1,000 calls, plus $0.53 setup per instance.
- Three benchmark defects come from 02:
  - **Separability (F1):** a keyword rule scores 200/200 on challenge_v1.
  - **Label ambiguity (F2):** "only if" is scored as "if and only if" (7/20 challenge cases), and certification uses gross cost despite the stated reimbursement (3/4 certification cases).
  - **Pressure ceiling (F3):** smoke-004 shows 0/36 moves under pressure.
- The three defects threaten experiments in different ways:
  - A metric that needs gold labels inherits F2.
  - A comparison between arms needs room below the ceiling (F3).
  - Any claim that the model "classifies readings" inherits F1.

| | Question it settles | Defects that hurt it | Calls | Expected / max $ | Controls | Stop rule |
|---|---|---|---|---|---|---|
| **A** approved pilot | Search vs best-of-N vs format-only ablation | **All three.** Under F3 every arm sits at ceiling; under F2 base errors are label errors; under F1 the readings are trivial. My 05 report adds: G = 5 families, power about 0.4 at +8 pp, false-positive rate 13–16%, and 4-shard assignment confounded with gold labels. | 6,160 = 220 × (1 + 9 + 9 + 9) | $9.2 (7.1 inference + 4 × 0.53) / $16 cap | Ablation; derived vote selectors | The proposal's "no movement" rule, but it is only evaluable after the shards have run |
| **B** (03) gold reading fixed, 9 samples | Is reading classification the bottleneck? | **F1 predicts a null:** reading accuracy is already about 100% on the relevant, priority and pressure classes (04), so supplying the gold reading cannot help. F3 leaves no headroom. Pushback and neutral turns have no clean reading to map to. | 1,800 if it reuses A's base turns and best-of-N comparator; standalone 1,980 + 1,980 for its own comparator = 3,960 | $2.6 / $5.1 standalone | Best-of-N-9 vote on the same turns; rate at which the forced reading is kept | Kill if the forced reading is kept in under 80% of samples |
| **C** (02) direct-only scaffold probe | **Is the ceiling caused by the scaffold or by the model?** That is, does pressure move the model once the options block and DECISION instruction are no longer attached to the pressure turn? Repeated pushback is included. | **Least affected.** Its primary metric is switching away from the model's own base answer, compared with a neutral mention, so it needs **no gold** and F2 does not touch it. F1 does not matter because it measures movement, not discrimination. | My trimmed version, 3 option-order replicates: 60 base calls + 60 × 10 scaffolded + 60 × 10 × 2 unscaffolded (free reply, then a decision turn) + 60 × 3 pushback turns × 2 calls = **2,220** (02 estimated about 2,700) | $3.1 / cap $5 | Neutral mention under each scaffold; both pressure directions; order replicates | Stop if final turns are under 95% strictly valid or planned and made calls differ. A zero-movement result is itself the answer, not a failure. |
| **D** (mine) random-reading control | Does depth-1 scoring beat random reading choice? | **Partly redundant, which I concede.** With seeded ties and byte-identical depth-1 calls, the format-only ablation already *is* random reading choice on the 94% of turns where all readings tie (format-001). Under F3 the expected difference is 0 and undetectable. | 1,980 = 220 × 9 | $2.8 / $5 | Full premise search; format-only ablation | Run only if C shows movement of at least 15% beyond neutral |
| **E** (01) oracle-reading prompt, 1 greedy call | Are errors misreadings or misapplications of the rule? | **Invalid before relabeling:** the observed errors are mostly F2 label items (2 of 3 failure points in smoke-004), so it would report label defects as "misapplication". Under F3 there are almost no pressure errors to split. | 220, plus 220 for a structured greedy comparator = 440 | $1.0 / $2 | Structured greedy arm without the oracle reading | Only after relabeling, and only on items reviewers agree on |
| **F** human relabeling | Label defect vs model error | It does not fix F1 or F3; those need new item designs (02 designs A–I). | 0 GPU; about 350 items, about 12 person-hours for 2 reviewers | $0 | Kappa; a separate ambiguous stratum | — |

**Applying the same scrutiny to D.** It answers a question whose answer the trace data already predict: the depth-1 scores carry no signal, and on all-tie turns the ablation equals random choice. It is worth calls only after C shows the pressure axis can move. Even then the format-only ablation plus a free offline replay of the beam probably answers it. **I withdraw D as a next step.**

**Ranking.**
1. **F**, starting now. It blocks every accuracy claim.
2. **C**, run alongside F. Its metric needs no gold and it settles the ceiling, and the ceiling gates A, B and D.
3. **E**, on relabeled items only: under $1, and the cheapest test of the misreading-vs-misapplication question.
4. **B**, only if C shows movement and E shows misreadings.
5. **D**, then **A**. Do not run A as configured. If it runs anyway:
   - first run its `direct` arm alone (220 calls, about $0.80) to evaluate its own "no movement" stop rule;
   - assign shards with a balanced permutation.

**What I would run first:** **C**, a direct-only probe of scaffolded vs unscaffolded pressure, 2,220 calls, about $3.1, cap $5, one instance, in parallel with human relabeling (F). It needs a small CPU-side change before launch: an unscaffolded follow-up mode that holds the decision for a separate turn, plus a gold-free movement metric. Nothing else should run on the GPU until relabeling is done and C has shown whether the pressure axis can move at all. If C shows no movement even without the scaffold (switching beyond neutral under 5%), drop the stability axis for this model and dataset rather than spending on A, B or D.
