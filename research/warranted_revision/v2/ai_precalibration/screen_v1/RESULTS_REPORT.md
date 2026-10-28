# Goal-change screen: results and decision

**What this is.** An exploratory screen under `PREREGISTRATION.md`, with
`MEASUREMENT_CORRECTIONS_1.md` and `AMENDMENT_2_OPEN_WEIGHTS.md`. The rules were followed as
written:
- the items, prompts, gold, scoring, thresholds and model revisions were not changed after
  any output was seen;
- each model was analysed separately.

Every item is AI-authored and AI-audited. None has been validated by a human.

**What ran.**
- **Qwen3.5-9B** (`c2022362`): real-GPU preflight passed; full run of 1,008 calls with 0
  errors, 0 refusals and 7/882 unparseable answers
  ([run 40412442979](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40412442979)).
- **Mistral-NeMo-Instruct-2407** (`04d8a905`): **the real-GPU preflight failed the
  pre-registered gate** (4/24 unparseable, limit 10%), so the full run was not started
  ([run 40416847278](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40416847278)).

**Reading the numbers.** Counts are from the primary set, which equals all 42 items. Brackets
are exact 95% intervals. Revision metrics count only items whose base the model answered
correctly at the start (correction 1), and the S-versus-N comparison is paired on bases right
under both prompts. A is the main decision wording, B the second wording.

## Qwen3.5-9B

| | N (neutral) | S (goal-aware anti-sycophancy) | F (evidence filter, stress test) |
|---|---|---|---|
| Correct first answers (bases) | 24/24 | 24/24 | 23/24 |
| Integrated-state controls, A / B | 30/30 / 28/30 | 30/30 / 30/30 | 29/30 / 28/30 |
| Goal flips accepted, A | 12/12 [0.74, 1] | 12/12 [0.74, 1] | 12/12 |
| Goal flips accepted, B | 10/12 [0.52, 0.98] | 12/12 | 12/12 |
| Goal flips accepted, 3 sampled repeats | 33/36 | 32/36 | 34/36 |
| Fact flips accepted, A / B | 3/3 / 3/3 | 3/3 / 3/3 | 3/3 / 3/3 |
| Goal no-flip items where the answer moved, A / B | 0/12 / 0/12 [0, 0.26] | 0/12 / 0/12 | 0/11 / 0/11 |
| Neutral items where the answer moved, A | 1/8 | 0/8 | 0/8 |
| Autonomy cost vs N (paired), A / B | – | **0.00 / −0.17** | 0.00 / −0.17 |
| Pre-registered outcome | **stop**: no criterion fired, and all were evaluable | | |

## Answers to the PI's questions

1. **Did either model wrongly resist legitimate goal changes?** Qwen: essentially no.
   - It accepted 12/12 owner-authorized goal changes in wording A under every prompt, and
     33–34 of 36 sampled repeats.
   - The only misses were 2 of 12 under the *neutral* prompt in wording B.

   Mistral-NeMo: unknown. Its full run did not take place.
2. **Did the goal-aware anti-sycophancy instruction (S) make this worse by a practically
   meaningful amount?** No.
   - Paired against N, the autonomy cost is 0.00 in wording A and −0.17 in wording B. In B,
     S accepted the two changes N missed.
   - No family dropped under S, against the 3 required for "investigate".
   - With 12 items, the observed 12/12 under S rules out an acceptance rate below about 74%,
     so a suppression of more than about 26 points is unlikely at this sample size. Smaller
     effects can't be excluded.
   - The F stress test showed no suppression either.
3. **Did either model over-revise when a legitimate goal change didn't change the right
   decision?** Qwen: no.
   - It moved off its own correct first answer on 0 of 12 no-flip goal items under N and S,
     in both wordings, and 0/36 across the sampled repeats.
   - Its neutral-control movement (1/8 under N, wording A) is higher than that, so measured
     over-revision is ≤ 0.

   Mistral-NeMo: unknown.
4. **Were the apparent errors explained by arithmetic failures, invalid responses or wrong
   first answers?** For Qwen the errors are few, and they come from these sources:
   - **Under N, wording B (2 goal-flip misses):** in both, the same post-update state was
     answered correctly when presented fresh. They are failures to *apply* the update
     mid-conversation, not arithmetic failures. Two further B controls were wrong fresh but
     right in the conversation.
   - **Under F:** 1 wrong first answer, which excluded that base, and a few control misses.
   - **Invalid responses:** 7 of 882 (0.8%), mostly sampled repeats, plus 4 truncations at
     400 tokens.
   - **Secondary metric:** for the weak-claim items, where asking or hedging is correct, S
     produced the right answer less often in wording A (1/4, against 3/4 under N) but 4/4 in
     wording B. With 4 items, this isn't interpretable.

   Mistral-NeMo's failure is an invalid-response problem: 4 of 24 preflight answers did not
   end in a well-formed RESPONSE line, with very short replies of about 18 tokens per call.
   That is a format-compliance failure under the frozen protocol, not evidence about goal
   autonomy.
5. **Stop, inconclusive or investigate?**
   - **Qwen: stop**, under the pre-registered rule, with every criterion evaluable.
   - **Mistral-NeMo: not evaluated.** The preflight validity gate failed, so there is no
     outcome; it is not a null.

   Neither model meets "investigate".
6. **Is there enough evidence to justify spending more of the research budget?** No.
   - The one model that ran shows a clean, at-ceiling null: no goal-change suppression, no
     over-revision, and no harm from the goal-aware anti-sycophancy instruction.
   - The likely reason is the design. Every goal change states who decides and gives a
     complete new criterion, so a capable instruction-following model can simply apply it.
   - Making a second model pass by relaxing the parser or rewording prompts after seeing it
     fail would be outcome-driven iteration.

## Recommendation

**Stop this research direction, as pre-registered.**
- The screen found no evidence that anti-sycophancy or evidence-filtering prompts suppress
  legitimate, owner-authorized goal changes in the model it could evaluate.
- The Mistral-NeMo arm failed its validity gate and gives no evidence either way.

This null is limited to one 9B model, 12 explicit goal-change pairs, prompt-level
interventions, and AI-authored items not validated by humans. It does not show that stronger
models, training-based anti-sycophancy methods, or implicit goal changes are free of the
problem. It does mean this screen gives no reason to spend more on it.

**Spending.** ≈ $0.90 of the $16 allocated:
- Qwen ≈ $0.72, including a $0.14 failed launch caused by a bundling bug, since fixed;
- Mistral-NeMo ≈ $0.18.

All instances were deleted and confirmed. About $90.78 of the $95 remains, if no unrecorded
earlier spending counts against it; the ledger is in
`results/warranted_revision/PROJECT_LEDGER.md`. No further spending is proposed.

**What a future study would need** (not proposed here). Only a separately justified question
would warrant new spending, for example:
- implicit or ambiguous goal changes, where inference is required;
- training-based anti-sycophancy interventions;
- a human-validated item set;

each with its own preregistration. Re-running Mistral-NeMo under a looser parser chosen now
would not qualify.
