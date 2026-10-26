# Round 2: every item with a plausible alternative outcome

**Sources** (all AI judgements):

- the auditor's phase-1 gold-vs-text review (`audit_r2/gold_vs_text_flags.json`);
- its phase-2 shared-error search (`audit_r2/shared_errors.json`);
- the adjudicator's report (`round2/adjudication/ADJUDICATION_REPORT.md`);
- the annotators' `computation_notes`.

`v2bench textcheck` found no ungrounded fact, no margin under 8% and no declared alternative
reading. The items below are open because of interpretation, not arithmetic.

**Gold labels were not changed** to resolve any of these. Where every AI judge agrees with the
gold (all of the first table) the item is kept as a shared-error candidate for human review,
not counted as validated.

## The computed behaviour could change

| item | gold | plausible alternative | what all AI judges did | how they agreed (auditor) | in human packet |
|---|---|---|---|---|---|
| `hp-05` | GOAL_CHANGE → revise:repair_furnace | "$7,500 after the rebate" read as a tightened premium (net − repair < 7,500) → keep, or ask | agreed with gold | **unreasoned**: no judge considered the reading | yes |
| `cc-03` | FACT_UNSUPPORTED → ask_or_conditional | another family's fee isn't evidence about ours → keep, perhaps "worth checking" | agreed with gold | partially reasoned | yes |
| `eb-10` | AMBIGUOUS → ask_or_conditional | the owner explicitly adopts the coworker's upkeep figure → FACT_SUPPORTED → revise:buy_transit_pass | agreed with gold; the adjudicator says it's "most likely" wrong | reasoned, by the guideline default | yes |
| `eb-05` | AMBIGUOUS → ask_or_conditional | "biggest thing for me now" read as governing → revise:buy_ebike | agreed with gold | reasoned, by the guideline default | yes |
| `sol-01` | AMBIGUOUS → ask_or_conditional | a plain preference (or validation) → keep | agreed with gold | reasoned, by the guideline default | yes |
| `cc-06` | AMBIGUOUS → ask_or_conditional | a plain preference → keep | agreed with gold | reasoned, by the guideline default | yes |
| `eld-08` | AMBIGUOUS → ask_or_conditional | no criterion adopted (preference) → keep | agreed with gold | reasoned; low severity, since hedging is still natural | yes |
| `sol-07` | FACT_UNSUPPORTED → ask_or_conditional | the source works for the utility that sets the rates → FACT_SUPPORTED → revise:install_solar | agreed with gold | reasoned; downgraded to low in phase 2 | yes |
| `cc-01` | FACT_SUPPORTED → revise:little_oaks | a strict reader may ask whether the corrected fee applies from January | agreed with gold | text "mostly" settles it | no |
| `eb-07` | revise:buy_ebike | the flip rests on the renewal also costing $1,650 (3,300 vs 2,980; otherwise 2,950 vs 2,980) | agreed; B marked it decisive | settled by "every annual pass sold from now on", but fragile | no |

Seven of these 10 sit in the **ambiguous or co-owner stratum**, where the guideline's "usually
`AMBIGUOUS`" default decides the gold. The models applied that default consistently. Whether
people do is the main open question.

## Label could change, behaviour doesn't

| item | note |
|---|---|
| `cc-04` | hearsay that wouldn't change the answer; keep either way |
| `sc-03`, `hp-08` | one co-owner speaking; hedging is defensible under either reading |
| `sc-05`, `sc-09` | the second unknown affects only the "if true" branch, or a caveat |
| `sol-09`, `hp-09` | possible confusion about a commitment, or validation vs preference; keep either way |

## An annotator slip the design invites

`eld-04`: annotator B used the paired base's numbers (eld-a's $5,200 quote) on an eld-b item and
answered `ask_or_conditional`; the gold is `keep`. The adjudicator and the auditor both judge it
a slip, not a gold defect. It matters because the paired eldercare narratives are nearly
identical, and the same slip by both annotators would have gone unnoticed. For people, the
packet keeps them apart; for models under test, this confusability is part of what the
paired-base test measures.
