# Cross-review 03 → proposal (BENCHMARK_V2, PROTOCOL_v0.2, SCAFFOLD_PROBE, 01_design)

Reviewer: literature (author of `v2_reports/03_literature.md`, which is frozen). I read
`BENCHMARK_V2.md`, `PROTOCOL_v0.2.md`, `SCAFFOLD_PROBE.md`, `v2_reports/01_design.md`, and to
check claims, `v2/annotation/COORDINATOR.md`. No edits elsewhere, no runs. Citation tags are
those of 03: [repo] = authors' repo read; [snippet] = search abstract only.

## Most important first

1. **H-M1 is close to guaranteed and tells the field nothing new; replace it** (§3).
   - Pooled warranted (REVISE-heavy) vs unwarranted (KEEP-heavy) accuracy differing by
     ≥10 pp "for at least one of five models" mostly detects a KEEP or REVISE bias.
   - That trade-off is already published: SycoBench-600 [repo], Ma et al. [repo], Belief-R
     [repo], and BeliefShift's "personalizing models miss drift, grounded models miss legitimate
     updates" [snippet].
   - With n = 5 models, H-M2 ("not predicted by external suites") cannot be confirmed. It is a
     null claim on 5 points.
2. **The positioning statement omits the closest prior work; as written it overclaims.**
   - BENCHMARK_V2 §1 cites only SycoBench-600 and Ma et al. The proposal files never mention
     BeliefShift, Big-Big-SycoBench, ELEPHANT, AssertBench, PersonaMem, PrefEval or SYCON-Bench
     (grep).
   - Each one pre-empts part of a claimed contribution (§1). A reviewer will find them.
3. **The methodology is strong on surface-cue audits but has three gaps** (§2):
   - no contrast-set *consistency* metric;
   - no zero-shot LLM baseline that sees only the follow-up;
   - ambiguity is decided by two raters, which cannot estimate a disagreement distribution.
4. **The scaffold probe is not answered by prior work, but it is cheap and mostly an internal
   check** (§4). Run it for v2's readout decision (greedy vs sampled), not as a finding.

## 1. Novelty and positioning: accurate?

| Proposal claim | Verdict | Prior work that bears on it |
|---|---|---|
| "The estimand is already published (SycoBench-600, Ma et al.)" (§1) | **Accurate** | Both [repo] |
| "Supported/unsupported contrast with matched wording" as a contribution | **Partly pre-empted; reframe** | See detail below the table |
| "Lexical controls that the closest benchmarks lack" | **Accurate for SycoBench-600 and Ma et al.; unknown for Big-Big-SycoBench** | Ma et al.'s conditions are distinct templates (`Are you sure?` vs `Here is a reference note:`) [repo]. SycoBench-600's correct suggestion matches its wrong one in wording and carries no evidence (tex l.130) [repo]. Say "the closest benchmarks *whose prompts we inspected*" |
| Goal-change and preference classes in decision advice | **Not found elsewhere as operationalised here, but must be positioned against three works** | See detail below the table |
| VALIDATION class | **Not new; cite** | ELEPHANT measures validation sycophancy in advice [repo]. Val-Obj has 48 human-written validation vs information-seeking pairs [snippet]. v2's addition is only that validation is placed in contrast sets against the other labels |
| Multi-turn, follow-up delivered alone, decision in a later turn | Design choice, not a contribution | SYCON-Bench [repo]; Kim & Khashabi: follow-up framing raises rebuttal acceptance [snippet] |

**Supported vs unsupported claims.**
- Big-Big-SycoBench separates valid from invalid arguments, with 5,400 human-reviewed arguments
  [snippet].
- AssertBench uses one-word framing minimal pairs [repo].
- Ma et al.'s `user_evidence` holds the evidence string fixed and varies only its attribution
  [repo].
- "Resist, Update, Reject" has models flip iff the *stated* source reliability exceeds the prior
  [snippet].
- v2's FACT_SUPPORTED vs FACT_UNSUPPORTED split is defined by a **source clause** (01 §1.2
  rule 6: admissions office vs neighbour). That is a stated-reliability manipulation, close to
  the last two.
- What is new is the computed HEDGE gold (a conditional answer) and the decision-rule setting,
  not the supported/unsupported contrast itself.

**Goal change vs preference: the three works to position against.**
- **BeliefShift** [snippet] claims to separate "legitimate belief updates" from "drift", with
  2,400 human-annotated trajectories that include product preferences and values. This is the
  nearest claim. Read it in full before writing "first".
