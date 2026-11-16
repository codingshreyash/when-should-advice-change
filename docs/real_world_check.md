# Real-world check (scope, written before any run)

Status: scope only. Nothing here has been run. Written 2026-11-16.

## Why

Every result so far uses generated scenarios. They are templated. The truth is built in.
A reviewer can say: "This only holds on your generator."
This check asks one thing: **do the second-look findings hold on questions people wrote, with answers we did not build?**

## Claims to test

Same claims as `docs/second_look.md`. We do not add new claims.

- C1. A re-ask does not fix a model's own wrong answers better than a fresh resample (experiment 4).
- C2. A re-ask repairs a planted wrong answer (experiment 3).
- C3. Some mid-size models break right answers under "look again" (experiment 1 / 3 loss).
- C4. Break-even accuracy separates models where asking pays from models where it does not.

## Two arms

### Arm A: real questions with a known answer (main arm)

- Source: public multiple-choice sets with a gold answer that a person wrote. Pick two with an advice flavor. Candidates, to verify before use: a medical-choice set, a commonsense or everyday-decision set.
- Size: 600 items per set, 4 options each (fewer if the set has fewer clean items). Fixed seed, drawn once, list committed.
- Why it fits: a "own error" is a real error on a real question. The gold answer is not ours.
- Limit: it tests facts and reasoning, not advice under trade-offs. We say so in the paper.
- Run: the same runners as experiments 3 and 4. Only the loader changes (an adapter that outputs our scenario schema with `expected.base`, `options`, `option_text`). No `margin` field, so the boundary analysis is skipped here.
- Models: the six from experiment 4. Same wordings (neutral, look_again, review).
- Cost: about 5 calls per item per model (turn 1, resample, 3 re-asks) plus planted-error calls. About 3,000 calls per model per set.

### Arm B: human-written advice scenarios (small, close to our topic)

- Source: 60 advice questions written by the team, in the four domains. Each has a short list of facts and 3 options.
- Labels: two team members label blind, using `docs/labeling.md` (acceptable set, `need_more_information` only for missing facts). Keep only items where both agree. Report the agreement rate.
- Why it fits: it is real advice with real trade-offs. It also gives us the human check we lack.
- Limit: small. Wide intervals. Report it as a check, not as the main evidence.
- Run: the 6 models, 5 samples per turn-1 prompt (to see instability), then the same re-ask branches.

## Pre-set hypotheses

- R1. On Arm A, own-error recovery by re-ask is at most the fresh-resample rate plus 0.10 for every model except one that collapses (as in Gemma 2 9B).
- R2. On Arm A, the sign of the value-add (re-ask minus resample) matches experiment 4 for Llama 3.1 8B and Mistral 7B (negative).
- R3. On Arm A, Gemma 2 9B again has break-even accuracy below its own accuracy.
- R4. On Arm B, no model has a re-ask recovery above its fresh-resample rate by more than its 95% interval.

A hypothesis fails if the interval crosses the stated bound. We report failures.

## What counts as a replication

- Replicated: R1 and R2 hold on at least one Arm A set.
- Partly replicated: the direction holds, the size does not.
- Not replicated: the sign flips. Then the paper says the finding is specific to generated scenarios.

## Decisions we need from the team

1. Which two Arm A sets. (We check licence and answer quality first.)
2. Who labels Arm B. Two people, about 2 hours each for 60 items.
3. Whether Arm B items may be shared publicly.

## Known risks

- Arm A models may have seen these sets in training. A high accuracy then means few own errors and wide intervals (the Haiku problem). Mitigation: prefer sets that are harder or newer, and report the own-error count first.
- Sampling default of the API still sets the resample baseline. We keep the same default and say so.
- Parse failures bias results (Llama 3.1 8B lost 13%). We report them per model and rerun failed items once.

## Order of work

1. Pick the sets and write the adapter. Dry-run on 20 items.
2. Run Arm A on one cheap model. Check own-error counts are at least 40. If not, change the set before spending more.
3. Run Arm A on all six models.
4. Label Arm B in parallel. Run it after labels are final.
5. Append results to this file. Do not edit the hypotheses above.
