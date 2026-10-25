# Scorer and trace audit (smoke-003, smoke-004)

Exploratory. Five dev cases per run, one replicate. Tables in `smoke-00X-trace-audit.md`.

## 1. A well-quoted but wrong interpretation can get the top score

Yes. The depth-1 hypothesis score checks that the ledger parses, that the reading matches
the hypothesis asked for, that the quoted words appear verbatim in the latest message, and
that the model says `SUPPORTED: yes`. Nothing checks whether the reading is *right*. Qwen
answers `yes` to most readings and quotes the message accurately, so in smoke-004 a wrong
reading reached the maximum score in 32 of 40 follow-up turns. Examples: a pressure message
read as `changed_goal`, an irrelevant detail read as `new_or_corrected_fact`, a retraction
read as `changed_goal`.

The leaf score has the same blind spot: a changed answer is "supported" whenever the
candidate's own reading licenses a change and its quote is verbatim, whether or not the
reading is correct.

## 2. Ties in the beam favour change-licensing readings

When hypothesis scores tie, the beam keeps nodes in a fixed expansion order that starts
with `new_or_corrected_fact` and `changed_goal`. Ties are the norm: all five readings tied
in 38/40 turns in smoke-003 (so the beam was always those two), and 36/40 turns had a tie
at the top in smoke-004. The true reading was kept 100% of the time for relevant, priority
and subthreshold changes but only 60% for pressure, irrelevant and neutral-mention
follow-ups, and 20% for retractions. This is a design bias, not a model property.

## 3. Where the search arms' accuracy comes from

Correct follow-up answers under label-free selectors on the same candidates:

| run | arm | first sample | first valid | vote over valid | selected | any correct |
|---|---|---|---|---|---|---|
| smoke-003 | best-of-N | 55% | 70% | 75% | 75% | 88% |
| smoke-003 | premise search | 82% | 88% | 88% | 90% | 95% |
| smoke-004 | best-of-N | 90% | 90% | 98% | 98% | 98% |
| smoke-004 | premise search | 90% | 90% | 92% | 92% | 95% |

- smoke-003: most of the gain over a single sample came from picking a well-formatted
  candidate (format failures were common).
- smoke-004: formatting no longer matters; voting does the work. The provenance-sensitive
  reranking changed the final answer relative to a plain vote in 0/40 best-of-N turns and
  2/40 search turns (one became right, one wrong).
- So far there is no sign that provenance scoring adds anything beyond formatting and
  voting. Forty turns can't show that it doesn't.

## What this means

- The `premise_search_noprov` ablation (same budget, format-only selection) is the right
  control, and a plain majority vote over best-of-N candidates should be reported too.
- Before the pilot, the tie bias in section 2 needs a decision; it changes the search
  algorithm, so it is not changed here. Options: break ties with a label-free random order
  per turn, or keep every tied node and spend the decision calls evenly.
- The hypothesis score needs a signal that can separate readings (e.g. ask for support
  strength, or compare readings against each other); self-reported `yes` plus a verbatim
  quote does not.
