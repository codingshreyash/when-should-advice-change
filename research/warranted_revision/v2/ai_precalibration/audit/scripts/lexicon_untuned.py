"""Adversary keyword lexicon, written from GUIDELINES.md and BENCHMARK_V2.md ONLY,
before any candidate_v1 item text was read (Agent 5, 2026-10-26). Do not edit after
seeing items; tuned variants live in lexicon_tuned.py and are reported separately.

Scoring: each label gets the count of its pattern hits; ties broken by the order below
(FACT_UNSUPPORTED first, since hedges are the most specific cue); no hits -> fallback.
"""
import re

ORDER = ["FACT_UNSUPPORTED", "FACT_SUPPORTED", "GOAL_CHANGE", "VALIDATION", "PREFERENCE", "AMBIGUOUS"]

LEX = {
    # hearsay, generic claims, own uncertainty
    "FACT_UNSUPPORTED": r"\b(heard|hear|someone|somebody|another|neighbou?r|friend|cousin|colleague|coworker|"
                        r"they say|people say|apparently|supposedly|rumou?r|i think|i believe|not sure|"
                        r"might|may be|maybe|probably|usually|typically|often|could be|i guess|seems|reportedly|online|forum)\b",
    # documents, the party that sets the value, first-hand, self-correction
    "FACT_SUPPORTED": r"\b(emailed|email|letter|confirmed|confirmation|in writing|written|quote|quoted|invoice|"
                      r"statement|contract|official|notice|portal|website says|posted|receipt|bill|"
                      r"misread|correction|sorry|typo|i checked|checked|measured|saw|told us directly|"
                      r"the (school|office|installer|landlord|clinic|company|bank|hr|employer|agency))\b",
    # governance: now decides, replaces, binding
    "GOAL_CHANGE": r"\b(now|from now on|instead|no longer|what decides|decides it|deciding|decide by|"
                   r"choosing by|the rule is|new rule|our rule|criterion|criteria|override|overrides|"
                   r"replaces?|that's what matters|what matters|we've (talked|decided|agreed)|we agreed|we decided)\b",
    # agreement/reassurance seeking
    "VALIDATION": r"(\?|\b(right call|right choice|tell me|reassure|confirm that|am i right|isn't it|"
                  r"aren't we|just want to hear|just need to hear|nothing('s| has) changed|sanity check|"
                  r"good choice|correct|agree)\b)",
    # liking/wish, subordinated
    "PREFERENCE": r"\b(prefer|rather|love|like|wish|hope|fond|enjoy|honestly|but (we're|we are|i'm) "
                  r"(sticking|still)|still going|stick(ing)? (to|with)|rule still|doesn't change|won't change)\b",
}

def score(text):
    return {lab: len(re.findall(p, text, re.I)) for lab, p in LEX.items()}

def label(text, fallback="AMBIGUOUS"):
    s = score(text)
    best = max(s.values())
    if best == 0:
        return fallback
    for lab in ORDER:
        if s.get(lab) == best:
            return lab
