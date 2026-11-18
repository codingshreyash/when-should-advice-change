# Working thesis: inconsistency, the decision boundary, and what to do there

Status: proposal for the team, written 2026-11-11 after reading `docs/findings.md`,
`docs/PROPOSAL_GAP.md` and the negative-methods report. It adds a direction. It does not
replace `PROTOCOL.md`. Everything built for it is **exploratory** until blind labels exist.

## Problem

An adviser answers. The input then changes in a way that means the same: the user asks
again, pushes, rewords, reorders the options, or adds a fact that does not matter. The
answer changes. We call this **inconsistency**. A change is good only when a fact that
matters changed (a warranted change). So the question is the same as the project's:
did the answer change for the right reason? The new angle is *where* it fails, and *what
to do about it*.

## What the team's data already says

- Claude Opus is almost stable. It is right on 192 of 192 constrained threshold-sweep
  prompts. Pressure moves it on 2 of 28 prompts (`docs/findings.md`).
- The 9B models are not stable. Pressure flips are more common at low base margin
  (Nimble 0.62 vs 0.21, Qwen 0.86 vs 0.40), but they are "not limited to" low margin.
- Haiku errs far from the threshold too (switch point off by x1.44).

So inconsistency is a problem of smaller and open models. A fix is worth testing on
them. On Opus there is little to fix.

## Thesis (to test, not assumed)

**Instability under equal-meaning input is a usable signal of closeness: it marks the
decisions where the facts do not settle the answer. A builder can gate on it. We test
whether the best response there is a stable answer, an answer with a stated doubt, or a
question.**

Claims we do **not** make:

- "Near the boundary the correct answer is need_more_information." The team's rule says
  that label is for a missing deciding fact, "not because the decision is hard"
  (`docs/labeling.md`). A close call with all facts present is a different case. We
  treat the right response there as an open question and ask humans (see H3).
- Two-sided updating (stay on irrelevant, move on relevant) is new. BeliefTrack and the
  team's own controls already cover it.
- Models are sensitive to wording, order, or pressure. Known (see `docs/literature.md`).

## Hypotheses

- **H1 (boundary).** For non-relevant changes, flip rate falls as margin grows. Partial
  support from the team for pressure in two 9B models. Untested for reframe, irrelevant
  facts, order and resampling. Test on a large margin-controlled set with a noise floor.
- **H2 (not stubborn).** A fix that lowers inconsistency must keep the update rate on
  relevant facts. Report both.
- **H3 (response at the boundary).** Humans rate, for close calls with all facts present,
  whether "stable answer", "answer plus doubt" or "ask" is the best response. We use
  those ratings, not our own rule, as the label.
- **H4 (transfer).** Training for invariance on one kind of change does not transfer to
  other kinds unless the training also has relevant-fact pairs. No training exists in
  the repo. Resist and Update and bias-augmented consistency training may overlap; read
  them first.

## Evidence needed, in order

1. Noise floor: five samples per prompt, deterministic option permutations
   (`PROTOCOL.md` already asks for this). No model has it yet.
2. Run the missing variants on the 9B models and Haiku: irrelevant update, subthreshold
   update, threshold sweep.
3. Run the generated set (`docs/procedural_scenarios.md`) for H1 with real power. Mark
   results exploratory. Keep them apart from the confirmatory summary.
4. Human ratings on about 100 generated items: realism, relevance, and H3's question.
5. Fix comparison on the 9B models: invariance training, vote over rewrites, gate on
   instability. Three scores: inconsistency, update rate, quality at the boundary.

## Risks the team's own reports raise

- Items from explicit rules invite shortcuts. In v2, arithmetic plus a phrase list
  reproduced 70% of gold labels. The generated items are built from explicit weights, so
  the same risk applies. Human validation and a shortcut check come before any claim.
- Do not tune items until an effect appears.
- Response format is a validity gate. Check parse rates first.
- The strongest model barely flips. A result that rests on Opus will be flat.

## How this fits the open items in `docs/PROPOSAL_GAP.md`

- Threshold and boundary work (row 6) is open for the 9B models, Sonnet and Haiku. The
  generated margin-controlled set serves it.
- Length-matched omissions (row 4): the generator controls what is omitted.
- More scenarios without hand labels: truth by construction, with the limits above.

## First results (2026-11-14, exploratory, 9B models only)

Source: `results/summaries/instability_career30_5perm.txt` and
`instability_procedural_third.txt`. Nimble@bd792f44 and Qwen3.5-9B base. No Claude or other
model has been run with a noise floor yet.

- **Noise floor exists and is not zero.** Same prompt, five option orders: the answer differs
  in 6% (Nimble) and 14% (Qwen) of pairs. Inconsistency above that floor is 0.10 [0.05, 0.15]
  and 0.15 [0.09, 0.21] on the 30 career scenarios. Part of what earlier tables call
  inconsistency is order sensitivity.
- **H1 holds for Nimble, on true margin.** On 134 generated scenarios (margin set by
  construction, not read from the model), flip rate falls as the margin grows: Spearman
  rho -0.45 (permutation p = 0.0002), AUROC 0.77, flip rate 0.26 below tau and 0.06 above.
  The career set agrees (rho -0.64) but uses the model's own base margin there, which is
  partly mechanical: near-tied probabilities flip an argmax easily.
- **H1 does not hold for Qwen.** Rho -0.20, AUROC 0.55; flip rate 0.50 below tau and 0.42
  above. Qwen's pressure flips are 0.59 to 0.85 in every margin bin. Its inconsistency is driven
  by pressure, not by closeness. So "instability marks close calls" is a property of Nimble
  here, not of both models.
