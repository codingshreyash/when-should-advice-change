# When should advice change? A negative methods report on measuring warranted revision

**Status:** closing record of the warranted-revision / premise-search research direction
(`research/warranted_revision/`, October 2026). It recommends ending that direction. All
numbers come from the committed records cited in each section; nothing here is new analysis.

**Scope.** This report closes the premise-search work and the goal-autonomy screen. It does
**not** close the original CS 1684 project (the 30 career scenarios, the Claude, Bespoke-Nimble
and Qwen comparisons, and the confirmatory protocol in `PROTOCOL.md`). Several of that
project's questions remain open; see `docs/PROPOSAL_GAP.md` at the repository root.

**Where the cited records are.** Paths under `research/warranted_revision/` and `results/warranted_revision/` refer to branch `research/warranted-revision-v1` of this repository, which holds the full research record and is not merged into `main`.

**What is and isn't complete.**
- Only one model, Qwen3.5-9B, completed the final screen. Mistral-NeMo stopped at its
  preflight gate.
- Human annotation was not completed. Every item and label is AI-made, and the prepared
  23-item human review returned no results.

## Abstract

We set out to measure whether language-model advisors revise a recommendation when, and only
when, a follow-up message warrants it: a new fact, a new constraint, or a change of criteria
by the person who owns the decision. Over four stages the question narrowed. Three stages
ended in empirical negative or null results (1, 2 and 4); stage 3 was a literature audit,
not an experiment.

1. **Method.** Label-free "premise search" added nothing detectable beyond sampling plus
   majority voting. Its verifier checked self-consistency, not premises.
2. **Measurement.** In a 60-item AI-authored benchmark, the distinctions that mattered
   (supported vs unsupported claims, goal changes vs preferences) were defined by their
   wording. Arithmetic plus a hearsay word list reproduced 70% of the gold behaviours, and
   perfect agreement among AI annotators came from shared guidelines, not demonstrated
   validity.
3. **Novelty (literature audit, not an empirical result).** Sensitivity to whether a *fact*
   update changes the decision is already measured by BeliefTrack (Xu et al., EMNLP 2026).
   The two-sided estimand and the anti-sycophancy trade-off on evidence are also published.
   This narrowed the question; it is not evidence about any model.
4. **The remaining question.** Do anti-sycophancy or evidence-filtering instructions suppress
   *legitimate, owner-authorized goal changes*? A pre-registered screen found no such effect
   in the one model that completed it, Qwen3.5-9B:
   - with the goal-aware anti-sycophancy prompt (S), it accepted 12/12 goal changes that
     should flip the answer, in both decision wordings;
   - with the neutral prompt (N), it accepted 12/12 in wording A and **10/12 in wording B**;
   - it never revised when a goal change left the right answer unchanged;
   - S cost nothing relative to N.

   Mistral-NeMo-12B failed the pre-registered response-format gate and was not evaluated.

The screen cost about $0.90 in GPU time. We report it, and the methodological lessons from the
whole project, as a negative result.

## 1. The question and how it narrowed

| stage | question | outcome |
|---|---|---|
| v0 benchmark and premise search | Does searching over readings of a follow-up ("premises") improve warranted revision? | Search ≈ a 4-sample vote; the verifier measures self-consistency (§2) |
| v2 benchmark, AI pre-calibration | Can warranted vs unwarranted follow-ups be labelled reliably and without lexical shortcuts? | Labels are wording-defined; shortcuts reach 70% (§3) |
| novelty audit (literature, no experiment) | Is paired-base consequence sensitivity new? | Not for fact updates: BeliefTrack covers it (§4) |
| goal-autonomy screen | Do anti-sycophancy or evidence-filter prompts suppress legitimate goal changes? | No, in the evaluable model (§5) |

Each stage was frozen before the next began. Earlier data, configs and preregistrations were
kept unchanged; changes were made as new versions or recorded amendments.

## 2. Negative result 1: label-free premise verification reduces to self-consistency

**Sources:** `agent_reports/SYNTHESIS.md`, with corrections from `v2_reports/SYNTHESIS.md`.

**Setup.** Qwen3.5-9B on rule-generated advice scenarios: 3 GPU runs, 7 development cases in
the informative runs.

- **Premise search was no better than voting.**
  - A fixed 4-sample majority vote scored exactly what premise search scored (0.925 on
    smoke-004).
  - Reranking against a plain vote over the same candidates gained 4 turns and lost 1 out of
    96 (sign test p ≈ 0.38).
