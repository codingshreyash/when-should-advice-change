# Shortcut audit of candidate_v2: round 2, phase 1 (adversarial auditor)

**What this is.** An AI-only pre-calibration audit. It is not human validation.

- **Scope:** 60 items in 6 dev families (12 bases), from `candidate_v2/items.json`.
- **Gold:** the behaviours v2bench computes from the author's design labels: KEEP 28, REVISE 17,
  HEDGE 15.
- **What I did not read:** AUTHOR_NOTES.md, audit_run*.json, anything under `round2/`, and
  `data/v0/holdout_*`.
- **Sample size:** at n = 60 every number is indicative.

**Baselines:**

| | value |
|---|---|
| label chance | 16.7% |
| label majority | 20.0% |
| behaviour chance | 33.3% |
| best constant (always KEEP) | **46.7%** (28/60) |

p-values are one-sided binomial tests against the best constant.

## The three most important findings

### 1. On 43 of the 60 items, arithmetic plus a hearsay word list gets the gold behaviour

The policy is a blind one: it knows the base rule and does simple arithmetic, but doesn't read
standing.

1. Recompute the rule with every new number. Each number is mapped to a base fact by context
   words in the narrative (`kw`).
2. If the answer flips, give HEDGE when a hearsay or doubt word appears, otherwise REVISE.
3. Everything else is KEEP.

**Results.** The policy gets **42/60 = 70.0%** (p = 0.0002). With perfect fact extraction it
gets **43/60 = 71.7%**, which is the ceiling for any policy that reads only arithmetic and
standing phrases.

| label | right |
|---|---|
| FACT_SUPPORTED | 12/12 |
| PREFERENCE | 8/8 |
| VALIDATION | 8/8 |
| FACT_UNSUPPORTED | 8/11 (10/11 with perfect extraction) |
| GOAL_CHANGE | 3/12 |
| AMBIGUOUS | 3/9 |

**Which word lists.** The hearsay list is the round-1 auditor's, written before any v1 item was
read and never shown v2 items. With my own pre-registered list
(`scripts/lexicon_untuned_r2.py`, frozen 2026-10-26T15:32:37Z, before `items.json` was opened)
the policy gets 39/60 = 65.0% (p = 0.003). My list lacks "told" and "says".

**Its 17 errors under perfect extraction:**

- **10 goal changes that flip:** eld-06, eld-09, hp-05, hp-06, cc-07, sc-01, sc-10, sol-03,
  sol-06, eb-06.
- **6 decision-relevant ambiguous items:** eld-08, hp-08, cc-06, sc-03, sol-01, eb-05.
- **cc-03:** "A mom at the park **told me**", which has no listed hearsay word.

**Standing versus governance:**

- **Evidential standing (FS/FU) is fully solved.** It reduces to arithmetic plus a source or
  hedge phrase, as the guideline defines it ("how the message presents its source").
- **Only the governance axis needs anything more.** These are the 17 items where a new
  criterion governs or might govern: 10 GOAL-flip and 7 AMB-conflict.
- **That axis is phrase-marked too, at least in-sample.** A 6-line tuned lexicon written after
  reading the items, added to the same policy, reaches **51/60 = 85%** (GOAL 10/12, AMB 7/9).
  With `marker_span` masked it drops to 17%.

  | phrase | where it appears |
  |---|---|
  | "agreed / settled / made up our minds" | 11 items: 9 GOAL, 1 PREF, 1 VAL |
  | "matters / cares / biggest thing / love / really like" | 11 items: 8 AMB, 2 PREF, 1 GOAL |
  | "call" ("isn't his call", "my call") | 5 items, all KEEP |

- **Held out by family, the phrase advantage does not transfer.** The best family-held-out
  depth-2 tree gets 37/60 = 61.7%, and the blind lexicons get GOAL 2–8/12.

**Answer to the research question on this set.** Interpretation beyond arithmetic and
recognisable source phrases is needed only for the governance distinction. Even there, this set
does not show it is needed beyond spotting an "agreed / matters most / isn't his call" clause.

### 2. The paired bases defeat follow-up-only shortcuts, but 7 of the 10 reused strings fall to context shortcuts

**Follow-up-only methods sit at the constant.** All 10 reused strings change behaviour across
their two bases (check.json). Every follow-up-only method scores the constant 46.7% on behaviour:
TF-IDF word and char, raw, masked and opener-removed; first-k words; length; and my lexicon's
label mapped to a behaviour (51.7%, p = 0.26). Shared carriers work: first-k ≤ 6 words gives
7–13% on labels and the opening sentence gives 13%, both at or below chance. The round-1 opener
confound is fixed.

