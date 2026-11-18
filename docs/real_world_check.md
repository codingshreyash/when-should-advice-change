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

---

## Progress log

### 2026-11-18: Arm A sets chosen, loader built, gate passed

Sets (both checked for licence and a gold answer; raw files are not in the repo):
- `medqa`: GBaker/MedQA-USMLE-4-options, test file, CC-BY-4.0, 4 options. Many items ask for the best next step in management, so it is advice-like. 1,273 items, 600 drawn.
- `csqa`: tau/commonsense_qa, validation split (the test split has no labels), MIT, 5 options. 1,221 items, 600 drawn.
Both drawn with `random.Random(1684)`. Lists: `data/scenarios/realworld/{medqa,csqa}.jsonl`. Converter: `scripts/data/gen_realworld.py`. For MedQA the gold text matches the raw answer text for all 600 items.
Option codes are `choice_a`, `choice_b`, ... and there is no `need_more_information` option.
`run_own_error_reask.py` got a `--pools TAG=file,...` flag. Default behaviour is unchanged.

Known weakness of `csqa`: some questions have more than one defensible answer, so a model "own error" may be a label error. We report csqa and medqa separately and do not pool them in the headline.

Gate (step 2 of "Order of work"): Mistral 7B, first 100 items of each set (200 items), live.
- Own accuracy 0.56. Own errors E = 85 (needed at least 40). Gate passed.
- 0 error rows. Unparsed turn-1 answers: 5 of 200 (2.5%).
- Summary: `results/summaries/realworld_gate_mistral.txt`.
- This is a gate check on a subset. It is **not** a result and we do not test R1 to R4 with it. The intervals are wide. It shows the same sign as experiment 4 for Mistral (re-ask below resample), but we do not count that.

Next: step 3, all six models on the full 1,200 items. Expected size is about 3,000 to 4,000 calls per model, so about 20,000 calls in total. Not started.

### 2026-11-19: Arm B items drafted (60 items, labels still missing)

