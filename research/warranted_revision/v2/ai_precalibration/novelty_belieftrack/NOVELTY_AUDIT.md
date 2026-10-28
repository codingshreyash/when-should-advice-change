# Novelty audit: paired-base consequence sensitivity vs BeliefTrack (Xu et al. 2026)

Auditor: an independent AI literature audit (Claude). No model runs, no paid API, no GPU, no
commits. **This comparison is provisional**, because the paper's full text could not be read
(see the access table). It rests on the released code plus the abstract and search snippets.

## Verdict

**(B), leaning towards (C) for the core construct.** BeliefTrack does not contain our exact
manipulation: the same update text placed on two bases, where it flips the decision on one and
not the other. But the *question* that manipulation is meant to answer is already
operationalised there, in a formally verified domain: does revision track the update's
consequence for the current state, or merely the arrival of new input?

- **Failed Stay** is true, admissible new evidence that leaves the verified belief state
  unchanged. Failure means revising anyway. That is our "warranted-but-inconsequential
  over-revision" and our "irrelevant-change revision" [code/data inspected].
- **Failed Update** is a state-changing input that the model fails to integrate. That is our
  under-revision, although its trigger is an explicit correction or retraction [code/data inspected].
- **Failed Isolation** adds social-pressure noise (authority, flattery, urgency) to the same
  evidence, with a no-noise (`none`) control [code/data inspected].
- A capability filter scores a stay/update case only if the model was right on the preceding
  turns. That plays the role of our integrated-state control [code/data inspected].

For the FACT_SUPPORTED pairs, our Q1 is therefore a **domain adaptation** of Failed Stay vs
Failed Update to rule-stated advice. It adds one design refinement: text held byte-identical
across bases, where BeliefTrack uses different observations in its stay and update cases. That
is a cleaner causal contrast, not a new construct.

**Not covered by BeliefTrack (evidence below):**

1. **User or owner goal and criterion changes.** BeliefTrack's hypothesis space and
   consistency criterion are fixed, and nobody can legitimately change what counts.
2. **The evidential standing of the same claimed value.** In BeliefTrack, host evidence is
   authoritative by construction, and noise is never a factual claim about a specific
   quantity.
3. **"Ask/hedge" as a correct action.** Their set-valued belief state represents uncertainty,
   but no clarifying or hedging action is ever gold.
4. **A user-owned decision with prior committed advice.**
5. **The autonomy cost of an evidence-filtering intervention.** Their own "belief-tracking"
   system prompt (`PROMPT_ENHANCEMENT_TEXT`) tells the model to exclude "preference-oriented
   or biased expressions" and "suggestive or advisory content" as non-evidence. That is
   harmless where no legitimate preference change exists. In advice, it would by design
   suppress owner goal changes, and this is untested in BeliefTrack.

**Minimal distinctive measurement that remains:**

- GOAL-change pairs: the same owner-stated criterion change on a flip and a no-flip base;
- crossed with an evidence-filtering intervention, either BeliefTrack's own enhancement prompt
  or our anti-sycophancy sentence.

This is the checkpoint's Q2 (autonomy cost) plus the GOAL half of Q1. The FACT half of Q1 is
not distinctive.

**Recommendation:**

- **Stop** Q1 as a standalone contribution. Do not frame the paper as "consequence
  sensitivity". If any subject run happens, cite BeliefTrack as the formal-domain precedent.
- **Pivot** to the autonomy-cost question (Q2), via a **small screen**:
  - ~12–24 GOAL pairs plus existing FS pairs;
  - neutral vs anti-sycophancy prompt vs BeliefTrack-style evidence-filter prompt;
  - greedy decoding, open 7–9B models first.
- Go further only if the filter or anti-sycophancy prompt lowers GOAL-flip revision by ≥15 pp
  more than FS-flip revision.

The checkpoint already found GOAL items largely solvable by extracting the stated criterion.
So a null is the likely outcome, and a null should end the study.

**Confidence:** moderate (about 0.65) on (B)/(C) for FACT-type Q1, and moderate on the "not
covered" list. It would change if any of the following were found:

- The full text contains a natural-language or real-world transfer section, or a
  matched-observation analysis. That would move Q1 to a clear (C).
- The HF dataset contains preference or goal-change turns, or hedge or ask golds. That would
  narrow Q2.
- Conversely, the paper reports that its belief-tracking prompt *helps* uniformly. That would
  make the Q2 autonomy-cost test sharper, since no test of over-suppression exists there.

**To complete this audit,** the lead should upload the paper PDF (arXiv 2605.30219 or ACL
Anthology 2026.emnlp-main.336) and, if possible, one file from each split of the HF dataset
`zjunlp/BeliefTrackDataset` (`Task_A/9B/test/{failed_stay,failed_update,failed_isolation}`).

