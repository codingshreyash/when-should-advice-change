"""Build data/derived/pressure_direction.jsonl: a paired design that separates asking for an
option from merely naming it, in both directions.

For each career scenario, A is the base label (expected.base) and B is the pressure
target. Every prompt is the base prompt plus at most one appended sentence:

  base                   the base prompt unchanged
  mention_A, mention_B   the option is named with no preference (MENTION)
  request_A_p0..p5       third-person request to endorse A, six phrasings (PREF_PHRASINGS)
  request_B_p0..p5       the same six phrasings toward B

The phrasings are the ones in build_pressure_controls.py, written generically with {opt},
so the wording toward A and toward B is identical. They are third person only: the
first-person version draws refusals from Claude in this project. Nothing decision-relevant
changes, so every expected label is the base label. The deference/opposition estimate is
P(A | request_A) - P(A | mention_A) per scenario (and the same for B); see
scripts/analysis/pressure_direction.py.

Option order: run with RANDOMIZE_OPTIONS=1; prompts.ordered_scenario seeds the order on
scenario and sample only, so every prompt of a scenario shows the same order.

Skipped: scenarios whose base label is need_more_information, whose base label equals the
pressure target, or that do not have two distinct concrete options.

Usage: python3 scripts/data/build_pressure_direction.py
"""
import json, sys
sys.dont_write_bytecode = True   # importing the sibling builder should not leave __pycache__
from build_pressure_controls import MENTION, PREF_PHRASINGS, as_clause

NMI = "need_more_information"
SOURCES = ["data/scenarios/career_pilot.jsonl", "data/scenarios/career_v2.jsonl"]
OUT = "data/derived/pressure_direction.jsonl"

def skip_reason(s):
    a, b = s["expected"]["base"], s.get("pressure_target")
    concrete = [o for o in s["options"] if o != NMI]
    if a == NMI: return "base label is need_more_information"
    if b is None or b == NMI: return "pressure target is missing or need_more_information"
    if a == b: return "base label equals pressure target"
    if len(set(concrete)) < 2 or a not in concrete or b not in concrete:
        return "fewer than two distinct concrete options"
    return None

def appended(s):
    """variant -> the one sentence appended to the base prompt (None for base)."""
    a, b = s["expected"]["base"], s["pressure_target"]
    opt = {"A": as_clause(s["option_text"][a]), "B": as_clause(s["option_text"][b])}
    out = {"base": None}
    for side in "AB":
        out[f"mention_{side}"] = MENTION.format(opt=opt[side])
    for side in "AB":
        for k, p in enumerate(PREF_PHRASINGS):
            out[f"request_{side}_p{k}"] = p.format(opt=opt[side])
    return out

def build(s):
    base = s["prompts"]["base"].rstrip()
    a, b = s["expected"]["base"], s["pressure_target"]
    sentences = appended(s)
    prompts = {v: base if sent is None else f"{base} {sent}" for v, sent in sentences.items()}
    check(base, prompts, sentences, s["id"])
    return {"id": s["id"], "domain": s.get("domain", "career"),
            "options": s["options"], "option_text": s["option_text"], "question": s["question"],
            "option_A": a, "option_B": b, "pressure_target": b,
            "prompts": prompts, "expected": {v: a for v in prompts},
            "appended": {v: t for v, t in sentences.items() if t is not None},
            "notes": "Base prompt plus one appended sentence; A = base label, B = pressure target. "
                     "No fact changes, so every expected label is the base label."}

def check(base, prompts, sentences, sid):
    """Each appended sentence occurs exactly once in its prompt, never in the base, and
    removing it gives back the base prompt exactly."""
    assert len(set(prompts.values())) == len(prompts), f"{sid}: duplicate prompt texts"
    for v, sent in sentences.items():
        p = prompts[v]
        if sent is None:
            assert p == base, f"{sid}: base changed"
            continue
        assert sent not in base, f"{sid}/{v}: appended sentence already in base"
        assert p.count(sent) == 1, f"{sid}/{v}: appended sentence not found exactly once"
        assert p.replace(" " + sent, "", 1) == base, f"{sid}/{v}: differs from base beyond the sentence"

if __name__ == "__main__":
    recs, skipped = [], []
    for f in SOURCES:
        for line in open(f):
            if not line.strip(): continue
            s = json.loads(line)
            why = skip_reason(s)
            if why: skipped.append((s["id"], why))
            else: recs.append(build(s))
    with open(OUT, "w") as f:
        for r in recs: f.write(json.dumps(r) + "\n")
    for sid, why in skipped:
        print(f"skipped {sid}: {why}")
    n = sum(len(r["prompts"]) for r in recs)
    print(f"wrote {len(recs)} scenarios x {len(recs[0]['prompts'])} prompts = {n} prompts to {OUT}")
