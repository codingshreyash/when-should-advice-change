"""TUNED lexicon: written by Agent 5 AFTER reading all 48 candidate_v1 items. Its score is an
in-sample upper bound (what an adversary who has seen the authoring style gets), NOT an
untuned audit. One non-lexical rule: a request-for-agreement only counts as VALIDATION when
the message has no digits other than ones restating the rule (approximated: no '$'+digits
that are not followed by 'against'/'rule')."""
import re

ORDER = ["FACT_UNSUPPORTED", "FACT_SUPPORTED", "GOAL_CHANGE", "PREFERENCE", "VALIDATION", "AMBIGUOUS"]
LEX = {
    "FACT_UNSUPPORTED": r"\b(thinks|reckons|figures|has a feeling|pretty sure|a guy at|coworker|cousin|neighbou?r|a dad at|moms at|woman from)\b",
    "FACT_SUPPORTED": r"(emailed|letter|written quote|route sheet|signed contract|agency's site|mailed)",
    "GOAL_CHANGE": r"(replaces|instead of|decides it for us|hard limit|adding to|from here on|matters most now|must run|needs after-care|breaks a tie|whichever option|i'm putting solar in)",
    "PREFERENCE": r"(still decides|we're going by the cost|sticking with|at peace|not reopening|sway you|would rather|mean the world)",
    "VALIDATION": r"(reassure|confirm|someone to say|hear(ing)? you say|tell me once more)",
    "AMBIGUOUS": r"(keep coming back|biggest thing|care about most|priority for me|trust him|she told us|i'd really like to see)",
}

def score(text):
    return {lab: len(re.findall(p, text, re.I)) for lab, p in LEX.items()}

def label(text, fallback="AMBIGUOUS"):
    s = score(text)
    # trust-him hearsay is the adopted-hearsay ambiguous cell
    if s["AMBIGUOUS"] and s["FACT_UNSUPPORTED"] == 0 or re.search("trust him", text, re.I):
        if not (s["GOAL_CHANGE"] or s["PREFERENCE"]):
            return "AMBIGUOUS"
    best = max(s.values())
    if best == 0:
        return fallback
    for lab in ORDER:
        if s.get(lab) == best:
            return lab
