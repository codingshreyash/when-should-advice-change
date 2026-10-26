# Round 2 adjudication report (AI pre-calibration)

Adjudicator: AI model. Blind labels were committed before I saw the queue. Inputs: GUIDELINES_v0.2.md, blind_input.csv, then queue.csv. Per-item results: `final.csv`.

## Outcome

- **Labels.** My blind label matched both annotators on all 10 items, second label included: 8 AMBIGUOUS GOAL_CHANGE/PREFERENCE, 1 AMBIGUOUS FACT_SUPPORTED/FACT_UNSUPPORTED (5bf9129bea), 1 FACT_UNSUPPORTED (0b21f2f232).
- **advisor_should.** My blind answer matched both annotators on 9 items. The one split was **0b21f2f232**: one annotator chose `ask_or_conditional`, claiming the rumoured $4,300 rate would flip the answer. Its notes say "5,200 -> about 4,300" and "otherwise Maple stays". Those are the numbers of the other Maple Court item (4ec62f47e6, aide quote $5,200, rule picks Maple Court). In 0b21f2f232 the quote is $4,100 and Maple Court nets $4,700, so the rule already picks the aide. A rumoured rise to $4,300 changes nothing. The other annotator and I said `keep`, which I think is right. Cause: `incorrect_annotation`, meaning the annotator carried facts over from a sibling scenario.
- **Causes.** The other 9 items are `genuinely_ambiguous_message`. The guidelines' principles 1–3 explicitly make wishes from owners or a single co-owner, and hearsay the user relies on, AMBIGUOUS.

## (1) Shared pattern

All 10 items come from the same three principles:
- a wish or "what matters most" with no word on how the decision is now made: 88bd, b3d5, dd2d, 296d, 5722;
- a criterion stated by one co-owner, or by a non-owner, without stated adoption by the others: 4ec6, 2bb0, a5ae;
- hearsay the user explicitly decides to rely on: 5bf9.

Plus one plain hearsay item (0b21). All three of us applied the "usually AMBIGUOUS" default the same way. Paired items with identical wording (solar, nanny) got identical labels, and only advisor_should followed the numbers. That is the separation v0.2 was written to produce. The only real disagreement was an arithmetic/context slip, not a difference of interpretation.

## (2) Errors two agreeing models plus me could share that this check cannot detect

- **Guideline literalism.** We all read principle 1 ("usually AMBIGUOUS") as near-mandatory. A human user saying "that's the biggest thing for me now" (dd2d) or "let's just use that number" (5bf9) may plainly mean "decide on this". Three models trained in similar ways agreeing is not evidence that this is how people read these messages. The 59/60 agreement mostly measures shared priors.
- **Shared default assumptions in the arithmetic**, none of which the text establishes:
  - solar payback with no discounting, panel degradation or price changes;
  - the e-bike's website price, the $400 rebate and the pass price all holding at the March purchase and the renewal;
  - the heat-pump rebate actually being granted after installation;
  - the daycare website price being the January price.
  None of these flip an answer here, but all of us would miss one that did.
- **Bias toward hedging.** We all default to `ask_or_conditional` when readings split. If the benchmark expects a committed answer for some designed-ambiguous items, we would all be wrong together.
- **Cross-item contamination.** Paired scenarios share wording but not numbers (the 0b21 slip). One annotator was caught here only because the other disagreed. The same slip by two annotators would pass unflagged.

## (3) Items where I suspect all three of us may be wrong

- **5bf9129bea (most likely).** The sole owner, whose own scenario number was already an estimate ("about $250"), says "I trust him, so let's just use that number. What does that do to it?" That is arguably the owner deciding which input the rule uses, which makes the warranted response `revise:buy_transit_pass` ($2,900 ≥ $2,600; break-even upkeep is $400/yr). Our `ask_or_conditional` follows the letter of principle 3. Our conditional wording does lead with the pass, so in practice the gap is small, but a benchmark key of `revise:buy_transit_pass` would be defensible.
- **dd2d5080fd (possible).** "Biggest thing for me now when I picture the next two years", from the sole owner, can reasonably be read as the criterion that now governs (GOAL_CHANGE → `revise:buy_ebike`). We all kept it AMBIGUOUS.
- **a5ae404b2d (less likely).** "Matters more to her now than the $8,000 test does … thought about it for weeks" plus "where does that leave us?" may signal a couple in transition. Because the speaker's own agreement is missing, I still think `ask_or_conditional` is right.
