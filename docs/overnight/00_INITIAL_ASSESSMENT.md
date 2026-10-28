# Initial assessment (written before the overnight loop)

**Date.** 2026-10-28.
**Basis.** Raw legacy rows in `results/career/nimble-and-qwen__career_{pilot,v2}.jsonl`
(recomputed here, not copied from summary tables), `docs/findings.md`, the
preregistration, and the decision-procedure code.

**Not verified.** The literature claims in the handoff could not be checked from this
environment: arxiv.org is outside the network allowlist, and a web search did not find
"Are AI Decision Models Biased? A Case Study of Jev". The overnight pass 1 is told to verify
them or mark them unverified.

**For the overnight passes.** Pass 1 is told not to read this file, so that its verdict is
independent. Pass 5 compares the two.

## What the raw legacy data actually show

There are 30 scenarios and one sample per scenario. The option order is fixed, the labels
are draft labels, and the Nimble checkpoint is `bd792f44`. These are exploratory results.

| | Qwen3.5-9B base, through Nimble's scorer | Bespoke-Nimble-9B |
|---|---|---|
| Answer changed: pressure | 19/30 | 11/30 |
| Answer changed: **reframe** (same facts, reworded) | **12/30** | 3/30 |
| Answer changed: relevant update | 16/30 | 14/30 |
| Base answer matches the draft label | 22/30 | 27/30 |
| `need_more_information` on omission / on the **complete** base prompt | 10/30 / **8/30** | **0/30 / 0/30** |
| Mean change in P(pressure target), pressure vs base | +0.50 | **+0.29** |
| P(target) rose when the pressure did *not* change the choice | 9 of 11 | **19 of 19** |

### What follows from these numbers

1. **Arm A is a weak baseline.**
   - Base Qwen, read out through a single-token scorer it was never trained for, changes
     its answer on 40% of pure rewordings.
   - Its 63% pressure change rate therefore cannot be separated from general instability.
     The legacy runs have no neutral-mention or irrelevant-update control for the 9B models.
2. **"Nimble resists pressure" is true only at the argmax.**
   - The probability of the pressure target rose in all 30 pressure prompts for Nimble.
   - That includes all 19 where its choice held.
   - Choice-level metrics therefore understate its pressure sensitivity.
3. **"Qwen asked for missing information on 10/30" is not discrimination.**
   - It also asked on 8/30 complete prompts.
   - Nimble never chose `need_more_information` at all.
   - Note that 6 pilot relevant-update labels *are* `need_more_information`, which caps
     Nimble's correct-update count at 24.
4. **The handoff's legacy table is arithmetically correct**, but it omits the reframe and
   base-rate columns, which change its reading.

## Answers to the handoff's questions

1. **Is Qwen-vs-Nimble worth finishing?**
   - As a course study, yes. It is cheap ($2–4), already built, and fills a gap the
     proposal promised.
   - The current primary contrast (D vs A), however, has a largely predictable answer:
     - Nimble was trained on minimal pairs where one fact flips the answer;
     - arm A uses the base model through an interface it was not trained for;
     - Nimble's own README reports 90% vs 66% for the same contrast on its holdout.
   - The more informative contrast is **D vs B**: does the decision adapter beat simply
     asking the base model, in its native chat format, for one code? That arm is already in
     the 4,800-call design.
   - Making it primary is a pre-run amendment, and it is the PI's decision.
2. **Does the literature already answer the question?**
   - The general question (update on evidence, resist pressure) is well covered, if the cited
     papers say what the handoff says (not verified here).
   - What remains is narrow: adapter vs base vs procedure, on out-of-domain personal advice,
     with neutral-mention and irrelevant-update controls.
   - That is a course-report contribution, not a paper.
3. **Is an adapter-vs-base comparison informative?**
   - D vs A mostly measures "trained for this read-out" vs "not trained".
   - It isolates the adapter cleanly, but at an uninteresting point.
   - D vs B is the practical comparison.
4. **Is the phenomenon real or an artifact?**
   - The legacy gaps are confounded by base-model instability (the reframe changes), a fixed
     option order, one sample, and draft labels.
   - The probability-shift observation is the most robust of them: it held in 30/30 prompts.
5. **Are 30 scenarios enough?**
   - For a large D–A effect, yes.
   - For effects below about 0.15 in Δ, no (preregistration §6).
   - D vs B could be small, so a null there would be "inconclusive at this precision".
6. **Are human labels a hard blocker?**
   - Only for claims that depend on labels: correctness, eligibility and confirmatory status.
   - Change rates, the pressure-vs-mention shift, reframe stability, probability shifts and
     ask rates on omission vs base need no labels.
   - Still, running before the labels would let the outputs be seen before the scenario
     validity is settled.
   - The labels cost $0 and about 2 hours per person. They are the highest-value remaining
     step.
7. **Is there a hidden discovery?**
   - **Probability moves while the choice holds** is real in the legacy data. It costs no
     extra calls: the scorer arms log probabilities, and the run includes the
     `mention_target` control. It belongs in the report as a *secondary, exploratory*
     analysis. Its novelty is doubtful if the Jev-bias paper covers probability shifts.
   - **Nimble never asks:** this probably reflects training and interface, and the planned
     run measures it.
   - **Claude's refusals:** these need API spending, there is no key, and the finding is
     Claude-specific. Drop it.
8. **Priorities.**
   - A strong course report is: labels → pilot → full run → an honest preregistered result,
     with probability shifts reported alongside choices.
   - A publishable paper is not realistic from this project with this budget and these
     overlaps.

## Options

| option | verdict |
|---|---|
| **A**, finish the controlled experiment | **Yes**, as the course study, with D vs B proposed as primary (PI decision before the pilot) |
| **B**, investigate one failure | No separate study. The probability-shift observation is analysed inside A's run at no extra cost |
| **C**, course report only | **Yes, combined with A**: stop publication-oriented work |
| **D**, a different direction | No. No candidate has both a verified literature gap and preliminary evidence |

**Preferred: A + C.**

**Strongest objection.** Even D vs B may be unsurprising: decision-tuned models beat
prompting on their own task. The answer is that the course study's value is a clean,
preregistered, honestly reported comparison, not novelty.

**Scientific value.** Modest. A careful course result; at best a workshop note.

**Stop condition.** After the full run and the preregistered analysis, write the report and
stop, whatever the result. Stop earlier, and write up what exists, if any of these happens:
- the two human labels are not complete within **7 days**;
- the pilot fails its gate twice;
- the run would need more than the $5 allocation.

No new scenarios, models or benchmarks.

**No GPU run overnight.** A label-free exploratory run could estimate the change-rate
contrasts. But it would expose outputs before the labels exist, and it adds nothing the
confirmatory run will not give a week later.
