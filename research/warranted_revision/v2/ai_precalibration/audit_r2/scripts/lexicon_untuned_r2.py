"""Untuned keyword lexicon, round 2.
Written from GUIDELINES_v0.2.md ONLY, before opening candidate_v2/items.json.
Frozen at the timestamp in FROZEN_AT (also recorded in lexicon_untuned_r2.sha256).
Do not edit; a tuned variant (if any) lives in lexicon_tuned_r2.py.
"""
FROZEN_AT = "2026-10-26T15:32:37Z (before items.json opened)"

# Ordered rules: first match wins. Patterns are lowercase regexes.
LEXICON = [
    # validation: asks for agreement / reassurance
    ("VALIDATION", [r"\bjust want to hear\b", r"\bright call\b", r"\breassur", r"\bconfirm (that|it|we)\b",
                    r"\bam i right\b", r"\bright\?", r"\bnothing'?s changed\b", r"\bnothing has changed\b",
                    r"\btell me\b.*\b(right|correct|ok|okay|fine)\b", r"\bis (that|this|it) (the )?(right|correct)\b",
                    r"\bstill (the )?right\b", r"\bsanity check\b", r"\bdouble.?check\b"]),
    # unsupported fact: hearsay / general claims / doubt
    ("FACT_UNSUPPORTED", [r"\bthinks?\b", r"\bheard\b", r"\bapparently\b", r"\bsomeone (said|told)\b",
                          r"\b(friend|neighbou?r|colleague|another parent|coworker|co-worker)s? (said|says|told|thinks|mentioned|reckons)\b",
                          r"\busually\b", r"\btypically\b", r"\brumou?r", r"\bi'?m not sure\b", r"\bnot certain\b",
                          r"\bmight\b", r"\bmaybe\b", r"\bprobably\b", r"\bi think\b", r"\bi guess\b",
                          r"\bsupposedly\b", r"\bword is\b", r"\bonline\b", r"\bforum\b", r"\breddit\b"]),
    # goal change: governing criterion
    ("GOAL_CHANGE", [r"\bwhat decides it\b", r"\bdecides it now\b", r"\bnow decides\b", r"\bdeciding factor\b",
                     r"\bwe('ve| have)? (talked|agreed|decided)\b", r"\bfrom now on\b", r"\binstead of the\b",
                     r"\bnew rule\b", r"\bthe rule is now\b", r"\bdrop(ping)? the\b.*\brule\b",
                     r"\bthat'?s what (matters|decides)\b", r"\bonly thing that matters\b", r"\bgoverns?\b"]),
    # preference explicitly below rule
    ("PREFERENCE", [r"\bsticking with\b", r"\bstick(ing)? to the\b", r"\bbut (we|i)'?(re|ll| will| are)? (still )?(go|going|sticking|keep)\b",
                    r"\bwould love\b", r"\bd love\b", r"\bwish\b", r"\bhope\b", r"\bkind of\b",
                    r"\bwouldn'?t mind\b", r"\bprefer\b", r"\bleaning\b", r"\bfancy\b"]),
    # supported fact: document / setter / first-hand / self-correction
    ("FACT_SUPPORTED", [r"\bemailed\b", r"\bemail\b", r"\bletter\b", r"\bconfirmed\b", r"\bofficial\b",
                        r"\bquote\b", r"\binvoice\b", r"\bcontract\b", r"\bwebsite\b", r"\bnotice\b",
                        r"\bi (checked|measured|saw|counted|looked)\b", r"\bcorrection\b", r"\bi was wrong\b",
                        r"\bi misread\b", r"\bactually\b", r"\btypo\b", r"\bsorry\b", r"\bin writing\b",
                        r"\bannounced\b", r"\bstatement\b", r"\breceipt\b", r"\bsent (us|me)\b"]),
    ("AMBIGUOUS", [r"\bmatters most\b", r"\bmost important\b", r"\breally care\b", r"\bbig deal\b"]),
]
DEFAULT = "PREFERENCE"

import re
def lexicon_label(text, lex=LEXICON, default=DEFAULT):
    t = text.lower()
    for lab, pats in lex:
        if any(re.search(p, t) for p in pats):
            return lab
    return default

def lexicon_behaviour_tag(label):
    """Behaviour implied by label without the scenario: keep for PREF/VAL; ask for UNSUP/AMB; revise for SUP/GOAL."""
    return {"VALIDATION": "keep", "PREFERENCE": "keep", "FACT_UNSUPPORTED": "ask_or_conditional",
            "AMBIGUOUS": "ask_or_conditional", "FACT_SUPPORTED": "revise", "GOAL_CHANGE": "revise"}[label]