- **PersonaMem** [snippet] treats every preference change as legitimate and to be tracked.
- **PrefEval** [repo] treats a stated preference as a constraint to follow.
- **v2's PREFERENCE gold (KEEP when the preference is subordinated) contradicts the
  personalization benchmarks' convention.** That is defensible, because the rule is
  user-stated, but the paper must say so explicitly. Otherwise reviewers from the
  personalization community will call v2's PREFERENCE gold sycophancy-avoidance at the cost of
  user autonomy.

**Is "legitimate goal change vs preference" operationalised anywhere?**
- Not in the form v2 uses: a user-stated rule, a governance clause deciding GOAL vs
  PREFERENCE, and the same string flipping one base and not the other.
- This rests on about 30 searches and snippets. BeliefShift is the open risk.
- 01's own analysis (§0, bottom line) concedes that clear GOAL vs PREFERENCE items are decided
  by an explicit scope clause. The defensible claim is therefore "a benchmark of whether models
  *respect explicitly stated changes of decision criteria* and surface conflicts when the scope
  is unstated", not "models distinguish goal changes from preferences" in general. BENCHMARK_V2
  §1 already disclaims inference of unstated goal changes, which is good. Carry that wording
  into the title and abstract.

## 2. Methodology against the precedents

| Precedent (03 §2) | In the proposal? | Gap or action |
|---|---|---|
| Hypothesis-only and partial-input baselines (Gururangan [snippet]; Poliak [repo]) | **Yes, thorough:** A2–A8, follow-up only and base+follow-up, family-held-out | **Add a zero-shot LLM baseline that sees only the follow-up (A12).** TF-IDF and DeBERTa test surface features. The systems under test are LLMs, which read "that's what we're deciding by now" semantically. If a context-free LLM recovers the *behavior* (not the class) well above best constant, the paired-base design is leaking. A11 checks this by construction, but only on the share of strings that are shared. |
| Contrast sets (Gardner [snippet]) | **Built:** paired bases, shared carriers, ≥20% context swaps | **Missing a consistency score.** Report contrast-set consistency (all members of a set right) and **paired-base consistency** (correct on both α and β of a shared string) beside per-item accuracy. Gardner et al. report the drop to consistency as the headline. Here, the share of models that revise on α *and wrongly* on β is the cleanest decision-sensitivity metric (§3) |
| Counterfactual minimal edits (Kaushik [repo]) | **Yes:** minimal partners listed per string (01 §2, e.g. A7/A8 differ only in the source clause); length ±15% | Log edit distance per partner pair, and audit that the *differing span* is not itself a closed vocabulary. A10 caps reuse at 3, which is good |
| AFLite (Le Bras [snippet]) | Yes, as a separate subset | Fine. Name which model family the filter is fitted with |
| Ambiguity modelling (AmbiEnt [repo]; ChaosNLI [repo]; Pavlick & Kwiatkowski [snippet]) | **Partly.** There is an AMBIGUOUS label, decision-relevant vs decision-invariant cells, author-written readings, and HEDGE gold | Two raters cannot estimate a label distribution, and Pavlick & Kwiatkowski show NLI disagreement persists with more raters. **Collect ≥5 labels on every item either rater or the author flags as possibly ambiguous** (about 20–25% of items, so about 250 × 3 extra labels), and evaluate HEDGE against that distribution. Also require each rater who picks AMBIGUOUS to write both readings, as AmbiEnt does, so the HEDGE branches are human-sourced rather than author-sourced |
| Per-annotator raw labels; perspectivism (Plank, Cabitza [snippet]) | **Yes:** COORDINATOR §5 item 6, plus an adjudicated-excluded sensitivity check | Also release rationales and confidence, and report results under soft labels |
| Agreement and adjudication (Artstein & Poesio [snippet]) | **Yes**, detailed (α, per-category κ, side-taking test, third-rater audit) | **Internal inconsistency:** BENCHMARK_V2 and COORDINATOR use two reviewers plus an adjudicator. 01_design §3.3 uses three annotators per item, keeping items where 2 of 3 agree. Pick one before B1. α ≥ 0.80 on 6 labels including AMBIGUOUS is ambitious given the precedents; pre-state what happens to *items* (not just labels) between 0.67 and 0.80 |
| ≥5 models; external suites | **Yes:** B4 runs ≥5 models plus SycoBench-600 and Ma et al. | Use ≥2 families, and include **anti-sycophancy-tuned vs base pairs** where available (§3) |
| Multi-prompt reporting (Sclar [repo]; Mizrahi [snippet]) | **Missing for v2.** Turn-3 wording is fixed | Run ≥3 paraphrases of the Turn-3 decision request and of the system framing, and report the spread. Otherwise a reviewer will attribute label effects to the one wording |
| Option-ID bias (Zheng [snippet]) | Option-order counterbalancing exists in the probe, not in v2 §4 | Add option-order permutation to v2 elicitation |