## Access table

| # | resource | method | result |
|---|---|---|---|
| 1 | https://aclanthology.org/2026.emnlp-main.336/ | WebFetch | **failed**: DNS `ENOTFOUND aclanthology.org` |
| 2 | https://aclanthology.org/2026.emnlp-main.336.pdf | WebFetch; curl via proxy | **failed**: DNS; proxy `CONNECT 403` |
| 3 | WebSearch for the paper / arXiv | WebSearch (3 queries) | **ok**: snippets identify arXiv 2605.30219 (Haoming Xu + 8 co-authors, posted 28 May 2026), abstract-level claims |
| 4 | https://arxiv.org/abs/2605.30219, /pdf/, /html/2605.30219v1, export.arxiv.org | WebFetch; curl | **failed**: DNS; proxy `CONNECT 403` |
| 5 | Mirrors: alphaxiv, chatpaper, themoonlight, 163.com, benchmarklist, opentrain, sotaverified, mind-verse | WebFetch; curl | **all failed**: DNS / proxy 403 |
| 6 | Code: https://github.com/zjunlp/CBM (found via search and the README) | `git clone --depth 1` into the scratchpad `belieftrack/` | **ok**: commit `6aead1b5dfee7058ec0048062a503d589d04dcd4` (30 May 2026), 122 files; code read, nothing executed |
| 7 | Data: HF dataset `zjunlp/BeliefTrackDataset` (named in the README) | `git clone` of the HF dataset repo; HF API | **failed**: proxy `CONNECT 403` for huggingface.co. The `data/` folder is not in the GitHub repo. No GitHub mirror found (`gh search` is blocked in this session) |

**Not read:**

- the paper full text (any version);
- the EMNLP 2026 Anthology page. The EMNLP Main acceptance and the ID 2026.emnlp-main.336 are
  therefore **[not verified]**: the repo README cites only the arXiv preprint;
- the released test/train cases;
- per-model result tables.

The 70.9% (RL) and 46.1% (steering) failure reductions, and "Failed Isolation up to 95.4%", come
from search snippets only **[abstract/snippet]**.

Tags used below: **[full text]** none available; **[abstract/snippet]**; **[code/data
inspected]** = code read in the clone (data not available); **[not verified]**.

## What BeliefTrack is (from what could be read)

- **Setting** [abstract/snippet; code/data inspected]: closed-world multi-turn hypothesis
  tracking, with two task families.
  - **Task A, Rule Discovery** (`task_a/core/rules.py`): integer triples and hidden rules such
    as `sum_divisible_by_3`. The host gives a triple and a YES/NO result, and by default also
    each candidate rule's prediction for it (`task_a/core/agent.py`,
    `include_rule_predictions`).
  - **Task B, Circuit Diagnosis** (`task_b/domain/faults.py`): 9 single faults; measurement
    results YES/NO with per-fault predictions.
- **Model output:** a set of still-consistent hypotheses in `<hypothesis>` tags. **Gold** is
  the survivor set computed symbolically (`compute_surviving_set`). The "formal verification"
  is exact set computation over a finite hypothesis space [code/data inspected].
- **Failed Stay** (`generate_failed_stay_sequence` and the `belief_stats_failed_stay_*`
  variants):
  - Turn structure: a prefix converges to the oracle singleton, then further *true* evidence
    arrives that is locally ambiguous (consistent with the oracle plus others) but cannot
    change the cumulative survivor set. The variants add "post-convergence interference"
    rounds.
  - Scoring (`_classify_repeat_trajectory`): the case counts only if turn 0 is correct. It is a
    failure if the model later reintroduces eliminated hypotheses or leaves the singleton
    [code/data inspected].
- **Failed Update** (`generate_failed_update_sequence_v2`):
  - Turn structure: a prefix, then a **misrecorded** result that eliminates the oracle, then an
    explicit host **retraction/correction**. The model must restore the oracle.
  - Scoring: only if the pre-correction turn was matched; a failure if the post-correction turn
    is wrong.
  - The `failed_update_depth` pipeline delays the correction with K "oracle-neutral" triples
    [code/data inspected].
- **Failed Isolation** (`sample_authority_failed_isolation.py`,
  `analysis/depth_and_noise/augment/cd_noise_typology.py`):
  - The evidence turns carry a host comment pushing a wrong hypothesis. Noise types are
    `authority` ("I am certain the rule is `{wrong_rule}`"), `sycophancy` (flattery for a
    wrong hint) and `stress` (urgency), plus a `none` type that strips the comment from the
    same evidence.
  - Scoring is the final turn only [code/data inspected].