- **Irrelevant facts move Nimble little on generated data** (0.04; 0.00 once the answer must
  stay in the acceptable set) and Qwen more (0.23). Subthreshold edits: 0.02 and 0.12 on career.
- **Ask behavior.** Qwen asks on 27-31% of omissions and on 14-18% of complete prompts; Nimble
  never asks. The "ask at the boundary" idea has no support from these two models.

Cautions: one run, 9B models only, 134 generated scenarios with one option order, a scorer
that always returns an answer. The generated margins come from our own weights and prose
templates, and the human check has not been done. Do not cite these as confirmatory.

### Is pressure directional? (`scripts/analysis/pressure_direction.py`)

Share of answers that land on the option the user named, minus the base share, over
scenarios whose base answer is not that option. Output: `results/summaries/pressure_direction_9b.txt`.

| | pressure, career (5 orders) | pressure, generated (1 order) | reframe / irrelevant fact |
|---|---|---|---|
| Qwen base | +0.50 [+0.35, +0.64] | +0.82 [+0.75, +0.89] | about 0 to +0.11 |
| Nimble | +0.39 [+0.24, +0.55] | +0.18 [+0.11, +0.25] | about 0 to +0.07 |

- **Pressure pushes toward the named option in both models.** Reframes and irrelevant facts
  do not. So the pressure effect is not generic shaking.
- **Qwen's push does not depend on the margin** (+0.86 below tau, +0.80 above). Nimble's does
  (+0.47 below, +0.12 above).
- **Two failure types, not one.** Nimble's problem looks like closeness: it moves when the
  decision is close, under pressure and under reframes. Qwen's problem looks like deference
  to the named option at every margin. A gate on instability could help the first. It cannot
  help the second, which needs the pressure removed or ignored.
- **What this does not show.** The named option is also repeated in the prompt, so priming
  and deference are not separated. The neutral-mention control (`data/derived/pressure_controls.jsonl`)
  has not been run on the 9B models. Run it before calling this sycophancy.

### Neutral rewrite by Qwen3.5-9B: negative result (2026-11-14)

Qwen3.5-9B base rewrote every prompt with one fixed instruction ("keep every fact and stated
priority; remove any statement about what the person wants to hear"), then Nimble and Qwen scored
the rewrites with the same option orders as the originals. Files: `data/derived/rewritten_*.jsonl`,
`results/rewrite/`, `results/summaries/rewrite_check.txt`, `rewrite_pressure_direction.txt`.

| shift toward the named option | original | rewritten |
|---|---|---|
| Qwen, career (5 orders) | +0.50 | +0.48 |
| Qwen, generated (67 scenarios, 1 order) | +0.82 | +0.78 |
| Nimble, career | +0.39 | +0.32 |
| Nimble, generated | +0.23 | +0.25 |

- **The fix did not remove the pressure.** The rewriter kept the pressure sentence in 83% of
  career prompts and 88% of generated prompts (example: "They really want to hear that the new
  company is the right choice." copied word for word). It followed "keep every fact and
  priority" over "remove the statement".
- **It also dropped some facts.** On generated prompts, 84% of base rewrites keep every attribute
  value (81% for relevant updates). The update rate did not change much (Nimble 0.77 to 0.70,
  Qwen 0.47 to 0.43); the sample is small.
- **What this shows and does not show.** It shows that a 9B model prompted once is a poor
  canonicalizer. It does not show that canonicalizing cannot work. Untested: a stronger
  rewriter, an instruction that first lists the sentences to delete, a two-step "extract facts,
  then answer from the facts" pipeline, and rewriting by a model other than the one being
  tested. This matches the team's own negative-methods lesson about self-checking pipelines.
- **The neutral-mention control was not run** (the session hit its time budget before that
  stage). Priming against deference is still open.

### Full generated set and the neutral-mention control (2026-11-15, exploratory)

Files: `results/procedural/nimble-and-qwen__procedural_{third,rest}.jsonl` (400 scenarios, 1 option
order), `results/pressure_controls/nimble-and-qwen__pressure_controls.jsonl`, and
`results/summaries/instability_procedural_full.txt`, `pressure_direction_procedural_full.txt`.

**H1 on 400 scenarios (margin set by construction).**

| | flip rate, margin < tau | margin >= tau | Spearman rho (p) | AUROC closeness to flip |
|---|---|---|---|---|
| Nimble | 0.27 | 0.07 | -0.50 (0.0002) | 0.77 |
| Qwen base | 0.49 | 0.45 | -0.13 (0.0096) | 0.54 |

Nimble's instability is a closeness effect. Qwen's is not: it flips about half the time at every
margin, mostly under pressure (0.53 to 0.82) and reframes. Pressure moves Nimble +0.52 toward the
named option below tau and +0.13 above; Qwen +0.92 and +0.79. Irrelevant facts barely move Nimble
(0.03 flips; 0.01 outside the acceptable set).

**Neutral mention control (30 career scenarios, 1 sample, wide intervals).** Shift toward the
named option:

| | "They want to hear X" | "I want you to tell me X" | neutral mention of X | filler |
|---|---|---|---|---|
| Qwen base | +0.90 | +0.86 | +0.48 [+0.31, +0.66] | +0.03 |
| Nimble | +0.26 | +0.11 | +0.22 [+0.07, +0.37] | 0.00 |

- **Naming the option alone moves both models.** For Nimble this explains most of the effect:
  mention (+0.22) and preference (+0.26) are within noise of each other. For Qwen about half is
  naming (+0.48) and the rest is the stated preference (+0.90).
- So "pressure" in these models is partly priming. Do not call the Nimble effect sycophancy.
- Limits: one sample per prompt, 27 to 29 eligible scenarios, one scenario set.
