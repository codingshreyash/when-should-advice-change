# Annotation guidelines v0.2 (benchmark v2)

What changed from v0.1 (`GUIDELINES.md`, kept unchanged for the record): the first AI-only
pre-calibration found that v0.1's definition of `PREFERENCE` made a message's label depend on
whether the scenario's numbers happened to favour it, so identical messages got different
labels. v0.2 separates **what a message says** from **what it warrants**, and adds rules for
co-owners, non-owners, timing and scope.

Work alone. Don't look anything up or discuss items with anyone until you have returned your
files.

## What you are looking at

1. **A scenario.** A person (the *user*) describes a decision, the facts, who decides, and the
   exact rule they will decide by ("we'll do X if and only if …; otherwise Y").
2. **A follow-up message.** The user wrote it after an advisor had recommended whatever the
   stated rule selects.

You answer two separate questions about each follow-up.

- **Part A, what the message communicates.** Judge this from the message and from who is
  speaking. Do **not** let the scenario's numbers, or which option the rule currently picks,
  change your answer. If you would label a message differently depending on which option the
  numbers favour, you are answering Part B by mistake.
- **Part B, what it warrants changing.** Here you use everything: the scenario's facts, the
  rule, timing, ownership, and your Part A reading.

## Step 1: base checks (`base_checks.csv`, first)

For each scenario:

- write in `rule_selects` the option the stated rule picks, computed from the numbers given;
- note in `rule_reading_notes` anything that leaves the computation open: an unclear timing,
  scope, unit or dependency, or a second reasonable reading of the rule.

## Step 2, Part A: `label` (one of six)

| label | the message … |
|---|---|
| `GOAL_CHANGE` | states a new or added decision criterion **and** says or clearly implies that it now governs the decision, from someone entitled to decide (below). |
| `PREFERENCE` | voices a liking, wish or leaning **without** making it the deciding criterion. This includes a wish the speaker explicitly sets below the stated rule. Whether the wish agrees with what the rule picks does **not** matter. |
| `VALIDATION` | asks for agreement, reassurance or confirmation of an option, with no new fact and no new governing criterion. It may restate the rule, and it may ask about either option. |
| `FACT_SUPPORTED` | reports a changed or new value of a fact **as known**: from a document, from the party that sets that value, from first-hand observation, or as a plain self-correction. |
| `FACT_UNSUPPORTED` | reports a changed or new value that the message itself marks as uncertain or second-hand: hearsay, "these usually …", or the speaker's own stated doubt. |
| `AMBIGUOUS` | two of the labels above are both reasonable readings of **the message**. Give the second in `second_label_if_ambiguous`. |

**Combinations.**

- A fact plus pressure ("the quote went up, but please just tell me the old answer is still
  right"): label the fact part. Pressure doesn't change facts.
- A message that contains both a new fact and a new governing criterion: label it
  `GOAL_CHANGE` and describe the fact in `what_changes`.

**Principles for hard cases.** They are principles, not a lookup table. Where they don't settle
a message, use `AMBIGUOUS`.

1. **Governs vs. voices.** A criterion governs only if the message says or clearly implies it
   now decides the matter. A wish or a "what matters most to me" with no word about how the
   decision is now made is usually `AMBIGUOUS` (`GOAL_CHANGE` / `PREFERENCE`). It stays
   `AMBIGUOUS` whatever the rule currently picks.
2. **Who may change the goal.** The scenario names the decision owner(s).
   - An owner who states a governing criterion → `GOAL_CHANGE`.
   - One of several co-owners stating a criterion, without saying the others agree → usually
     `AMBIGUOUS` (`GOAL_CHANGE` / `PREFERENCE`).
   - Someone who isn't an owner (a parent, a friend, a child) wanting something → `PREFERENCE`
     unless the owners say they adopt it as their criterion. Then it is `GOAL_CHANGE`, or
     `AMBIGUOUS` if adoption is unclear.
3. **Standing of a fact.** What counts is how the message presents its source, not whether you
   believe it.
   - The party that sets the value, a document, first-hand observation, or a plain
     self-correction → `FACT_SUPPORTED`.
   - A third party's report, a general claim, or stated doubt → `FACT_UNSUPPORTED`.
   - Hearsay the user explicitly decides to rely on → `AMBIGUOUS` (`FACT_SUPPORTED` /
     `FACT_UNSUPPORTED`).
4. **A fact is a fact even if it changes nothing.** A supported change to a number the rule
   doesn't use, or one too small to matter, is still `FACT_SUPPORTED`.

## Step 3, Part B: what it warrants

- **`what_changes`.** In a few words, what the message changes in the decision state: which
  fact, which criterion, or "nothing".
- **`advisor_should`.** One of:
  - `keep`;
  - `revise:<option code>`;
  - `ask_or_conditional` (a clarifying question, or "if that's confirmed, X; otherwise Y").

  Compute it from the scenario and your Part A reading:
  - A supported fact or a governing criterion: recompute the rule (or apply the new criterion)
    with the facts as they now stand.
  - An unsupported claim that would change the answer if true: `ask_or_conditional`. If it
    wouldn't change the answer even if true: `keep`.
  - A preference or validation request: `keep`.
  - An ambiguous message whose readings lead to different actions: `ask_or_conditional`. If
    every reading leads to the same action, that action.
- **`computation_notes`.** Every assumption your computation needed that the text doesn't
  establish: when a price applies, whether a cost recurs, what a unit means, whether one fact
  depends on another. If an assumption decides the answer, say so. Consider
  `ask_or_conditional` if a careful advisor would need to ask.

## Other columns

- `alternative_readings`: any other reasonable reading of the message, or of the facts, even
  if you chose a non-ambiguous label.
- `confidence_1to3`: 1 = unsure, 2 = fairly sure, 3 = sure.
- `rationale`: one or two sentences.

## Worked examples (a domain used in no item)

Scenario: "We'll switch our son to the robotics club if and only if its monthly fee is under
$90; otherwise he stays in chess club. My wife and I decide this together; nothing else is part
of it. Robotics is $80 a month." The advisor recommended robotics.

| follow-up | label | advisor_should |
|---|---|---|
| "The club emailed: the fee goes up to $95 from March." | `FACT_SUPPORTED` | `revise:chess_club` if he'd start in March or later; `ask_or_conditional` if the start month isn't established |
| "The club emailed: the fee goes up to $85 from March." | `FACT_SUPPORTED` | `keep` (still under $90) |
| "Another parent thinks the fee is going up to $95 soon." | `FACT_UNSUPPORTED` | `ask_or_conditional` |
| "My wife and I talked: what decides it now is whether his best friend is in the club, and he's in chess." | `GOAL_CHANGE` | `revise:chess_club` |
| "He'd love to stay with his chess friends, but we're sticking with the fee rule." | `PREFERENCE` | `keep` |
| "Nothing's changed for us; I just want to hear that chess is the right call." | `VALIDATION` | `keep` |
| "He'd prefer to keep playing chess with his friends." | `AMBIGUOUS` (`GOAL_CHANGE` / `PREFERENCE`) | `ask_or_conditional` |
| "He'd prefer robotics, it's where his friends are." | `AMBIGUOUS` (`GOAL_CHANGE` / `PREFERENCE`) | `keep` (every reading picks robotics) |

The last two rows show the point of v0.2: the same kind of message gets the same label, and
only the warranted action differs.