## 3. Is H-M1/H-M2 the right question? Sharper alternatives

**H-M1, as written, is weak.**
- Pooled warranted vs unwarranted accuracy confounds discrimination with response bias. A model
  that always keeps scores high on unwarranted and low on warranted, and "passes".
- The literature has already established that such gaps exist.

**H-M2, as written, is untestable.** With n = 5 there is no power to show non-prediction. Make
it descriptive, or use ≥15 models.

Three questions this instrument is uniquely placed to answer:

1. **Decision sensitivity, not message-type sensitivity (best fit to the design).**
   - Prediction: on shared strings that flip α but not β, models revise on *both*, i.e. they
     respond to "a goal or fact message arrived" rather than to whether it changes the decision.
   - Metric: a paired-base d′ (or revise-rate difference flip − no-flip) within GOAL_CHANGE and
     FACT_SUPPORTED, family-level test.
   - This needs paired bases with byte-identical text. No benchmark I found has warranted
     updates that *should not* change the answer, paired with ones that should. SycoBench-600,
     Ma et al. and Big-Big-SycoBench all condition on the answer needing to change.
   - It is response-bias-free and lexical-cue-free by construction.
2. **Does anti-sycophancy suppression also suppress respect for the user's own goals?**
   - Ma et al. show that suppressing sycophancy impairs *factual* rational updating [repo].
   - The open, field-relevant extension: do DPO/SFT anti-sycophancy models also refuse
     legitimate GOAL_CHANGE revisions, i.e. trade sycophancy for user autonomy?
   - Test with base vs anti-sycophancy-tuned pairs. Use Ma et al.'s checkpoints if released (I
     did not check), or public "non-sycophantic" fine-tunes.
   - This is the question most likely to make a main-venue paper. It links to an active
     debate and needs only the goal-change classes to be clean, not all six.
3. **Where errors come from: reading the message vs applying the rule.**
   - The integrated-state controls already allow a three-way split: message reading, rule
     interpretation, arithmetic.
   - Make "share of revision errors explained by misreading the message type" a pre-registered
     secondary analysis. 01's novelty review found no prior decomposition.

**Suggested confirmatory set (Holm over two):**
- (Q1) a paired-base decision-sensitivity effect;
- (Q2) anti-sycophancy-tuned minus base on GOAL_CHANGE-flip revision rate.

Keep H-M1 as descriptive.

## 4. Can the scaffold probe be skipped because prior work answers it?

**No prior work answers the specific question.** Format sensitivity is general:
- 76-point spreads from formatting alone (Sclar [repo+snippet]);
- rankings change with paraphrase (Mizrahi [snippet]);
- option-ID priors (Zheng [snippet]).

The deference-specific evidence is indirect and mixed:
- evaluative framing reduces rebuttal acceptance (Kim & Khashabi [snippet]);
- clear MCQ items flip more readily than ambiguous cases (Kim et al. 2026, a clarity confound)
  [snippet];
- a persona scaffold raises Turn of Flip by up to 63.8% (SYCON-Bench [repo+snippet]).

None tests "options + DECISION line on the pressure turn".

**But its value is internal, not literature-facing:**
- v2 already adopts the unscaffolded format (Turn 2 alone, decision in Turn 3).
- What v2 needs from the probe is:
  - whether the **sampled** readout should be primary (in-repo, temperature-0.7 samples
    switched 12/45 against 0/45 neutral, while greedy never moved);
  - whether the Turn-3 decision request (= S3's decision turn) itself re-suppresses movement.

Stage 1 (S0 vs S3, plus sampling, $2.05 cap) answers both. Prior work cannot answer either for
this model and these items.

**Recommendation:**
- Run stage 1.
- Treat stage 2a's factor decomposition as optional. Its +20–30 pp detectable effect makes a
  null uninformative, and the literature already says formats matter in general.
- Do not frame any probe result as a contribution.
- Add a single Turn-3 paraphrase cell if the budget allows, since §2 needs a multi-prompt spread
  anyway.

## Why I might be wrong

- BeliefShift and Big-Big-SycoBench are known only from abstracts. Either could be much closer
  or much weaker than I assume.
- Whether Ma et al. released tuned checkpoints is unchecked. Q2 may need other public
  anti-sycophancy models.
- Q1 assumes models do over-revise on no-flip warranted messages. If they don't, Q1 is a clean
  null, which is still reportable.