- **The "verifier" didn't verify.**
  - A wrong reading received the maximum score in 32/40 and 16/16 turns.
  - The model affirmed `SUPPORTED: yes` for 52–70% of wrong readings.
  - The arithmetic check passed invented totals.
- **The benchmark couldn't separate the classes it was built to separate.**
  - A policy reading only a follow-up's opening words scored 280/320 on dev and 200/200 on the
    challenge set.
  - "I'll only X if…" was scored as "if and only if" in 14/40 dev cases.
  - Greedy pressure turns never moved (0/36). Sampled turns did (12/45 vs 0/45 for neutral
    mentions), so the pressure ceiling held only under greedy decoding. That decoding causes
    it is a hypothesis; the scaffold probe that would have separated causes was never run.

**Conclusion.** These are the failure modes Huang et al. (ICLR 2024) predict for label-free
self-verification. The planned pilot was cancelled before launch, and its frozen
configuration is refused by the GPU controller.

## 3. Negative result 2: the distinctions are wording-defined, and AI agreement isn't validation

**Sources:** `v2/ai_precalibration/REPORT.md` (round 1) and `round2/SYNTHESIS.md`;
`audit_r2/SHORTCUT_AUDIT.md`, `audit_r2/SHARED_ERRORS.md`.

**Setup.** A rebuilt benchmark (v2: 60 items, 6 families, 12 base scenarios) had gold
behaviours (keep, revise, hedge) computed from stated rules. Two AI annotators (Claude Opus,
Claude Sonnet), an AI adjudicator and an adversarial AI auditor labelled and audited it.
Packets were blinded, each output was frozen by commit before the next step, and isolation
was checked afterwards.

- **Perfect agreement, little information.**
  - Annotators agreed perfectly in round 1 (κ = 1.00 on 48 items) and again in round 2.
  - A context-blind model that saw only the follow-up, never the scenario, matched the label
    on **60/60** items and the behaviour on 48/60.
- **The labels are wording-defined.**
  - Masking the marked phrases removed most of the signal, and supported/unsupported minimal
    pairs fell from 4/7 to 0/7.
  - A phrase list fitted after reading the items reached 85% in-sample, and fell to chance
    with the phrases masked.
- **Shortcuts with context.** A policy that recomputes the stated rule with any new number
  and hedges on a doubt word got **42/60 (70%)**, against 47% for "always keep". Its failures
  were concentrated in goal changes and ambiguous items, which are marked by governance
  phrases ("agreed", "settled").
- **The hard items were the contested items.**
  - Ten items had a plausible alternative outcome, and on all ten every AI judge agreed with
    the gold.
  - Where reading beyond arithmetic and phrases was needed, the right answer was itself in
    dispute.

**Conclusion.** The benchmark can test whether a model *follows an explicitly stated* change
of standing or goals. It cannot test whether a model *infers* one. A 23-item human-review
packet was prepared and blinded to settle the contested items; no human results were
available for this report.

## 4. Novelty audit: what remained novel was narrow

**Sources:** `agent_reports/01_novelty.md`; `v2/ai_precalibration/novelty_belieftrack/NOVELTY_AUDIT.md`.

**This section is a literature audit, not an empirical result.** No model was run for it. It
narrowed the question that §5 tested; it adds no evidence about model behaviour.

- **The two-sided estimand is published:** resist unsupported pressure while keeping warranted
  updates (SycoBench-600, Belief-R, SycEval).
- **So is the mitigation trade-off:** Ma et al. (Findings EMNLP 2026) show that sycophancy
  suppression impairs updating on *evidence*.
- **BeliefTrack** (Xu et al., EMNLP 2026; code `zjunlp/CBM@6aead1b`) already measures:
  - "Failed Stay": revising on admissible but inconsequential evidence;
  - "Failed Update";
  - pressure isolation.

  Our paired fact items, the same text on two scenarios, are a cleaner domain adaptation of
  that construct, not a new one.

**What BeliefTrack doesn't contain** is a legitimate change of the decision *criteria* by the
person entitled to make it. Its own belief-tracking prompt tells the model to ignore
"preference-oriented" content. That left one question: **do anti-sycophancy or
evidence-filtering instructions suppress legitimate, owner-authorized goal changes?**

## 5. The goal-autonomy screen: a pre-registered null

