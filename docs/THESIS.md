# Thesis: instability lives at the decision boundary

Status: working plan, written after the midterm. It replaces the midterm focus on
sycophancy. The midterm data and scripts stay valid. They become the test bed.

## The problem

An adviser gives a recommendation. Later the input changes in a way that means the
same thing: the user asks again, pushes, rewords, reorders the options, or adds a fact
that does not matter. The answer changes. We call this **inconsistency**.

A change is good only when a fact that matters has changed. So we must separate
three cases:

| Cause of the change | Name | Good or bad |
|---|---|---|
| No new fact, model gives in to the user | sycophancy | bad |
| No new fact, answer varies at random or with format | inconsistency | bad |
| A fact that matters changed | warranted update | good |

## Thesis

**Inconsistency is not spread evenly. It concentrates where the decision is close.
At that point the warranted answer is "I need more information". So the right fix is
not to force one fixed answer. The right fix is to make the model stable where the
facts decide, and to make it ask where they do not.**

Practical rule for builders: treat instability under equal-meaning input as a signal
that the model does not know. Gate on it.

## Definitions

- Let Z be the facts that matter for the decision. Let N be everything else:
  pressure, wording, option order, irrelevant facts, resampling.
- Warranted behavior: the answer is **invariant** to changes in N. The answer
  **changes** when Z changes, in the direction the decision rule gives. The answer is
  **ask** when Z is missing or when the margin between the top options is below a
  threshold tau.
- Margin: utility of the best option minus utility of the second option, in the
  scenario's own weights. For models with probabilities, the margin of the base
  distribution (p1 minus p2) is a proxy.
- This is counterfactual invariance (Veitch et al. 2021) plus a responsiveness
  condition. Z is a modeling choice. In generated scenarios we set Z by construction.

## Hypotheses

- **H1 (boundary).** Flips under N-changes are more frequent when the margin is small.
- **H2 (not stubborn).** A fix that lowers inconsistency must keep the update rate on
  relevant facts. A model that never changes fails.
- **H3 (ask at the boundary).** Near the boundary, "ask" beats a forced answer on a
  combined score of consistency and correctness.
- **H4 (transfer).** Training for invariance on one kind of N does not transfer to
  other kinds, unless the training also contains relevant-fact pairs.

## Experiments

1. **Generator.** Procedural scenarios with truth by construction and a controlled
   margin (`scripts/gen_procedural.py`). Four domains.
2. **Noise floor.** Five samples per prompt, random option order. Report change
   against the model's own resampling variation.
3. **Boundary test (H1).** Flip rate by margin bin. Sweep the size of a relevant fact
   (k steps) to get a switch curve per model.
4. **Fix comparison (H2, H3).** Three fixes on one benchmark: invariance training
   (LoRA on Qwen3.5-9B), vote over rewrites, ask when unstable. Three scores:
   inconsistency, update rate, ask quality.
5. **Transfer (H4).** Train on one kind of N, test on the others. Hold out a domain.
6. **Human check.** About 100 generated items rated by people for realism and for
   "does this fact bear on the decision" (1 to 7 scale).

## What we do not claim

These are already done by others (see `docs/literature.md`):

- Models are sensitive to wording, format, and option order.
- Models flip under "Are you sure?" and user pressure.
- Irrelevant context distracts models.
- Resistance and responsiveness should be measured together, with a noise floor.

Our new part, if the checks hold: the advice setting with an "ask" option, the link
between instability and abstention, and a comparison of fix families that tests
transfer and stubbornness.

## Known limits of the evidence so far

- Existing data: 30 scenarios, one sample per prompt, fixed option order, author
  labels. The margin result (AUROC 0.71 to 0.89 for 9B models) would not survive
  correction across variants.
- Claude flipped on 16 of 412 equal-meaning prompts (constrained) and 6 of 342
  (conversational). On this data Claude has little inconsistency to fix. The problem
  is in open models, and maybe in harder conditions we have not yet tried.
- The irrelevant-update prompts exist but no model has run them.
- In the generated set (`data/procedural/procedural_v0.jsonl`, 400 scenarios), 136 relevant
  updates flip to the other option and 264 move the answer into the "ask" band. One changed
  fact rarely flips a large-margin decision. Analyze the two kinds apart, or the relevant
  update mixes factual updating with asking (the flaw `PROTOCOL.md` lists for the pilot).
- Generated prose is more uniform than human text. Human validation is required.

## Next steps

1. Read in full the closest papers before any novelty claim (list in
   `docs/literature.md`).
2. Run the missing data: irrelevant updates, 5 samples, random option order.
3. Run the generated set on all models. Analyze with `scripts/analyze_instability.py`.
4. Train and compare the fixes.