- **Interventions** [abstract/snippet; code/data inspected]:
  - a belief-tracking prompt (`PROMPT_ENHANCEMENT_TEXT` in the eval scripts: valid-evidence
    definition, exclusion of non-evidential content, correction and restoration rules);
  - GRPO RL with a Jaccard or exact-match belief-state reward (`task_*/training/reward.py`);
  - activation steering (EasySteer);
  - post-answer probing.
- **Models in code** [code/data inspected]: Qwen2.5-7B-Instruct, Qwen3.5-9B,
  Qwen3-30B-A3B-Instruct-2507, and `deepseek-v3.2` via an API backend. Frontier closed models
  are possibly in the paper [not verified].
- **Decoding:** 7B at T=0.3; 9B at T=1.0 with thinking; 3 repeats; a case fails if any repeat
  fails [code/data inspected]. No prompt-format or wording-variation study was found in the
  code [code/data inspected; paper not verified].

## Our design (as read)

The source files are `round2/SYNTHESIS.md`, `round2/PUBLICATION_CHECKPOINT.md`,
`BENCHMARK_V2.md`, `PROTOCOL_v0.2.md`, `GUIDELINES_v0.2.md` and `candidate_v2/items.json`.

- 60 items, 6 families, 12 bases.
- Labels: FACT_SUPPORTED 12, GOAL_CHANGE 12, FACT_UNSUPPORTED 11, AMBIGUOUS 9, PREFERENCE 8,
  VALIDATION 8.
- Each base states an explicit iff rule as code. Gold is computed from facts, rule and
  readings.
- 10 follow-up strings are reused byte-identically on paired bases. Example: `eld-01`/`eld-02`
  both receive "Brightside emailed us a revised quote this morning… $4,300 a month". On eld-a
  that flips the decision (4,700 vs 4,300), and on eld-b it does not (4,700 > 4,300 still). The
  hearsay version (`eld-03`/`eld-04`) crosses evidential standing on the same bases. The GOAL
  pair `eld-05`/`eld-06` ("cost no longer decides it… within 15 minutes") is the same string on
  both bases.
- Planned controls: integrated-state (fresh-context) controls, neutral "thanks" controls,
  two Turn-3 wordings, greedy plus samples.
- No model has been run as a subject.

## Dimension-by-dimension comparison

| dimension | BeliefTrack | our paired-base design | overlap |
|---|---|---|---|
| Experimental unit | Multi-turn trajectory of symbolic observations; per-turn hypothesis set [code] | 3-turn advice conversation: base with a stated rule → recommendation → one follow-up → decision | Different surface; same abstract unit (state, then new input, then a re-decision) |
| State representation and verification | Finite hypothesis space; exact survivor-set computation; called "symbolic verifiers" [abstract/snippet; code] | Rules as code (`rule.expr`) over stated facts; gold computed by `v2bench`; "readings" encode interpretation | Same idea: a computable gold state. Ours adds an interpretive layer (readings, labels) that is AI-adjudicated, not verified |
| Warranted update | Host correction of a misrecorded result (Failed Update) [code] | Supported fact change, or explicit owner goal or criterion change, that flips the rule's output | Partial: theirs is retraction-only; no new-fact flip and no goal change |
| Warranted stay | True new evidence that leaves survivors unchanged (Failed Stay); oracle-neutral delay triples [code] | Supported change under the threshold; supported change to a quantity outside the rule; GOAL picking the current option; pressure (VAL/PREF) | **Strong overlap for the FACT cases**: Failed Stay is warranted-but-inconsequential input |
| **Same update text in should-change vs should-not-change contexts** | **Not found.** Stay and update cases are generated by separate samplers with different observations, and the update mechanism (retraction) differs from the stay mechanism (new true triple). No paired, matched or counterfactual construct exists in the code (grep for pair/counterfactual/matched: only circuit "paired branch faults") [code]. The released cases could not be inspected | Core manipulation: 10 byte-identical strings on flip and no-flip bases | **Our only design-level difference.** It is a refinement of their stay/update contrast, not a new construct |
| Evidential standing (supported vs unsupported) | Host evidence is authoritative by construction. Unsupported content appears only as noise asserting a wrong *hypothesis*, never as a hedged claim about a specific value [code] | Same value, crossed as documented vs hearsay (eld-01..04, cc-01..04, eb-01..04) | Not covered (ours) |
| User goal or preference change | None. The criterion (consistency with evidence) is fixed. Their prompt classes "preference-oriented" content as non-evidence [code] | GOAL_CHANGE (12) and PREFERENCE (8) items | Not covered (ours) |
| Social pressure | Failed Isolation: authority, sycophancy (flattery), stress templates; host-originated [code] | VALIDATION and PREFERENCE pressure items (KEEP gold); user-originated | Covered in kind by them. Ours is a domain adaptation |
| Ambiguity or hedging as a correct response | The belief state is a set, so uncertainty is represented as multiple survivors. No ask or hedge action is gold [code] | HEDGE gold on 25% of items; `RESPONSE: ask` | Not covered as an *action*. Note that the checkpoint found the AMB golds contested |
| Controls | Prefix-capability filter (`insufficient_capability` unless earlier turns are correct) ≈ our integrated-state precondition; `none` noise type = the same evidence without the host comment ≈ a neutral control [code] | Integrated-state fresh-context controls; neutral "thanks" follow-ups (planned) | Largely equivalent; ours uses a fresh-context control rather than prefix correctness |
| Decoding and format sensitivity | Fixed temperatures (0.3 / 1.0), 3 repeats, any-failure aggregation; no wording or format variation found [code] | 2 Turn-3 wordings × option order; greedy plus 5 samples | Ours is more format-robust (planned only) |
| Models | Qwen2.5-7B, Qwen3.5-9B, Qwen3-30B-A3B, DeepSeek-V3.2 in code; "multiple LLMs" in the abstract [code; abstract/snippet] | Planned: Llama-3.1-8B, Qwen3-8B, 2 API models | — |
| Methods evaluated | Belief-tracking prompt ("limited gains"); RL with belief-state reward (−70.9%); steering (−46.1%) [abstract/snippet; code] | Neutral vs anti-sycophancy system prompt (planned) | Their prompt is functionally an evidence-filter / anti-sycophancy prompt. Its effect on *legitimate preference or goal changes* is untested because their domain has none |
| Failure taxonomy | Failed Stay / Failed Update / Failed Isolation | No-flip over-revision / flip under-revision / irrelevant-change revision, plus pressure capitulation | See the mapping below |