**Sources:**
- `v2/ai_precalibration/screen_v1/`: `PREREGISTRATION.md`, `MEASUREMENT_CORRECTIONS_1.md`,
  `AMENDMENT_2_OPEN_WEIGHTS.md`, `RESULTS_REPORT.md`;
- `results/warranted_revision/goal-screen-*`.

### Design

**Items.** candidate_v3, AI-authored and audited against its text with 0 medium or high flags.
It contains:
- 12 goal-change pairs. In each, the same owner-stated new criterion flips the answer on one
  base and not on the other.
- 3 fact pairs, 2 weak-claim pairs and 8 neutral controls.
- 30 integrated-state controls: each post-update situation presented fresh, single-turn.

**Protocol.** Three turns:
1. the scenario and the model's first recommendation;
2. the follow-up, answered freely;
3. a decision request in two wordings, plus 3 sampled repeats.

**System prompts:**
- **N:** neutral advisor.
- **S:** goal-aware anti-sycophancy. It resists mere validation pressure while explicitly
  accepting new facts, constraints and criteria changes by the decision's owner.
- **F:** a paraphrase of BeliefTrack's evidence filter, run as a domain-transfer stress test
  only.

**Measurement**, fixed before any output and corrected before any output:
- revision is measured against the model's *own* first answer, and counted only on bases it
  answered correctly;
- S is compared with N on bases correct under both;
- if too few items remain eligible, the outcome is "inconclusive", not "stop".

**Decision rule:**
- **Investigate** if S's autonomy cost is ≥ 15 points in both wordings with ≥ 3 families
  dropping, or if goal no-flip over-revision is ≥ 20 points.
- **Stop** otherwise.

**Subjects.** Claude Sonnet 5.5 was planned but replaced, before any output existed, because
no API key was available (Amendment 2). The subjects became Qwen3.5-9B (`c2022362`) and
Mistral-NeMo-Instruct-2407 (`04d8a905`), on one L40S each, run one after the other.

### Results

**Qwen3.5-9B** passed the real-GPU preflight gate. Its full run made 1,008/1,008 calls with
0 errors; 7/882 answers were unparseable.

| | N | S | F |
|---|---|---|---|
| Correct first answers | 24/24 | 24/24 | 23/24 |
| Goal changes that should flip the answer, accepted (wording A) | 12/12 | 12/12 | 12/12 |
| Goal changes that should flip the answer, accepted (wording B) | 10/12 | 12/12 | 12/12 |
| Fact updates that should flip the answer, accepted | 3/3 | 3/3 | 3/3 |
| Goal changes that shouldn't flip it, answer moved anyway | 0/12 | 0/12 | 0/11 |
| Autonomy cost vs N, A / B | – | 0.00 / −0.17 | 0.00 / −0.17 |

The pre-registered outcome is **stop**, with every criterion evaluable.

- **The only misses** were 2 goal changes under the *neutral* prompt in wording B. In both,
  the model answered the same post-update situation correctly when presented fresh, so these
  were failures to apply the change mid-conversation, not arithmetic errors.
- **Precision.** With 12 items, 12/12 under S rules out an acceptance rate below about 74%
  (exact 95% interval). Large suppression is unlikely; small effects can't be excluded.

**Mistral-NeMo** failed the pre-registered preflight gate:
- 4 of 24 answers (16.7%, against a 10% limit) didn't end in a well-formed RESPONSE line;
- its replies were very short, about 18 tokens per call;
- its full run was not started.

This is a format-compliance failure under the frozen protocol, not evidence about goal
autonomy. The parser and prompts were not changed afterwards; doing so would have been
scoring tuned on observed output.

### Interpretation

The observed result is that one 9B instruction-following model applied clearly authorized
goal changes, and that an instruction against sycophancy which explicitly licenses such
changes did no measurable harm. The screen measured whether a model *honours* a clearly
authorized change, not whether it *infers* one.

**Why it sat at ceiling is a hypothesis, not a finding.** The screen did not vary any of these
factors, so none of the following is demonstrated:
- every goal change stated who decides and gave a complete new criterion, which may make the
  task easy for any capable instruction follower;
- the S prompt explicitly licensed owner-authorized changes, which may have pre-empted
  suppression;
- the items may be easy for this model family in particular.

The result says nothing about:
- implicit or ambiguous goal changes;
- training-based anti-sycophancy methods;
- larger models;
- human-validated items.

## 6. Methodological lessons

1. **Agreement among AI annotators from one provider is not validation.** A context-blind
   baseline that reproduces the labels shows where agreement comes from. Masked-text audits
   show whether a contrast is defined by its wording.
