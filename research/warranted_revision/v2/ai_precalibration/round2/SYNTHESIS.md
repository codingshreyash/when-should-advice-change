# Round 2 synthesis (AI-only pre-calibration)

Every judgement here comes from an AI model:

- the author, the auditor, the adjudicator and the checkpoint reviewer ran on the session's
  Claude model;
- annotator A ran on Claude Opus;
- annotator B and the context-blind baseline ran on Claude Sonnet.

All are from one provider. Nothing here is human validation. B1's human gate has not been run,
no model has been evaluated as a subject on v2 items, and no paid API or GPU was used.

Round-1 files and `candidate_v1` are unchanged. Each agent's output was committed before any
later step could see it:

| step | commit |
|---|---|
| author (`candidate_v2`) | `dee6fc3` |
| baseline | `723a1e9` |
| annotator B | `ca74893` |
| annotator A | `8996ed2` |
| adjudicator, blind labels | `19ab28e` |
| adjudicator, final | `6c976d4` |
| auditor, phase 1 | `a840631` |
| auditor, phase 2 | `013240d` |
| checkpoint | `ef0a4da` |

The human-review selection rule was committed (`3e00f8f`) before the auditor's findings were
read.

**Isolation.** Every agent's own tool calls were searched for forbidden paths. All matches were
inspected by hand, and every one was a false positive: a forbidden name appearing in the
agent's report text, or in a JSON field name. No forbidden file was opened.

## 1. candidate_v2 and the guidelines

**Guidelines v0.2** (`v2/annotation/GUIDELINES_v0.2.md`) split each item into two questions:

- **What the message communicates** (the label). It is judged without regard to which option
  the numbers favour.
- **What it warrants** (`what_changes`, `advisor_should`, `computation_notes`).

They also add principles for co-owners, non-owners, evidential standing, timing and scope.

**candidate_v2** (`../candidate_v2/`):

| property | value |
|---|---|
| items | 60 |
| scenario families | 6 |
| base scenarios | 12 |
| behaviours | KEEP 47%, REVISE 28%, HEDGE 25% |

**Defects fixed:**

- `eb-04`, `eb-07` and `eb-08` (the high-severity round-1 gold defects) were replaced.
- The four round-1 strings whose label changed with the numbers were removed.

**Item types added:**

- supported changes that stay under the threshold;
- large supported changes to numbers the rule doesn't use;
- three sets that cross evidential standing with two base scenarios.

**Checks:** `v2bench check` reports no problems, and `textcheck` reports no ungrounded fact, no
margin under 8% and no undeclared alternative reading. In the auditor's own review, none of
round 1's gold defects remain: it raised 0 high, 7 medium and 7 low flags.

## 2. A reproducible gold-versus-text audit

There are two parts:

- **Mechanical:** `python -m warranted_revision.v2bench textcheck --items ../candidate_v2/items.json`
  (grounding, margins, declared alternatives, label consistency of reused strings).
- **Reviewed:** the auditor's `audit_r2/gold_vs_text_flags.json` (phase 1) and
  `audit_r2/shared_errors.json` (phase 2), with scripts in `audit_r2/scripts/`.

## 3. Items with plausible alternative outcomes

See `analysis/ALTERNATIVE_OUTCOMES.md`. **Ten items** could change their computed behaviour:

- `hp-05`
- `cc-03`
- `eb-10`
- `eb-05`
- `sol-01`
- `cc-06`
- `eld-08`
- `sol-07`
- `cc-01`
- `eb-07`

**Shared-error candidates.** On every one of the ten, all AI judges agreed with the gold. Seven
are kept for human review rather than counted as validated (`eb-10`, `eb-05`, `sol-01`,
`cc-06`, `cc-03`, `hp-05`, `eld-08`).

- In `hp-05`, no judge even considered the alternative reading, a tightened version of the
  rule's original threshold.
- In five of the seven, the judges saw the alternative and chose the gold because the
  guidelines' "usually `AMBIGUOUS`" default told them to.

No label was changed to make anyone agree.

## 4. Does the same follow-up produce different warranted behaviour under paired bases?

**Yes**, for all 10 reused strings, and each keeps the same label on both bases (the v0.2 fix
holds).

| judge | both bases right |
|---|---|
| both annotators | 9/10 |
| context-blind baseline | 0/10 |

The one miss (`eld-04`) is an annotator using the sibling scenario's numbers, a slip the
near-identical paired narratives invite.

**But context-aware shortcuts take most of them** (`audit_r2/SHORTCUT_AUDIT.md`):