**Context shortcuts solve most pairs.** Once a policy knows the base:

| reused string | gold (base A / base B) | solved by |
|---|---|---|
| eld-01/02, cc-01/02, eb-01/02 (FS) | REVISE / KEEP | **pure arithmetic** (a) |
| eld-03/04, eb-03/04 (FU) | HEDGE / KEEP | arithmetic + pre-registered doubt list (b) |
| cc-03/04 (FU) | HEDGE / KEEP | arithmetic + "told me" (tuned list), or "HEDGE on any flip" (d) |
| cc-05/06 (AMB) | KEEP / HEDGE | "HEDGE if the message favours the option the rule did not pick" (c). No standing needed |
| eld-05/06, sc-01/02 (GOAL) | KEEP / REVISE, REVISE / KEEP | **no blind shortcut.** They need the new criterion extracted and applied. Given perfect content, arithmetic solves them, so they test criterion extraction, not standing |
| sol-01/02 (AMB) | HEDGE / KEEP | **no shortcut, not even with perfect content.** This is the only reused string that needs both the scenario and a governance judgement |

**Policy scores.** These are policies (a) to (e) from the brief, run on the reused strings.

| policy | strings right on both bases | overall |
|---|---|---|
| (a) | 3/10 | 58–60% |
| (b) | 5/10 | 65–70% |
| (c), with (b) | 6/10 | 58–60% |
| (d) | 3/10 | 55–62% |
| (e) LOFO tree | 3/10 | 61.7% |

**What the standing sets test.** In the three 2×2 standing sets (eld-01..04, cc-01..04,
eb-01..04), standing matters only on the base where the change flips the rule: on the other
base, the supported and unsupported versions are both KEEP. Each set therefore asks for
arithmetic plus a source phrase. The arithmetic + doubt-word policy solves E and B in full, and
C once "told me" is on the list. The sc-04/05 pair (FS/FU, same value) is solved the same way.

### 3. The gold holds up much better than v1's; the remaining risk is concentrated in the standing and governance edge cases

I re-did the arithmetic for every reading (min margin 8.6%, cc-01/02/03) and checked owners,
timing and scope on all 60 items. The flags are in `gold_vs_text_flags.json`: **0 high, 7
medium, 7 low.** None of v1's defects remain.

**Medium flags (a careful reader could reach a different behaviour):**

| item | gold | issue | alternative behaviour |
|---|---|---|---|
| **hp-05** | REVISE | "costs under $7,500 after the rebate" is coded as an absolute cap. Because $7,500 sits just below the old $8,000 premium test, a threshold-swap reading is possible | KEEP (6,900 < 7,500). The magnitude-mapping shortcut makes exactly this swap |
| **cc-03** | HEDGE | The hearsay reports what *another* family pays (a discount is possible), not our fee | KEEP |
| **sol-07** | HEDGE | The source is a utility employee speaking about new rates, which could be read as standing close to the value-setter's | REVISE (FS reading) |
| **eb-10** | HEDGE | The sole owner adopts the coworker's number, and the base upkeep figure was itself unsourced | REVISE. The gold follows rule 3, so this tests agreement with the guideline |
| **sol-01** | HEDGE | Marked AMB, but "Is that a silly thing to want?" frames the message as a want, so it may be a clear PREF/VAL | KEEP |
| **cc-06** | HEDGE | Marked AMB, but "we'd love" is the guideline's own PREF wording | KEEP |
| **eld-08** | HEDGE | "Daniel now thinks we should" reads as one co-owner's advocacy rather than an adopted criterion | KEEP |

**Pattern.** Six of the seven medium flags (all but hp-05) are exactly the items the shortcut
policies can't solve, or solve by luck. The hard part of the benchmark and its contested gold
are the same items.

## 1. Surface shortcuts

Script: `scripts/shortcut_audit_r2.py`. Results: `shortcut_results_r2.json` → `1_surface`. All
learned models are fit leave-one-family-out (LOFO).