### Mapping of failure classes

| ours | BeliefTrack | fit |
|---|---|---|
| No-flip over-revision (warranted update, no consequence) | Failed Stay | Direct, for FACT_SUPPORTED. Not for GOAL no-flip (no analogue) |
| Irrelevant-change revision (supported change to a quantity outside the rule: hp-01, sol-09) | Failed Stay (new true evidence that cannot eliminate) | Direct |
| Flip under-revision | Failed Update | Partial: theirs is triggered by an explicit correction, ours by a new fact or a goal change |
| Capitulation to VAL/PREF pressure | Failed Isolation | Direct in kind; different speaker role (host vs decision owner) |
| Wrongly suppressing a legitimate goal change (autonomy cost) | none | **Not covered** |

## Why the byte-identical pairing does not by itself rescue Q1

- BeliefTrack's stay/update contrast already separates the update's consequence from its
  arrival. Every Failed Stay case delivers a genuine new observation, and the gold says
  nothing changes.
- In their domain, holding text fixed is unnecessary: an observation is a triple with no
  wording cues. In ours, the pairing *is* needed, because wording cues exist. But the
  checkpoint's own shortcut audit shows that the FACT pairs are solved by "arithmetic plus a
  doubt word" (SYNTHESIS §4).
- A finding of "models over-revise on the no-flip base" for FACT pairs would therefore read as
  Failed Stay in natural language. That would be a replication or transfer of their result,
  not a new failure mode.
- Interest would come only from a dissociation, for example a model with low Failed Stay
  that over-revises on our no-flip bases. We cannot test that without their data
  (unavailable here) or running their eval.

## Recommendation

1. **Stop** pursuing paired-base FACT consequence sensitivity as the differentiating
   contribution. Add BeliefTrack to the prior-work table, where the checkpoint missed it: it
   is closer than Belief-R or GSM-IC.
2. **If anything continues, run a small screen of the autonomy-cost question:**
   - **Items:** about 12 new GOAL pairs (owner-stated criterion change, byte-identical on flip
     and no-flip bases, with varied governance wording), plus the 3 existing FS pairs as the
     comparison class, plus neutral controls.
   - **Prompts:** neutral vs our anti-sycophancy sentence vs BeliefTrack's
     `PROMPT_ENHANCEMENT_TEXT` (adapted).
   - **Models:** greedy decoding, 1–2 open 7–9B models first. That needs a GPU and the user's
     approval; none was used here.
   - **Continue only if** GOAL-flip REVISE drops ≥15 pp more than FS-flip REVISE under a
     filter prompt. Otherwise, stop and write the pre-calibration up as a methods note.
3. **Before any run,** obtain the PDF and the dataset, to confirm that BeliefTrack has no
   goal or preference-change condition and no matched-observation analysis.
