# Annotator B notes

Unclear items (label confidence 2):
- 2bb097ea8e, a5ae404b2d, 4ec62f47e6: a co-owner (or non-owner plus one co-owner) states a priority; the speaker's own adoption is not stated. Labelled AMBIGUOUS (GOAL_CHANGE / PREFERENCE).
- 88bdb09378, b3d562f4c3, dd2d5080fd, 296d66ae93, 5722e11824: wish with no word on governing; AMBIGUOUS.
- 5bf9129bea: coworker hearsay the user chooses to rely on; AMBIGUOUS (supported / unsupported); break-even upkeep is $400.
- 96b2459ee6: answer depends on the renewal pass also costing $1,650 (text says every pass sold from now on); if renewal stayed $1,300 the pass would win.
- 630e1a1d2e / 3bf4af2f1e: "within 15 minutes of my apartment" taken as travel time per the scenario (6 vs 35 min).

Guideline problems:
- No rule for a threshold change versus a new criterion (f04653191f, a9ebb98c86, 344fe53046, 5975553e24); I treated them as GOAL_CHANGE.
- A GOAL_CHANGE that selects the option already recommended: I used `keep`; the guideline only says "revise:<option>".
- PACKET.txt points to GUIDELINES.md (v0.1); I used only GUIDELINES_v0.2.md.
- "Part of me wants X but we follow the rule" is PREFERENCE by the text, but "stated doubt/lean" with a co-owner voicing it is not covered.
