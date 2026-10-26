"""TUNED lexicon, round 2: written AFTER reading candidate_v2 items. In-sample upper bound only;
it is not an audit result. Shows how much of the authoring style a short phrase list captures."""
import re
FROZEN_AT = "written after items were read (2026-10-26, ~16:00Z)"
LEXICON = [
    ("AMBIGUOUS", [r"matters more", r"cares about most", r"biggest thing", r"we'd love", r"i'd really like",
                   r"\bi trust him\b", r"\bnow thinks\b"]),
    ("PREFERENCE", [r"isn't (her|his) call", r"it's (our decision|still my call)", r"don't weigh", r"put that aside",
                    r"is how i'm deciding", r"going by the cost rule", r"go by the \$8,000 test, so",
                    r"sticking with", r"what should i tell him"]),
    ("VALIDATION", [r"to hear", r"tell me", r"can you (just )?confirm"]),
    ("FACT_UNSUPPORTED", [r"\bthinks\b", r"\bheard\b", r"told (me|her)", r"\bsays\b", r"may have been"]),
    ("GOAL_CHANGE", [r"\bagreed\b", r"settled on", r"made up our minds", r"changing my test", r"deciding differently",
                     r"my test from here", r"from here on"]),
    ("FACT_SUPPORTED", [r"emailed", r"written quote", r"\bposted\b", r"\bsent\b", r"called to correct", r"measured"]),
]
DEFAULT = "AMBIGUOUS"
def lexicon_label(text, lex=LEXICON, default=DEFAULT):
    t = text.lower()
    for lab, pats in lex:
        if any(re.search(p, t) for p in pats):
            return lab
    return default