How the items were made. Four separate drafting agents each wrote 15 items for one domain (career, housing, medical choice, purchase) from public web sources. They paraphrased the sources and invented the names. The items are in `data/labeling/armb/*_items.jsonl`.
- Per domain: 8 clear, 3 close, 4 missing-fact items. Each has 2 real options and `need_more_information`.
- The drafters also proposed answers. These are in `data/labeling/armb/keys/` (kept local, git-ignored). They are **proposals, not labels**. Labelers must not see them.
- Sources: 4 dead links were removed. 28 of 53 links opened for us. 22 more are blocked to scripts (BLS, CDC, Mayo and similar), so they are **unverified**. Each item has a `source_check` field. Numbers in housing and purchase items are illustrative, not real listings.
- Known weak items (drafter's doubts): housing 10 and 15; purchase 13 and 14; medical 05, 09 and 13; career 05 and 12 to 15. Keep them. Disagreement between labelers is the filter.

What this arm can and cannot show.
- The items are AI-drafted. They are **not independent of AI models**. Only the blind human labels make this a human check. Without two agreeing human labels per item, Arm B is not reported as a result.
- The listed order favored the first option in 23 of 32 clear items. The labeling sheet shuffles option order (seeded). The runner also randomizes it.
- Medical items are hypothetical lay decisions. A person with health training should read them before use.

Labeling steps for the team:
1. Run `python3 scripts/data/build_armb_sheet.py` (or take `data/labeling/armb/labeling_sheet.csv`).
2. Two people copy the sheet. Each fills `acceptable` alone, with the rules in `docs/labeling.md`. Use `|` between codes. Mark `unsure` if needed.
3. Do not talk about answers until both finish.
4. Send the two filled sheets back. We keep items where both agree and report the agreement rate. We then compare the agreed labels with the drafters' proposals as a side check.

---

## Arm A results (2026-11-19): five of six models

Run: MedQA and CommonsenseQA, 600 items each, same runner and wordings as experiment 4. Models: Haiku 5.5, GPT-5.4 Mini, Gemma 2 9B, Llama 3.1 8B, Mistral 7B. **Gemma 4 31B is not in this table.** Its calls were very slow on the full prompts (28 of 1,200 turn-1 calls done after about an hour). We did not wait for it. This is a change from the plan of six models.
Files: `results/summaries/realworld_own_error_5models.txt` (pooled), `results/summaries/realworld_own_error_by_pool.txt` (split), `scripts/analysis/own_error_by_pool.py`. Rows: no error rows after one resume pass. Unparsed answers are at most 2.3% of turn-1 calls per model (Llama 28, Gemma 2 18, Mistral 11, Haiku 8, GPT 0).

### Own accuracy and number of own errors (E)
| Model | Own accuracy | E |
|---|---|---|
| Haiku 5.5 | 0.91 | 110 |
| GPT-5.4 Mini | 0.84 | 189 |
| Gemma 2 9B | 0.70 | 359 |
| Llama 3.1 8B | 0.59 | 476 |
| Mistral 7B | 0.51 | 589 |
The gate (at least 40 own errors) is met by every model. The capable models have many more own errors here than in experiment 4 (110 and 189, not 21 and 28). This is the first set that can test them.

### Recovery and loss, pooled (95% CI over items)
| Model | Fresh resample: recovery / loss | "Look again": recovery / loss | Value-add of "look again" (recovery) |
|---|---|---|---|
| Haiku 5.5 | 0.14 / 0.07 | 0.25 / 0.06 | +0.11 [+0.01, +0.20] |
| GPT-5.4 Mini | 0.23 / 0.06 | 0.39 / 0.16 | +0.15 [+0.07, +0.24] |
| Gemma 2 9B | 0.12 / 0.05 | 0.38 / 0.51 | +0.26 [+0.20, +0.31] |
| Llama 3.1 8B | 0.33 / 0.19 | 0.18 / 0.10 | -0.15 [-0.20, -0.11] |
| Mistral 7B | 0.25 / 0.22 | 0.19 / 0.20 | -0.06 [-0.10, -0.01] |
The neutral wording ("give me your final recommendation") revises little and has about zero net effect for every model. "Review for mistakes" behaves like "look again" for Gemma 2 9B and like a resample or worse for the others.

### Against the hypotheses fixed before the run
- **R1 (re-ask recovery is at most resample + 0.10, except for one collapsing model): NOT SUPPORTED.** The capable models exceed the bound with "look again": Haiku +0.11, GPT-5.4 Mini +0.15 (pooled). By set: the gain is clear on CommonsenseQA (+0.17, +0.16, intervals above 0) and weaker on MedQA (Haiku -0.04 [-0.19, +0.11]; GPT +0.14 [0.00, +0.28]). It holds for Llama and Mistral.
- **R2 (value-add is negative for Llama 3.1 8B and Mistral 7B): SUPPORTED.** Pooled intervals are below 0 for all three wordings. By set: all negative for Llama; for Mistral all negative except "look again" on CommonsenseQA (-0.01, no difference).
- **R3 (Gemma 2 9B has break-even accuracy below its own accuracy): SUPPORTED.** Break-even 0.42 ("look again") and 0.46 ("review") against own accuracy 0.70. It fixes 38% of its errors and breaks 51% of its right answers.
- **R4 (Arm B): NOT TESTED.** No labels yet.
Replication call, by the rule written before the run: **partly replicated.** The direction holds for the weaker models (R2, R3). It does not hold for the capable models (R1).

### What this changes
1. **Our earlier headline was too broad.** In experiment 4 the capable models looked like a fresh resample. That set had too few errors (5 to 28). With 110 and 189 errors, "look again" fixes **more** of a capable model's own mistakes than a fresh try does.
2. **The capable models revise selectively.** Haiku revises 31% of its wrong answers and 6% of its right ones. Of its revisions on wrong answers, about 80% end right. This is much better than chance, so the model uses the cue. GPT-5.4 Mini revises 53% of wrong and 16% of right answers.
3. **A gain in fixes still costs right answers.** Using the point values, the expected accuracy change from a "look again" turn, against keeping the first answer, is about -0.03 for Haiku, -0.07 for GPT-5.4 Mini and -0.24 for Gemma 2 9B. It is near 0 for Llama 3.1 8B and Mistral 7B. These are rough, because the intervals are wide.
4. **For the weaker models the anchoring result holds.** A fresh try beats a same-chat re-ask for Llama and Mistral.
5. **No second try is free.** A fresh resample also has a net cost for the capable models (their own errors are few and their right answers are many).

Practical reading, replacing the earlier one: do not use "look again" on a model that is probably right. The neutral wording is the safe one. If you do want a second try, a weak model does better in a fresh chat. A strong model fixes more with "look again", and pays for it.

### Cautions
- Pooling hides the set difference. The capable models' gain is mostly on CommonsenseQA, which has label noise. A move to a different answer there can reach the gold label by chance of ambiguity. MedQA is cleaner, and its capable-model intervals are wide.
- The resample baseline depends on the API's default sampling. At greedy decoding it would repeat the first answer.
- The "net accuracy change" numbers combine two separate samples and are rough.
- Gemma 4 31B is missing. Arm B is not run. These are still multiple-choice questions, not open advice.

### 2026-11-20: Arm B labeled by two AI labelers (NOT a human check)

Two separate AI agents (different models) labeled the 60 items alone, from the blind sheet and `docs/labeling.md` only. They did not read the drafters' answers (each used about 4 tool calls: rules, sheet, write, check). Files: `data/labeling/armb/ai_labels_A.csv`, `ai_labels_B.csv`. Script: `scripts/analysis/armb_agreement.py`. Output: `results/summaries/armb_ai_agreement.txt`.

- **Agreement between the two labelers:** identical sets on 53 of 60 items (0.88). They overlap on all 60. Cohen's kappa over item-by-option decisions is 0.92.
- **Where they differ:** 7 items. Both labelers marked 15 rows unsure; they agree exactly on 8 of those 15 and on all 45 other rows. So the unsure flag works as a signal.
- **Labeler style:** A gave more two-option labels (13, against 6 for B). Both gave "need more information" alone about as often (12 and 14). The drafters planned 16.
- **Against the drafters' proposals** (proposals, not labels): A matches exactly on 53 of 60, B on 52 of 60. Of the 53 items where A and B agree, 50 equal the proposal, and all 53 overlap it.
- **Items kept for Arm B if we used these labels:** the 53 with identical sets. The 7 with disagreement would be dropped.

What this does and does not show.
- The agreement is high, but it is **agreement among AI systems**. The drafters, the two labelers and the models we test share training habits. High agreement here proves less than the same agreement between two people. It shows the items are not broken or ambiguous to a careful reader, and that the labeling rules are usable. It does not show that people would label them the same way.
- **R4 stays untested.** We have not run the models on Arm B. If we run them, the result must say "AI-labeled".
- The human sheets are still needed. If two humans also agree with these labels, we can drop the "AI-labeled" tag.

---

## Update 2026-11-20: Gemma 4 31B finished on the real questions

Files: `results/summaries/realworld_own_error_6models.txt`, `realworld_own_error_by_pool_6models.txt`. The model made 163 own errors (own accuracy 0.86), so it can be tested.
- Fresh resample: recovery 0.24, loss 0.07. "Look again": recovery 0.20, loss 0.02. Value-add of "look again": **-0.04 [-0.12, +0.04]**, no clear difference. "Review": -0.13 [-0.20, -0.06]. Neutral: -0.21 [-0.28, -0.14].
- It breaks almost no right answers (2% with "look again"). It does not show the gain that Haiku 5.5 and GPT-5.4 Mini show.
- **Effect on the Arm A conclusions.** R1 is still not supported overall (Haiku 5.5 and GPT-5.4 Mini exceed the bound), but it holds for Gemma 4 31B. So "strong models gain from look again" is **not** a general result. It holds for two of the three strong models. Do not write "capable models" without naming which ones.

## Arm B results (2026-11-20): AI-labeled items, six models

Items: the 47 decisive items where both AI labelers agreed (35 with a concrete best option, 12 where "need more information" is right), in 5 copies each with a different option order (235 prompts per model). Same runner and wordings as Arm A. Analysis: `scripts/analysis/armb_own_error.py` (cluster bootstrap over original items; the copies are not independent). Output: `results/summaries/armb_own_error.txt`. Raw rows: `results/armb/`. 0 error rows.
**All labels here are AI-made, so this is not a human check.**

| Model | Own accuracy | Own errors (copies / distinct items) |
|---|---|---|
| Haiku 5.5 | 0.97 | 6 / 3 |
| GPT-5.4 Mini | 0.96 | 9 / 4 |
| Gemma 4 31B | 0.96 | 9 / 3 |
| Gemma 2 9B | 0.94 | 14 / 7 |
| Llama 3.1 8B | 0.75 | 55 / 26 |
| Mistral 7B | 0.76 | 54 / 27 |

**R4 verdict: not rejected, and mostly uninformative.**
- Rule fixed before the run: R4 fails for a model and wording if the whole 95% interval of (re-ask recovery minus resample recovery) lies above 0.
- It fails for **no** model and wording.
- Only Llama 3.1 8B and Mistral 7B have at least 10 distinct items with an error. For them R4 holds. "Look again" is no better than a fresh try (Llama -0.07 [-0.21, +0.05], Mistral -0.09 [-0.27, +0.08]). The neutral and "review" wordings are clearly worse (Mistral -0.29 and -0.28; Llama -0.21 for neutral).
- For the other four models the items are too easy. They have 3 to 7 items with an error, so no interval can fail. I added the "uninformative" flag **after** seeing these results. It does not change which wording passes or fails; it only stops "holds" from reading as evidence.
- **One result is clear without the flag.** Gemma 2 9B breaks right answers when asked to look again: loss 0.74 against 0.03 for a fresh try (difference +0.71 [+0.59, +0.82]). With "review" the loss is 0.52. This repeats the generated-scenario and Arm A results on a third item set.

What Arm B can and cannot show.
- It shows the weak-model pattern and the Gemma 2 9B collapse again on items written to be readable by people, with a "need more information" answer in a quarter of them.
- It does **not** test the capable-model gain, because those models almost never err here. To test it we would need harder Arm B items, or more of them.
- The items and labels are AI-made. The labelers, drafters and models share training habits.
