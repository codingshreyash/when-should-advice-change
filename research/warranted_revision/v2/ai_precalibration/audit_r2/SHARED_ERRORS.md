# Shared-error search: round 2, phase 2 (adversarial auditor)

**All of this is AI judgement.** Every judge is an AI model:

- annotators A and B (Claude Opus and Claude Sonnet);
- the AI adjudicator, which saw the 10 items in its queue;
- the context-blind follow-up-only AI baseline;
- me.

Agreement among these judges is not human validation, and shared training can produce shared
errors.

**Scope.** Phase-1 files (commit a840631) are unchanged. Item-level detail is in
`shared_errors.json`.

| read | not read |
|---|---|
| annotator_A/ and annotator_B/: items.csv, base_checks.csv, NOTES.md | round2/analysis/ |
| followup_only/items.csv | adjudication/blind_input.csv, adjudication/queue.csv |
| adjudication/: blind_labels.csv, final.csv, ADJUDICATION_REPORT.md | coordinator/packet_seed.json, coordinator/adjudication_queue_HELD.csv |
| coordinator/key.json | |

## The three most important findings

### 1. The 60/60 agreement doesn't show contextual reading: a judge that never saw the scenario also gets 60/60 labels

**What the context-blind baseline did.** It saw only the follow-up and still matched the design
label on **60/60** items. Its guessed action matches the computed gold on **48/60**, simply by
mapping each label to its default action:

| label | default action |
|---|---|
| FACT_SUPPORTED, GOAL_CHANGE | REVISE |
| FACT_UNSUPPORTED, AMBIGUOUS | HEDGE |
| PREFERENCE, VALIDATION | KEEP |

**Where the scenario matters.** It changes the gold on just 12 items. In each, the scenario's
numbers make the answer KEEP:

- cc-02, eb-02, eld-02 (supported change below the threshold);
- cc-04, eb-04, eld-04 (unsupported claim that wouldn't flip even if true);
- cc-05, sol-02 (ambiguous, but every reading agrees);
- eld-05, sc-02 (goal change that picks the option already chosen);
- hp-01, sol-09 (supported change to a number the rule doesn't use).

The annotators got 12/12 (A) and 11/12 (B) of these.

**What the agreement measures.** It shows two things:

1. the judges read the guideline's marker phrases the same way;
2. they do the base arithmetic correctly.

The phase-1 shortcut audit found the same split. It does not show that the gold follows what
the messages mean to people.

### 2. No item has a gold the text contradicts; seven have golds that rest on the guideline's AMBIGUOUS default, which every AI judge applied

**No contradicted gold.** I found no item where every AI judge endorses a gold the text
contradicts.

**The pattern instead.** In the borderline cases, the judges usually *saw* the alternative
reading and overrode it with the guideline's "usually AMBIGUOUS" default (principles 1–3). The
adjudicator says so itself: "three models trained in similar ways agreeing is not evidence".

**Candidates that need a human, in order:**

| item | gold | the reading the judges overrode | adjudicator's view |
|---|---|---|---|
| **eb-10** | HEDGE | Sole owner: "I trust him, so let's just use that number" → FS → REVISE to the pass. Both annotators wrote this reading down | "most likely" shared error |
| **eb-05** | HEDGE | Sole owner: "the biggest thing for me now" → GOAL → REVISE to the e-bike | "possible" shared error |
| **sol-01** | HEDGE | "Is that a silly thing to want?" → PREF/VAL → KEEP. B noted the validation reading | — |
| **cc-06** | HEDGE | "We'd love…" is the guideline's own PREFERENCE wording → KEEP | — |
| **eld-08** | HEDGE | Daniel "thinks we should" → PREFERENCE → KEEP | — |

For cc-06, the judges cited only the default rule. For eld-08, HEDGE stays defensible.

**Two agreements where the judges did not engage with the issue:**

- **hp-05: unreasoned.** No judge considered that "$7,500 after the rebate" could tighten the
  old premium test rather than set an absolute cap. That reading gives 6,900 < 7,500 → KEEP.
  The literal text favours the gold, so this is an untested ambiguity, not a shown error.
- **cc-03: partially reasoned.** B noted a possible discount, but every judge computed "if true"
  as if another family's fee were our fee. Nobody considered KEEP.

**Phase-1 sol-07:** both annotators weighed the utility employee's authority, so I downgrade it
to low.

### 3. The eld-04 split is an annotator slip, made likely by near-identical paired scenarios; the deciding assumptions annotators flagged are all settled by the text

**The slip.** On eld-04, B used eld-a's numbers ($5,200 quote, Maple Court as the current pick)
in an eld-b item.

**Why it wasn't copying.** In B's packet, eld-04 was row 6. B had already done eld-02 (eld-b)
correctly at row 3 and had not yet reached eld-03 (row 48), so B didn't copy its own note. It
mixed up the two eldercare bases. Those bases:

- are near-identical narratives;
- both net Maple Court to exactly **$4,700**;
- share a byte-identical follow-up.

**Verdict:**

- The item is correct; the error is the annotator's.
- The paired design invites this mix-up, and it was caught only because the other annotator
  disagreed.
- If both annotators had slipped, the error would have gone unflagged.

For v3: give a family's two bases different derived values and surface details, and keep
sibling items apart in a packet.

**Deciding assumptions annotators flagged** (task 2):

| items | assumption | flagged by | text settles it? | why |
|---|---|---|---|---|
| sc-04 / sc-05 | "45 minutes" is the bus ride alone (55 ≥ 50 → Lincoln) | A | **yes** | The base separates the "bus ride" from the "walk to the stop" |
| hp-a base, hp-06, hp-07 | the rebate is granted. Without it, all three would pick the repair | A | **yes** | The user's own rule is defined as "price minus the state rebate" |
| hp-02 | the household's later application counts as a "new application" | A, B | **yes** | They apply after installation, which hasn't happened yet |
| eb-07 | the renewal pass also costs $1,650 | B (as deciding) | **yes** | "Every annual pass sold from now on" covers it, but the gold flip rests wholly on that clause: at the old renewal price the comparison is 2,950 vs 2,980 |
| cc-01 / cc-02 | the corrected fee applies from January | A | **mostly** | No effective date is given at all |
| eb-01 | "out the door" might net the rebate | B | **no risk** | B's alternative is mis-computed: it gives 3,250 > 2,600, so the answer doesn't flip |

None of these is a shared error.

## 1. Phase-1 medium flags: what the judges did

| item | phase-1 issue | agreement type | evidence | status now |
|---|---|---|---|---|
| hp-05 | absolute cap vs premium threshold | **unreasoned** | A and B: ALT "none" | medium; human check |
| cc-03 | another family's fee ≠ our fee | **partially reasoned** | B: "different age group or discount"; A NOTES: "first-hand for her, second-hand for the user" | medium; human check |
| sol-07 | utility employee's standing | reasoned | A and B: ALT "semi-authoritative / some authority" | **downgraded to low** |
| eb-10 | owner adopts hearsay | reasoned (by principle 3) | A: "the supported reading alone would give revise"; adjudicator: "most likely" wrong | medium; human check |
| sol-01 | wish framed as a want plus reassurance | reasoned (by principle 1) | B ALT: validation reading | medium; human check |
| cc-06 | "we'd love" is PREF wording | reasoned only by the rule | A ALT: "not stated as deciding" | medium; human check |
| eld-08 | co-owner advocacy | reasoned | B ALT: PREFERENCE reading | **low**; HEDGE defensible |

**Added from the adjudicator's report:** eb-05, which I had at low in phase 1, raised to medium.
sc-03 and hp-08 stay low: the same principle-2 default, and plausible.

## 2. Answers to the brief

1. **Medium flags:** see the table above. Five are reasoned or partly reasoned agreements that
   follow the guideline's default, one is reasoned only by the rule (cc-06), and one is
   unreasoned (hp-05).
2. **Assumptions the annotators flagged as deciding:** all are settled by the text, except
   cc-01's effective date ("mostly") and sc-09, which affects only the "if true" branch of an
   answer that hedges anyway. The gold never quietly adopts a reading the text leaves open in a
   way that changes behaviour. The places where it comes close are hp-05 and cc-03, and no
   annotator flagged either.
3. **eld-04:** an annotator slip made likely by confusable paired scenarios. It is a design risk
   for annotation, not a gold defect.
4. **Candidates:** `shared_errors.json` → `shared_error_candidates`. Each entry gives the gold,
   every judge's answer, the defect, severity, whether a human is needed, and a v3 text fix.
   Items are not edited.

## 3. What this means for the human round

- **Annotator agreement is not evidence that the AMBIGUOUS stratum is right.** All AI judges
  apply the "usually AMBIGUOUS" default the same way, and a context-blind judge reproduces
  every label. Human raters should see eb-10, eb-05, sol-01, cc-06, cc-03 and hp-05 without the
  guideline's default spelled out, or should be asked separately whether they would follow it.
- **The one real AI disagreement was a context slip, not a difference in reading.** Measuring
  whether humans and models read the scenario needs the 12 "scenario says KEEP" items above.
  Those are the only ones a context-blind reader gets wrong.
