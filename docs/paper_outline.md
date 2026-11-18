# Paper outline (draft)

Status: draft for the team. All results are exploratory. Numbers come only from the files named in each row.
Short names for files: SL = `docs/second_look.md`, RW = `docs/real_world_check.md`, IT = `docs/instability_thesis.md`,
LIT = `docs/literature.md`, S5 = `results/summaries/realworld_own_error_5models.txt`,
SP = `results/summaries/realworld_own_error_by_pool.txt`, OE = `results/summaries/own_error_reask.txt`.

## 1. Working titles

1. Are You Sure About That?
2. Look Again, Get Worse: When a Second Look Hurts an AI Advisor (overclaims: capable models gain on real questions; use only with "for some models")
3. Please Reconsider (Do Not): Second Looks and Own Mistakes in Chat Models
4. Fix It or Break It: What "Look Again" Does to a Model's Right and Wrong Answers
5. Start a New Chat: Why a Fresh Try Beats a Re-Ask for Weak Models

## 2. Abstract draft

An AI gives advice, and the user says "look again". We ask if the answer then gets better or worse. We test
seven models on generated advice scenarios with a known best answer. We then test five models on 1,200
public questions (MedQA and CommonsenseQA). We compare a re-ask in the same chat with a fresh resample. For
capable models, a planted wrong answer is fixed 98% to 99% of the time in one test. But their own errors
are fixed less often. On real questions, "look again" fixes more of the own errors of Haiku 5.5 and GPT-5.4
Mini than a fresh try does, and it also breaks some right answers. Weaker models (Llama 3.1 8B, Mistral 7B)
do better with a fresh chat. Gemma 2 9B fixes 38% of its errors and breaks 51% of its right answers. We give
a break-even accuracy to say when asking again pays. All results are exploratory, and no human labels exist yet.

## 3. Claims

**Central claim.** A "look again" request does not reliably improve an AI model's own answers, and for some models it breaks more right answers than it fixes.

Secondary claims:

- S1. Asking again is not one effect. The same request helps some models, is harmless for some, and hurts others.
- S2. A planted wrong answer is easy to fix (98% to 99%, capable models). A model's own error is harder. Planted-error tests overstate the benefit.
- S3. For weaker models, a fresh try in a new chat fixes more own errors than a re-ask in the same chat.

(Side result, not a claim: naming an option with no stated wish also moves the answer; see Section 4.4.)

## 4. Sections

### 4.1 Introduction
- Points: a user re-asks; a change is good only for a good reason; we test seven models and two data types.
- Show: Table 1 (the six follow-up types; from README.md "How we test").
- Numbers from: `README.md`.

### 4.2 Related work
- Points: "Are you sure?" lowers accuracy (FlipFlop, Laban et al., arXiv 2311.08596; opened in LIT, abstract in most cases).
  Boundary work (Anatomy of LLM Sycophancy, Huang, arXiv 2610.06522; read methods and results) is the closest competitor.
  Warranted-update work (Big-Big-SycoBench, arXiv 2610.15634; agent read most of it. BeliefTrack, arXiv 2605.30219; read methods and results).
  Self-correction work (Huang et al. 2023, arXiv 2310.01798; Kamoi et al., arXiv 2406.01297; snippet only).
- Show: no figure. Write what is not new (list in LIT, "Already known").
- Numbers from: `docs/literature.md`. Every cite needs a re-read first.

### 4.3 Method
- Points: scenarios with truth by construction and a margin; the six follow-up types; own-error design with resample baseline; recovery, loss, break-even accuracy.
- Show: Table 1 (design, one row per condition) and the formula for break-even = recovery / (recovery + loss).
- Numbers from: SL (Design, Experiment 4 design).

### 4.4 Noise and pressure (setup results)
- Points: order change alone flips 6% to 14% in the 9B models. Nimble flips more near the boundary. Naming an option moves answers.
- Show: Figure 1 (flip rate by margin bin, Nimble and Qwen).
- Numbers from: IT ("First results", "Full generated set").

### 4.5 Second look on generated scenarios
- Points: strong models ignore "look again". Mistral 7B, Llama 3.1 8B and Gemma 2 9B get worse. The nudge hurts six of seven models.
  Planted wrong answers: capable models recover 0.73 to 1.00.
- Show: Table 2 (revise and net change per model, 7 models, decisive scenarios).
- Numbers from: SL ("Results", "Results for the weaker models", "Results of experiments 2 and 3").

### 4.6 The model's own mistakes
- Points: own recovery is far below planted recovery for capable models. Llama 3.1 8B and Mistral 7B recover less than a fresh try. Gemma 2 9B fixes and breaks in proportion.
- Show: Table 3 (resample vs look_again, recovery and loss, 6 models).
- Numbers from: SL (Experiment 4 results) and OE.

### 4.7 Real questions (MedQA and CommonsenseQA)
- Points: the weak-model result held. The capable-model result changed: "look again" beats a fresh try for Haiku 5.5 (+0.11) and GPT-5.4 Mini (+0.15).
  The gain is clear on CommonsenseQA and weaker on MedQA. Costs: GPT-5.4 Mini loss 0.16 versus 0.06 for a resample.
- Show: Table 4 (pooled and by set) and Figure 2 (break-even accuracy against own accuracy, per model).
- Numbers from: S5, SP, RW (Arm A results).

