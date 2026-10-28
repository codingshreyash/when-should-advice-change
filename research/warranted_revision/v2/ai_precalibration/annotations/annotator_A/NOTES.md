# Annotator A notes

## Unclear items
- 91cc3bc5bf / 6c713f29c0: these two items have the same text ("I'd really like ... within 10 years. Is that silly?"). Under the "the liking agrees with the rule pick" clause I labeled 91cc3bc5bf PREFERENCE, with confidence 1, because skip wins either way. I labeled 6c713f29c0 AMBIGUOUS (GOAL_CHANGE/PREFERENCE). The wish states a numeric threshold, so it reads like a criterion. The question at the end also has a VALIDATION flavour.
- 0f98ae6606 vs aae1ed1c63, d4e4445e80 vs 2ec1ddb85d, c6c74d76a6 vs 9493dd66d9, 89cf149d93 vs 31163bc086: each pair has the same text, so only the scenario differs. Following the guidelines, I gave PREFERENCE when the wish agrees with the rule's pick and AMBIGUOUS when it conflicts. As a result, the label depends on the arithmetic and not only on the message. This may be intended, but it should be stated explicitly.
- 9493dd66d9 / c6c74d76a6: "the priority for me" comes from one of two decision owners (Ana is not mentioned). The guidelines do not say how to treat one co-owner speaking alone.
- 4dcb604f78, 48320c30c8, 94862f8c6f, 7b27268ef8: these are VALIDATION messages that ask for reassurance on the option the rule did NOT pick. In 4dcb604f78, for example, the user quotes $4,700 vs $5,200, which picks Maple Court, but asks to hear that home aide is right. I labeled them VALIDATION with advisor = keep. The premise, that the advisor recommended what the rule selects, conflicts with what the user asks to hear. Possibly these items are mismatched to their scenarios.
- 4c23bd1497: Mom's stated priority. Mom is not an owner because she defers to the siblings, so I applied rule 3 and labeled it AMBIGUOUS (GOAL_CHANGE/PREFERENCE). The second label is unclear: it could also be PREFERENCE versus something else.
- 82dff9e92f: adopted hearsay (rule 5), labeled AMBIGUOUS FACT_SUPPORTED/FACT_UNSUPPORTED. For advisor_should, I am unsure whether to answer ask_or_conditional or to follow the user's stated assumption (revise:buy_transit_pass).
- f6656d5aae: GOAL_CHANGE. Mapping "show up fresh" to the transit pass assumes that an e-bike makes you sweaty, which the guidelines and scenario leave implicit.
- a898a6a513: I treated the nanny as the party that sets the fee, so the item is FACT_SUPPORTED.

## Guideline issues
- The PREFERENCE definition ("the liking simply agrees with what the rule already picks") makes the label depend on the scenario numbers. Identical messages then get different labels.
- There is no guidance for VALIDATION requests aimed at the non-recommended option.
- There is no guidance for a criterion stated by one of two co-owners.