- Arithmetic alone solves the supported-fact pairs.
- Arithmetic plus a doubt word solves the unsupported-fact pairs.
- "Hedge if the message favours the other option" solves one ambiguous pair.
- Extracting the new criterion solves the goal pairs.

No single cheap policy solves more than 6/10, and only `sol-01`/`sol-02` needs the scenario and
a governance judgement together. In the evidential-standing sets, both standings give `keep` on
the base where the value wouldn't flip the decision. So each set holds only one real standing
contrast.

## 5. Does the task still need interpretation beyond arithmetic and recognisable phrases?

**Mostly no.**

| policy | behaviours right (of 60) |
|---|---|
| knows the base rule, recomputes with any new number, hedges on a doubt word | 42–43 (70–72%) |
| always keep | 28 (47%) |
| context-blind model, labels | 60 (100%) |
| context-blind model, behaviours | 48 |

**Where the arithmetic-and-hedge-word policy goes wrong:**

- It misses 17 items, mostly goal changes and ambiguous items, and those are marked by
  governance phrases: "agreed / settled" for 9 of the 12 goal changes, and "matters / biggest
  thing / love" for 8 of the 9 ambiguous items.
- A phrase list written after reading the items gets 85% (in-sample only). With the marker
  phrases masked, every list falls to chance.
- Held out by family, the best two-level decision tree gets 62%.

**The items that need real interpretation are the same items whose gold the judges dispute**
(table 3). Where interpretation is required, the answer is contested. Where it isn't contested,
it can be read off phrases plus arithmetic. This is consistent with the round-1 conclusion:
evidential standing and goal governance are defined by their wording.

## 6. A proposed small human review

`human_review_packet/` (not sent) holds 23 items, built blinded with the existing tooling:

- **13 difficult:** every adjudicated item plus every high- or medium-flagged item;
- **10 random controls:** stratified by label, seed fixed in advance.

It answers what AI agreement can't:

- Do people side with the gold or the auditor on the 7 shared-error candidates?
- Do they use `AMBIGUOUS` and hedging where the models did?
- Do they reproduce the gold on the controls?

Its decision rule is fixed in its README. It takes about 1 hour per reviewer plus 15 minutes of
adjudication.

## 7. Publication checkpoint (`PUBLICATION_CHECKPOINT.md`)

**Verdict: a workshop-scale diagnostic as it stands.**

What v2 tests once the shortcuts are accounted for is reading explicit scope clauses, recomputing
a stated rule, and spotting source and uncertainty words. The estimand, the trade-off between
warranted and unwarranted updating, validation-seeking, and the harm anti-sycophancy training
does to rational updating are all already published.

**The one differentiated question is paired-base consequence sensitivity.** Given a
byte-identical, legitimate update, does a model's revision follow its consequence for this
decision, or the arrival of a message of that type? Over-revision on the base where nothing
should change is a failure that existing benchmarks don't isolate. They either always require a
change, or never hold the text fixed across scenarios. That rests on the checkpoint reviewer's
search. BeliefShift's full text is unread and could narrow this further.

**Whether that question has a non-trivial answer is unknown, because no model has been run.**
With explicit rules, capable models may simply compute it.

**The checkpoint specifies, but does not run, the smallest deciding experiment:**

- **Items:** the 60 items, plus about 12 new goal-change pairs and integrated-state controls.
- **Models:** two open models and two API models.
- **Conditions:** a neutral or an anti-sycophancy system prompt.
- **Size:** about 6.6k calls per model.
- **Cost:** roughly $50–90 in API calls plus about 4 GPU-hours. **Needs your approval.**

**Decision rules (fixed):**

- **Go to human validation and scale-up** if the following holds in two or more models that pass
  the controls: over-revision on no-flip bases at least 20 points above the neutral rate, or a
  drop of at least 15 points in accepting legitimate goal changes under anti-sycophancy
  prompting.
- **Stop or pivot** if paired consistency is at least 0.85 with little effect.

## Recommendation

1. **Do not run B1 and do not expand the item count.** At this stage the benchmark measures
   phrase-reading plus arithmetic, and its interpretive core is contested.
2. **The next decision is yours:** either approve the small subject-model experiment, which
   decides whether paired-base consequence sensitivity is a real model failure, or stop here
   and write up the pre-calibration as a negative methods note.
3. **The 23-item human review is worth running** in either case if you have two people for an
   hour. It is the only way to settle the 7 shared-error candidates and the guideline's
   ambiguity default, and it doesn't depend on the experiment.
4. **If the experiment goes ahead,** fix `hp-05`, `cc-03` and the `eb-10`-style adopted hearsay
   in a candidate_v3 first. candidate_v2 and every round-2 result stay as they are.
