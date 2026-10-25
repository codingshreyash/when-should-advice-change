"""Re-label dev + challenge items under two defensible alternative readings of the stated priorities.
(a) 'only if' read as a necessary (not sufficient) condition: a positive-action gold is then not entailed.
(b) certification 'pays for itself' computed on out-of-pocket cost (course_cost - min(budget, cost))."""
import json
from collections import Counter
from pathlib import Path
from warranted_revision.families import FAMILIES
root = Path(__file__).resolve().parents[2]
NECESSARY = {("refinance","payback"),("refinance","cushion"),("relocation","purchasing_power"),("relocation","near_family"),
             ("certification","no_out_of_pocket"),("freelance","annual_income"),("freelance","income_security"),
             ("certification","payback"),("car","total_cost")}
STRONG = NECESSARY - {("car","total_cost"),("certification","payback")}
def net_pay(f): return f["raise_per_year"]*f["years_in_field"] - (f["course_cost"]-min(f["training_budget"], f["course_cost"]))
for name, gp in [("v0dev","data/v0/dev_gold.jsonl"),("chal1","data/challenge_v1/challenge_gold.jsonl")]:
    a = Counter(); b = []; tot = Counter()
    for ln in open(root/gp):
        g = json.loads(ln); fam = FAMILIES[g["family_id"]]; facts = {x["name"]: x["value"] for x in g["facts"]}
        def check(label, pid, gold_action, fx, fid):
            pri = fam.priority(pid); tot[label] += 1
            if (fam.id, pid) in STRONG and gold_action == pri.positive_action: a[label] += 1
            if fam.id == "certification" and pid == "payback":
                alt = "enroll" if net_pay(fx) > 0 else "skip_course"
                if alt != gold_action: b.append((g["case_id"], label, fid, gold_action, alt))
        check("base", g["priority_id"], g["gold_base_action"], facts, None)
        for f in g["followups"]:
            c = f["contrast_class"]
            fx = dict(facts)
            if f.get("changed_fact") and f.get("new_value") is not None: fx[f["changed_fact"]] = f["new_value"]
            if c == "missing_information": continue
            check(c, f["priority_after"], f["gold_action"], fx, f["followup_id"])
    print(f"== {name}: items whose positive-action gold relies on reading 'only if' as 'iff' (strong necessary-condition priorities)")
    for k in tot: print(f"   {k:34s} {a[k]:2d}/{tot[k]}")
    print("   certification net-cost reading disagrees with gold:")
    for x in b: print("     ", x)