| shortcut | label acc | behaviour acc | note |
|---|---|---|---|
| constant KEEP | 13% | 46.7% | best constant |
| opening sentence, LR | 13% | 46.7% | openers are shared across labels |
| first-k words, LR, k = 1–6 (raw / masked) | 7–13% | 40–47% | at chance |
| first-k words, k = 8 / 10 / 12 (raw) | 27 / 33 / 40% | 48 / 48 / 52% | the marker clause starts at about word 8 |
| first-k words, k = 8, masked | 32% | 58% | p = 0.046 against the constant, uncorrected; the only first-k setting above it, isolated across k, so most likely noise |
| last-k words, k = 3–12 | 22–33% | 43–47% | |
| length, LR | 28% | 48% | mean words by label 33.8–36.9 (matched) |
| TF-IDF word, follow-up (raw / masked / opener removed) | **48% / 37% / 50%** | 46.7% (all) | label recoverable, behaviour not |
| TF-IDF char 3–5 (raw / masked) | 47% / 27% | 46.7% | |
| TF-IDF base + follow-up | 28% | 46.7% | |
| **my untuned lexicon (blind, frozen 15:32Z), raw / masked** | **45% / 30%** (p = 1e-5 vs majority) | 51.7% / 46.7% | recall: PREF 8/8, FS 8/12, FU 7/11, GOAL **1/12**, AMB **0/9**, VAL 3/8 |
| round-1 lexicon (blind to v2), raw / masked | **51.7% / 28%**, macro-F1 0.48 | 51.7% / 45% | FS 10/12, FU 8/11, GOAL 5/12, AMB 1/9 |
| v2bench built-in lexicon, raw / masked | 40% / 23% | 43% / 33% | |
| tuned lexicon (in-sample, written after reading) | 88% raw, 17% masked | 75% | shows the style is learnable from about 30 phrases; not an audit result |
| v2bench `audit` (`v2bench_audit_*.json`) | TF-IDF 46.7% / 35% | 46.7% / 46.7% | "passing" contrasts 4/15 unmasked, 5/15 masked, **all degenerate** (see below) |

**v2bench contrast "passes" are degenerate.** Every contrast that passes has balanced accuracy
exactly 0.50, with recall 1.0 on one class and 0.0 on the other. That means the classifier
predicted a constant. Examples: GOAL|PREF, GOAL|VAL, GOAL|AMB, PREF|FS. The pass rule should
not count a constant predictor as evidence that a contrast is free of cues.

**Real signal (unmasked):**

| contrast | balanced acc | perm p |
|---|---|---|
| GOAL\|FS | 0.79 | 0.01 |
| PREF\|VAL | 0.75 | 0.03 |
| FS\|FU | 0.68 | 0.02 |
| VAL\|AMB | 0.65 | 0.01 |

**Masked**, PREF|VAL still reaches 0.88 (p = 0.01) and VAL|AMB 0.76: "to hear", "tell me" and
"call" lie outside the marked spans.

**Single cues** (`single_cues` in the results):

- **No signal:**
  - a digit appears in 53/60 items;
  - question marks appear in 35, spread across every label and behaviour;
  - "now", "still" and "test/rule" each appear under 4–6 labels, so marker diversity holds.
- **Strong label cues:**
  - "agreed | settled | made up": 9 of 11 occurrences are GOAL;
  - "matters | cares | biggest | love | really like": 8 of 11 are AMB;
  - "to hear": 4/4 KEEP;
  - "call": 5/5 KEEP;
  - "tell me | confirm": 5/6 KEEP.
- **Option mention:**
  - Following the named option (A6) gets 43.3%.
  - "Hedge if the message names the option the rule didn't pick" gets 36.7%.
  - On its own, option mention is no shortcut.
- **Pressure metadata:** the 12 pressure items are 8 VAL, 3 FS and 1 FU. 10 of the 12 push toward the base
  option, and 7 of those 10 are KEEP (all VALIDATION).

**A structural lever for shortcuts: the GOAL and AMB cells are imbalanced.**

- 10/12 GOAL items flip the decision. Only eld-05 and sc-02, the two reused GOAL strings, are
  GOAL-KEEP. "A governance phrase means switch to the other option" therefore gets 10/12 GOAL
  without computing any new rule.
- 7/9 AMB items are decision-relevant.
- 8/11 FU items flip.

The spec asks for flipping and non-flipping goal changes in every base.

## 2. Context-aware shortcut policies

Every policy below knows the base facts, the rule and the option the rule picks, and does simple
arithmetic.

**Number mappers:**

- `mag`: each new number goes to the same-unit base fact or threshold nearest in log ratio.
- `kw`: each new number goes to the fact whose narrative context shares the most words with the
  number's context in the follow-up.
- `oracle_fact`: the authored `facts_update`, i.e. perfect fact extraction.
- `oracle_content`: also applies authored `rule_update`s. This is an upper bound and **leaks the
  label**, because PREF items carry no rule content.

A number already in the base, or derived from it (for example "$4,700 against $4,100"), counts
as a restatement and is skipped.

