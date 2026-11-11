# Working thesis: inconsistency, the decision boundary, and what to do there

Status: proposal for the team, written 2026-11-11 after reading `docs/findings.md`,
`docs/PROPOSAL_GAP.md` and the negative-methods report. It adds a direction. It does not
replace `PROTOCOL.md`. Everything built for it is **exploratory** until blind labels exist.

## Problem

An adviser answers. The input then changes in a way that means the same: the user asks
again, pushes, rewords, reorders the options, or adds a fact that does not matter. The
answer changes. We call this **inconsistency**. A change is good only when a fact that
matters changed (a warranted revision). So the question is the same as the project's:
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
