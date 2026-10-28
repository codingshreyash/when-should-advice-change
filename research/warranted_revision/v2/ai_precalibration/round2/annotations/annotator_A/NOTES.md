# Annotator A notes

## Unclear items
- c3f8104416: "ride is 45 minutes" read as bus-only (+10 walk = 55, Lincoln). If 45 included the walk, it would be Ridgeview. That reading decides the answer.
- 5bf9129bea: hearsay the user explicitly relies on, so AMBIGUOUS (FACT_SUPPORTED / FACT_UNSUPPORTED) under principle 3. I gave ask_or_conditional, but the "supported" reading alone gives revise:buy_transit_pass.
- 85b927887c: a neighbour who works for the utility. I treated this as a third-party report (FACT_UNSUPPORTED). Some annotators may treat it as semi-authoritative.
- 580fd36068 / a8479004eb: another parent reports the fee she pays herself. That is first-hand for her, but second-hand for the user. I labelled it FACT_UNSUPPORTED.
- 5c11ee69f8: the other nanny-share family is close to the source, but "thinks" marks doubt, so FACT_UNSUPPORTED.
- dd2d5080fd: the sole owner says "biggest thing for me now". This is borderline governing; I labelled it AMBIGUOUS.
- 2bb097ea8e / a5ae404b2d: a co-owner's criterion reported by the other co-owner, who does not say whether they agree. I labelled both AMBIGUOUS per principle 2.
- db5753abe2: PREFERENCE (a non-owner's view). VALIDATION is a possible second reading.

## Guideline problems
- Heat-pump scenarios: the rebate is applied for after installation. Whether to count it as certain decides 957ec113-based items and 8d24f2ed81 / 059377b67c. The guidelines don't say to assume stated rebates are granted.
- Principle 3 does not say what to do with a person who reports their own first-hand value for something the decision's party sets (e.g. the park mom's fee).
- For AMBIGUOUS FACT_SUPPORTED/FACT_UNSUPPORTED, the two readings always give different actions (revise vs ask). So the label effectively forces ask_or_conditional, even when the user explicitly adopts the number. A rule for "user-adopted inputs" would help.
- PACKET.txt says "Read GUIDELINES.md first", but the packet contains GUIDELINES_v0.2.md.