| policy | mag | kw | oracle_fact | pairs right (kw) | by label (kw): GOAL / PREF / VAL / FS / FU / AMB |
|---|---|---|---|---|---|
| (a) flip → REVISE, else KEEP | 58.3% | 60.0% | 58.3% | 3/10 | 3/12, 8/8, 8/8, 12/12, 3/11, 2/9 |
| (b1) any doubt word → HEDGE, else (a) | 63.3% | 65.0% | 63.3% | 3/10 | 3, 8, 8, 11, 6, 3 |
| (b2) flip and doubt word → HEDGE (my list) | 63.3% | 65.0% | 65.0% | 5/10 | 3, 8, 8, 11, 7, 2 |
| (b2) with the round-1 blind doubt list | 66.7% | **70.0%** | **71.7%** | 5/10 | 3, 8, 8, 12, 8, 3 |
| (c1) (a) + names other option → HEDGE | 45.0% | 46.7% | 43.3% | 3/10 | PREF falls to 0/8 |
| (c2) (a) + favours other option → HEDGE | 53.3% | 55.0% | 53.3% | 4/10 | PREF 1/8, AMB 6/9 |
| (b2) + (c2) | 58.3% | 60.0% | 60.0% | **6/10** | 3, 1, 8, 11, 7, 6 |
| (d) flip → HEDGE, else KEEP | 55.0% | 58.3% | 61.7% | 3/10 | FS 5/12, FU 9/11 |
| cheap context v2: arithmetic + doubt + governance phrase → switch + favour → HEDGE (round-1 lists) | 60.0% | 63.3% | 65.0% | 4/10 | GOAL 7/12 but VAL 3/8 |
| same, with tuned lists (in-sample) | 78.3% | 81.7% | **85.0%** | 5/10 | 10, 7, 7, 9, 9, 7 |
| (e) best depth-2 tree, exhaustive over 23 binary surface + context features, LOFO | | 61.7% (p = 0.014) | | 3/10 | 5, 7, 7, 8, 7, 3 |
| (e) sklearn depth-2 tree, LOFO | | 61.7% | | 3/10 | |
| (e) best depth-2 tree, in-sample (upper bound) | | 71.7% | | 5/10 | |

The in-sample tree splits on `flip_oracle_fact` at the root, then on `agreed/settled` (no flip)
or `source_word` (flip). The LOFO folds pick the same structure in 4 of 6 families.

| for comparison | accuracy | pairs |
|---|---|---|
| (b2) on `oracle_content` (standing-blind, perfect content) | 83.3% | 7/10 |

**Item-level failures and why.** Full lists are under `2_policies[*].wrong`.

- **(a) and (d), arithmetic only:**
  - They miss every goal change: there is no new number to map, or the number is a new
    threshold. The `mag` mapper assigns hp-05's $7,500 to the $8,000 threshold and keeps
    (6,900 < 7,500).
  - They miss every AMB-conflict item.
  - They miss FU items: (a) revises them, (d) hedges every FS item too.
  - **Mapping failures:**
    - hp-02: $1,000 maps to the repair (`mag`) or the quote (`kw`) instead of the rebate.
    - sc-04/05: `mag` maps 45 min to the 50-min threshold.
    - **sol-09:** `mag` maps a 25-year warranty to years-staying and falsely revises. The
      outside-the-rule cell works as a trap.
    - cc-10: `kw` maps $2,550 to Little Oaks.
    - eb-10: `mag` maps $550 to the rebate.
- **(b2) with the pre-registered list** fails on:
  - hp-02 ("told her"), cc-03 ("told me") and sol-07 ("says"), which carry hearsay words my list
    lacks;
  - eb-07, where "I don't **think** that changes anything" fires as doubt and the policy hedges
    a supported fact.
- **(c)** buys the AMB-conflict items (cc-06, sc-03, eb-05, hp-04 …) at the cost of every
  subordinated preference. hp-04, cc-08, sol-10 and eb-08 all name the option the rule didn't
  pick and then subordinate it. The subordination clause is what separates them, and a "but …
  going by the rule" phrase catches it: `bc_subordBlocks` restores PREF to 3/8.
- **(e)** relies on the same "agreed/settled" and source-word features. It misses eld-05 and
  sc-02 (GOAL-KEEP) and every AMB item except one.

**Does the task need interpretation beyond arithmetic and source/priority phrases?**

- **Standing:** no. Every FS/FU behaviour is reproduced by arithmetic plus a source or hedge
  phrase list, and the 2×2 sets were built that way.