2. **Explicit-rule items invite shortcuts, and may produce ceilings.** Making gold computable
   makes it checkable, but in round 2 it also made the task solvable by arithmetic plus
   phrase-spotting (70%, measured). Paired bases (the same text with different consequences)
   defeat follow-up-only shortcuts, but not arithmetic. That explicit items also caused the
   screen's ceiling is plausible but untested.
3. **Measure revision against the model's own first answer.** Our first analysis scored
   movement against the computed base answer. That would have counted a model holding a
   wrong first answer as "over-revising". The correction was made before any output existed.
4. **Separate "inconclusive" from "null".** An eligibility gate stops a screen with too few
   usable items from being reported as a negative result.
5. **Don't select items using annotators who are also the tested models.** Our exclusion rule
   was text-based only, so the primary set wasn't tuned toward Claude subjects.
6. **Treat response format as a validity gate, not a nuisance.** Strict final-line parsing
   failed for one of the two small models here, and earlier for Qwen (smoke-003, 68% valid
   decisions).
7. **Deployment failures are research risks.** Each of these was caught before any model
   output was affected:
   - a launch bundle that omitted the item files, which cost $0.14 and is now tested end to
     end;
   - a shell timeout of 0 that would have meant "no limit";
   - a tokenizer that transformers warned would mis-tokenize unless loaded with a fix;
   - a cost cap computed from an unverified price, now checked against the provider's live
     listing before each launch.

   Hash-locking the frozen inputs, and refusing to launch on any mismatch, kept the scientific
   inputs fixed through all of these fixes.

## 7. Limitations

- **Items and labels.** All were produced by AI models. None has been validated by a human;
  the human review was prepared but not completed.
- **The goal-autonomy screen.** Only one model, Qwen3.5-9B, completed it. Its 12 goal-change
  pairs give coarse precision, and the fact comparison rests on 3 items.
- **Mistral-NeMo.** It stopped at the preflight gate and contributed no data on the question.
- **Causes of the ceiling.** These were not tested (§5, Interpretation).
- **Novelty claims.** The comparison with prior work rests on independent AI literature
  audits; BeliefTrack's full text was verified by the PI.

## 8. Recommendation

**End this research direction.**
- Premise search: no gain over voting.
- The benchmark: wording-defined.
- Fact-update sensitivity: already measured by BeliefTrack.
- The one remaining question: a null in the one model that completed the screen.

Searching for prompts, items or parsers under which an effect appears would be
outcome-driven. A future study would need a different, separately justified question, for
example implicit goal changes or training-based interventions, with human-validated items and
its own preregistration.

## 9. Cost

| item | cost |
|---|---|
| Earlier Brev GPU runs (8, Oct 25; estimates) | ≈ $3.32 |
| Goal screen: Qwen, failed launch (bundling bug) | ≈ $0.14 |
| Goal screen: Qwen, completed run | ≈ $0.58 |
| Goal screen: Mistral-NeMo, preflight only | ≈ $0.18 |
| **Recorded total** | **≈ $4.22** |

Earlier exploratory API runs on another key, and earlier open-model runs, have no recorded
cost (see `results/warranted_revision/PROJECT_LEDGER.md`). All GPU instances were deleted,
with deletion confirmed.

## 10. Record

| artifact | location |
|---|---|
| First review and corrections | `agent_reports/SYNTHESIS.md`, `v2_reports/SYNTHESIS.md` |
| Pre-calibration, rounds 1–2 | `v2/ai_precalibration/REPORT.md`, `round2/SYNTHESIS.md`, `round2/PUBLICATION_CHECKPOINT.md` |
| Shortcut and shared-error audits | `v2/ai_precalibration/audit_r2/` |
| Novelty audit | `v2/ai_precalibration/novelty_belieftrack/NOVELTY_AUDIT.md` |
| Screen design, corrections and amendment | `v2/ai_precalibration/screen_v1/` |
| Screen results | `v2/ai_precalibration/screen_v1/RESULTS_REPORT.md`; `results/warranted_revision/goal-screen-qwen35-9b-v1/`, `goal-screen-mistral-nemo-v1/` |
| GPU runs | [Qwen, run 40412442979](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40412442979); [Mistral-NeMo, run 40416847278](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40416847278) (raw outputs in artifacts, kept 90 days) |
| Cost ledger | `results/warranted_revision/PROJECT_LEDGER.md` |
