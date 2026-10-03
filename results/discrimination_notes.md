# Can the models tell a relevant change from an irrelevant one?

Reanalysis of the existing 30 career scenarios (pilot + career_v2, current Nimble
checkpoint `@bd792f44`, draft labels). No new model calls. Script:
`scripts/analyze_discrimination.py`; full output in `discrimination_career30.txt`.

The proposal's question is whether a model can tell changes that *should* move a
recommendation from changes that shouldn't. `analyze.py` scores each behavior on its own,
so a model can look good on pressure just by never moving. Here every variant goes on
one axis: how far did the answer move from base? Then we ask how well that movement
separates `relevant_update` (should move) from `pressure` / `reframe` (should not).

| | hit (RU changes) | false alarm (pressure) | false alarm (reframe) | d′ [95% CI] | AUROC of movement | movement ratio RU / pressure [95% CI] |
|---|---|---|---|---|---|---|
| Qwen3.5-9B base | 0.53 | 0.63 | 0.40 | 0.04 [−0.49, 0.54] | 0.46 [0.33, 0.59] | **0.66 [0.45, 0.92]** |
| Bespoke-Nimble-9B | 0.47 | 0.37 | 0.10 | 0.63 [0.06, 1.19] | 0.71 [0.58, 0.82] | 1.44 [0.88, 2.38] |
| Claude Opus 5, constrained | 0.76 | 0.07 | 0.04 | 2.22 [1.46, 3.38] | – | – |
| Claude Opus 5, conversational | 0.68 | 0.04 | 0.00 | 2.36 [1.61, 3.26] | – | – |

"Movement" is total-variation distance between the base and variant option
distributions (Nimble's scorer gives a full distribution). Intervals are 2,000 bootstrap
resamples over scenarios.

## What this shows

1. **The base model moves more for a stated preference than for a real fact.** For
   Qwen3.5-9B, the average shift in the option distribution under pressure (TV 0.54) is
   larger than under a decision-relevant fact change (TV 0.36). Per scenario, pressure
   moves it more than the relevant fact in 23 of 30 (sign test p = 0.005), and the
   ratio's interval sits wholly below 1. Its d′ is zero: from its choices alone you
   can't tell whether the user added evidence or just said what they wanted.
2. **The adapter fixes discrimination partly, not pressure.** Nimble was trained on
   minimal pairs where one relevant fact flips the answer, and it does separate relevant
   from irrelevant changes better than its base (AUROC 0.71 vs 0.46). But the gain comes
   mostly from reframe stability (false alarms 0.40 → 0.10); pressure still flips it 37%
   of the time, and its pressure-vs-relevant ratio is not significantly above 1.
   Training on "this fact matters" did not teach "this preference doesn't."
3. **Pressure overrides confident answers.** Pressure flips happen more when the base
   margin is small, but not only then: the median Nimble answer that flipped under
   pressure had a base log-odds margin of 3.1 over the target (about 95% vs 5%), and for
   the base model 1.7.
4. **Claude's stability isn't rigidity.** It changes its answer on 68–76% of relevant
   updates and almost never under pressure or reframe, so d′ ≈ 2.3 in both conditions.
   Constrained and conversational are indistinguishable, so for this model the
   discrimination isn't coming from writing out reasoning.
5. **AITA pressure has nothing left to move.** On the 50 YTA posts the decision-only
   models already side with the poster at baseline (Nimble 35/50 NTA, base 43/50), and
   the pressure sentence leaves both counts unchanged (mean ΔP(NTA) +0.04 and −0.05).
   Claude conversational goes the *other* way under pressure (26 → 21 NTA). That's too
   small to claim on 50 posts, but it's worth checking with more samples.

## Caveats

- Draft labels; `hit` here only needs the answer to *change*, which doesn't depend on
  the labels. Warranted-update accuracy does (see `analyze.py`).
- 30 scenarios. The base-vs-pressure finding survives the bootstrap and a paired sign
  test, but the Nimble-vs-base AUROC gap is suggestive, not nailed down.
- The authored pressure sentences differ in wording across scenarios, and they name
  the target option. `scripts/build_pressure_controls.py` separates the two: a
  templated preference sentence, a neutral mention of the same option with no
  preference, a preference toward the answer the model already gave, and a filler
  sentence. If mention moves the decision-only models as much as preference does, their
  "sycophancy" is lexical priming, not deference to the user.

## Next experiments (scripts ready, need GPU / API)

- `run_gpu_experiments.sh`: Nimble's scorer on the controls, then `run_steering.py`,
  which estimates a "user wants X" direction in each 9B model from six held-out
  phrasings and projects it out of the residual stream (cross-validated by scenario,
  random-direction control). The test is whether pressure flips drop while
  relevant-update hits stay where they were. That would mean preference and evidence
  are separable inside the model, and that you could remove the first without losing
  the second.
- `run_pushback.py`: Claude in a second turn (directional pushback, plain "are you
  sure?", a fact correction, a restatement, and 3-turn escalation). Single-turn
  pressure is at floor for Claude, so if its discrimination breaks anywhere, it should
  break here.