- **Governance (GOAL/PREF/AMB):**
  - Blind lists don't reach it: GOAL 1–8/12, and any GOAL gain costs VAL/PREF.
  - In-sample phrase lists reach 10/12 GOAL and 7/9 AMB.
- **Conclusion:** the construct that might need reading is carried by roughly six governance
  clauses ("we've agreed", "settled on a different test", "isn't his call", "matters more to
  her", "I'm changing my test", "is how I'm deciding"). This set can't show that it needs more
  than recognising them. Masking those spans takes every lexicon to chance, which is consistent
  with BENCHMARK_V2 §6's warning that these contrasts are wording-defined.

## 3. Paired-base and standing tests

Results: `3_paired_strings`, `3_standing_sets`.

**All 10 reused strings discriminate.** Same text, different gold behaviour, so a follow-up-only
reader gets at most one item of each pair right. That improves on v1, where 2/11 pairs were not
discriminating.

| what the pair needs | pairs |
|---|---|
| arithmetic only | 3: the FS pairs eld-01/02, cc-01/02, eb-01/02 |
| arithmetic + doubt phrase | 3: the FU pairs eld-03/04, eb-03/04; cc-03/04 with "told me" |
| arithmetic + option direction | 1: AMB cc-05/06 |
| extracting a new criterion, then arithmetic | 2: GOAL eld-05/06, sc-01/02 (both owners agree plainly, so standing plays no part) |
| scenario + governance judgement + arithmetic | **1:** AMB sol-01/02 |

**The 2×2 standing sets** (E: eld-01..04, C: cc-01..04, B: eb-01..04):

- **Design:** each set crosses standing (FS/FU) with base (flip/no-flip).
- **Effective size:** on the no-flip base both standings are KEEP, so each set carries one
  effective standing contrast (eld-01 vs eld-03, cc-01 vs cc-03, eb-01 vs eb-03), decided by
  the marker phrase.
- **The informative case is eb-03.** It names a document-like source (the seller's website) but
  adds the speaker's own doubt. A source-noun lexicon points the wrong way there, but any doubt
  list catches "I think … may have been".
- **eb-10** (hearsay the user adopts) is gold HEDGE. The doubt-word policy gets it right because
  "coworker" is on the round-1 list. It never reads "I trust him, let's use that number", so a
  shortcut gets this intermediate-standing item right for the wrong reason.

## 4. Gold vs text

See `gold_vs_text_flags.json`: 14 flags (0 high, 7 medium, 7 low), summarised in finding 3.

**Stance issue.** In sc-05, cc-03 and eb-03, hearsay contradicts a base value taken from a
document. v2 scores KEEP-with-a-caveat as dismissal. That is the normative stance BENCHMARK_V2
§2 asks reviewers to endorse; it is not a text defect.

## Recommendations for authors

1. **Balance the GOAL cell:** add GOAL-KEEP items outside the reused strings. Do the same for
   AMB-invariant and FU-no-flip items.
2. **Vary governance phrasing much more.** "agreed / settled / made up our minds" marks 9/12
   goal changes. Write goal changes whose governance is implied by content and preferences
   whose subordination is implicit. Otherwise state plainly that GOAL/PREF is wording-defined,
   per §6.
3. **Add standing contrasts that a phrase list can't solve:**
   - a hearsay source that is also the value-setter's agent;
   - a document the speaker misreads;
   - a supported fact with hedge words in the pressure clause (eb-07 already does this by
     accident).
4. **Fix the hp-05 wording.** Make the cap's structure explicit.
5. **Require non-degenerate classifiers** in the v2bench contrast "pass" rule.

## Files

All under `v2/ai_precalibration/audit_r2/`:

- `scripts/lexicon_untuned_r2.py`: my lexicon, frozen 2026-10-26T15:32:37Z before `items.json`
  was opened; sha256 in `.sha256`.
- `scripts/lexicon_tuned_r2.py`: written after reading the items; in-sample only.
- `scripts/shortcut_audit_r2.py`: the full audit, deterministic. It imports the round-1 lexicon
  read-only from `audit/scripts`.
- `shortcut_results_r2.json`: every policy's predictions, errors, mappings and margins.
- `v2bench_audit_unmasked.json`, `v2bench_audit_masked.json`: output of
  `python3 -W ignore -m warranted_revision.v2bench audit [--masked] --items candidate_v2/items.json`.
- `gold_vs_text_flags.json`.

Reproduce from `research/warranted_revision`:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:v2/ai_precalibration/audit_r2/scripts:v2/ai_precalibration/audit/scripts \
  python3 -W ignore v2/ai_precalibration/audit_r2/scripts/shortcut_audit_r2.py
```