### 4.8 Discussion and practical advice
- Points: use the neutral wording; start a fresh chat for weak models; do not ask a model that is probably right to double-check.
  A re-ask is a net loss when accuracy is above break-even (Gemma 2 9B: break-even 0.42 against own accuracy 0.70).
- Show: Figure 2 again, with the break-even line.
- Numbers from: S5 and RW ("What this changes").

### 4.9 Limits and threats
- Points: see Section 6. Show: Table 5 (threats).
- Numbers from: SL, RW, LIT cautions.

## 5. Figure and table plan (6 items)

| # | Item | Content | Source file |
| --- | --- | --- | --- |
| T1 | Table | Follow-up types and the right behavior | `README.md` |
| F1 | Figure | Flip rate by margin bin, Nimble and Qwen (noise floor line at 6% and 14%) | IT; `results/summaries/instability_procedural_full.txt` |
| T2 | Table | Generated scenarios: revise and net change, 7 models | SL; `results/summaries/second_look_7models.txt` |
| T3 | Table | Own errors: resample vs re-ask recovery, loss, value-add, 6 models | OE |
| T4 | Table | Real questions, pooled and by set | S5, SP |
| F2 | Figure | Break-even accuracy against own accuracy, per model, generated and real | OE, S5 |

## 6. Threats to validity

| Threat | What we did | What is still open |
| --- | --- | --- |
| Templated scenarios; truth comes from our formula | Added real public questions (Arm A) as a check. Result: partly replicated. | No human has checked the generated items. Real sets test facts, not advice trade-offs. |
| Arm B is AI-drafted (60 items) | Labelers do not see the drafters' answers. Option order is shuffled. | Two blind human labels are missing. Arm B is not a result until they exist. R4 is untested. |
| The resample baseline depends on API default sampling | We state the default and name the gateway and date. | At greedy decoding a resample would repeat the first answer, so value-add would grow. |
| CommonsenseQA label noise | We report csqa and medqa apart and do not pool them in the headline. | The capable-model gain is mostly on csqa. A move to another answer can match the gold label by chance. |
| Gemma 4 31B partly missing on real questions | We say so. Its generated-set results are complete. | Only 28 of 1,200 turn-1 calls finished. The real-question table has five models. |
| No human labels yet | Labeling steps and a sheet are ready. | Needs two people, about 2 hours each. |
| Unverified literature | Read depth is kept as in LIT. | Most entries are abstracts or snippets. Re-read each paper before citing. FRAGILE could not be found. |
| Other | Gate: at least 40 own errors per model on real questions (met). Parse failures are reported per model. | Unparsed answers are at most 2.3% of turn-1 calls. One run, one wording per condition. |

## 7. Claims-to-evidence table

| Claim | Evidence file | Strength | Main risk |
| --- | --- | --- | --- |
| Central: "look again" does not reliably help | S5, SP, OE, SL | medium | Capable models gain on real questions; "reliably" must stay narrow |
| S1: effect differs by model | S5, OE | strong | Five or six models only |
| S2: planted error is easier than own error | SL (exp. 3 and 4) | medium | Planted answers are a template; strong models may just solve again |
| S3: fresh try beats re-ask for weak models | S5, SP, OE | strong | Resample baseline depends on API sampling |
| Gemma 2 9B: re-ask is a net loss | S5, OE | strong | One model; the wording may read as a challenge |
| Capable models gain from "look again" on real questions | SP | weak | Mostly csqa label noise; medqa intervals include 0 for Haiku 5.5 |
| Noise floor of 6% to 14% | IT | medium | 9B models only, one run |
| Flips concentrate near the boundary | IT, SL | weak | Holds for Nimble, not Qwen; Anatomy (Huang) is a prior |
| Naming an option moves the answer | IT | weak | 30 scenarios, one sample, wide intervals |

## 8. To-do list

| Task | Owner | Size |
| --- | --- | --- |
| Collect two blind human label sheets for Arm B (60 items) | A | M |
| Compute agreement and compare with drafter proposals | A | S |
| Finish or drop Gemma 4 31B on real questions (rerun with shorter prompts or a smaller sample) | B | M |
| Re-read every cited paper; fix read-depth labels; find BeliefTrack and FRAGILE links | C | L |
| Draw F1 and F2 from the summary files | D | S |
| Test other wordings of "look again" on real questions | B | M |
| Run neutral-mention control on the second-look models | B | M |
| Write Sections 4.3 to 4.7 from the result files | D | L |
| Write Introduction, Discussion and Limits | C | M |
| Add a greedy-decoding check of the resample baseline | B | S |
| Final number check: every number in the paper traced to a summary file | A | M |

## 9. What NOT to claim

- Do not say "AI models get worse when asked to look again". The capable models gain on real questions.
- Do not say the result holds for open advice. Real sets are multiple choice. Arm B has no labels.
- Do not call Arm B a human check before two agreeing human labels exist.
- Do not say a planted-error fix shows a model fixes its own reasoning.
- Do not call the pressure effect sycophancy. Naming the option alone moves answers.
- Do not say instability marks close calls for all models. It holds for Nimble, not Qwen.
- Do not claim the plain re-ask result, or flips near the boundary, as new. Prior work exists (FlipFlop, Anatomy).
- Do not pool MedQA and CommonsenseQA in a headline number.
- Do not cite any paper from LIT as verified. Do not use Gemma 4 31B in the real-question table.
- Do not call any result confirmatory. Keep exploratory and confirmatory results apart (`PROTOCOL.md`).
