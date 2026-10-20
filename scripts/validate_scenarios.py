"""Check scenario files against the SCHEMA.md rules that can be checked mechanically.

ERROR: breaks the format or a hard rule. WARN: likely leak or confound worth a human look.
Numbers are the one fact type we can compare automatically, so reframe must keep the
exact multiset of numbers from base, and pressure must keep all of them too.

Usage: python scripts/validate_scenarios.py data/pilot_scenarios.jsonl data/career_v2.jsonl
"""
import json, re, sys, collections

NMI = "need_more_information"
VARIANTS = ("base", "pressure", "reframe", "relevant_update", "irrelevant_update", "omission")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?%?")

def nums(text):
    return collections.Counter(n.rstrip(",") for n in NUM.findall(text))

def check(s):
    errs, warns = [], []
    opts, p, e = s["options"], s["prompts"], s["expected"]
    if NMI not in opts: errs.append("options missing need_more_information")
    if set(s["option_text"]) != set(opts): errs.append("option_text keys != options")
    # a scenario may carry a subset of variants (e.g. AITA base + pressure), but always base
    if "base" not in p or not set(p) <= set(VARIANTS): errs.append(f"prompts keys {sorted(p)}")
    if set(e) != set(p): errs.append(f"expected keys {sorted(e)} != prompts keys {sorted(p)}")
    for v, lab in e.items():
        if lab not in opts: errs.append(f"expected[{v}]={lab} not an option")
    tgt = s["pressure_target"]
    if tgt not in opts or tgt == NMI: errs.append(f"pressure_target {tgt} invalid")
    if tgt == e.get("base"): errs.append("pressure_target equals the base answer, so pressure can't be measured")
    if "omission" in p:
        if e.get("omission") != NMI: errs.append("omission expected must be need_more_information")
        if len(p["omission"]) >= len(p["base"]): warns.append("omission is not shorter than base")
    if "relevant_update" in p:
        if e.get("relevant_update") == e.get("base"): errs.append("relevant_update expected equals base expected")
        if e.get("relevant_update") == NMI: warns.append("relevant_update expected is need_more_information (confounds with omission)")
        if p["relevant_update"] == p["base"]: errs.append("relevant_update identical to base")
    if "irrelevant_update" in p:
        if e.get("irrelevant_update") != e.get("base"):
            errs.append("irrelevant_update expected must equal base expected")
        if p["irrelevant_update"] == p["base"]:
            errs.append("irrelevant_update identical to base")
        if (nums(p["irrelevant_update"]) != nums(p["base"])) != (nums(p.get("relevant_update", "")) != nums(p["base"])):
            warns.append("numeric-change cue is not matched between relevant and irrelevant updates")
    if "reframe" in p:
        if nums(p["reframe"]) != nums(p["base"]):
            errs.append(f"reframe numbers differ: base {dict(nums(p['base']))} reframe {dict(nums(p['reframe']))}")
        lb, lr = len(p["base"].split()), len(p["reframe"].split())
        if abs(lr - lb) > 0.2 * lb: warns.append(f"reframe length {lr} vs base {lb} words")
    if "pressure" in p:
        if nums(p["pressure"]) - nums(p["base"]):
            warns.append(f"pressure adds numbers {dict(nums(p['pressure']) - nums(p['base']))}")
        if not p["pressure"].startswith(p["base"]):
            warns.append("pressure is not base + appended sentence; check by hand that it adds no fact")
    return errs, warns

if __name__ == "__main__":
    n_err = 0
    for path in sys.argv[1:]:
        rows = [json.loads(l) for l in open(path) if l.strip()]
        ids = [r["id"] for r in rows]
        dup = [i for i, c in collections.Counter(ids).items() if c > 1]
        print(f"== {path}: {len(rows)} scenarios" + (f"; DUPLICATE ids {dup}" if dup else ""))
        n_err += len(dup)
        for s in rows:
            errs, warns = check(s)
            n_err += len(errs)
            for m in errs: print(f"  ERROR {s['id']}: {m}")
            for m in warns: print(f"  WARN  {s['id']}: {m}")
    print("OK" if n_err == 0 else f"{n_err} error(s)")
    sys.exit(1 if n_err else 0)
