"""Arm B scenarios from the AI-labeled items (docs/real_world_check.md).

Keeps items where labelers A and B gave identical acceptable sets of size 1 (decisive items; the own-error runner needs
exactly one acceptable answer). The label is that code. Items with two acceptable options (close calls) are listed but
not run. Each kept item is written REPS times with ids "<id>__r0".."__r<REPS-1>": the option order is hashed from the id,
so each copy shows a different order, and each copy gets an independent turn-1 sample. The copies are NOT independent
items: analysis must resample by the original id (scripts/analysis/armb_own_error.py does).
Usage: python3 scripts/data/build_armb_scenarios.py [--reps 5]   (writes data/scenarios/realworld/armb.jsonl)
"""
import argparse, csv, glob, json

def read(p):
    return {r["id"]: frozenset(x.strip() for x in r["acceptable"].split("|") if x.strip()) for r in csv.DictReader(open(p, newline=""))}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--out", default="data/scenarios/realworld/armb.jsonl"); a = ap.parse_args()
    A, B = read("data/labeling/armb/ai_labels_A.csv"), read("data/labeling/armb/ai_labels_B.csv")
    items = {}
    for f in sorted(glob.glob("data/labeling/armb/*_items.jsonl")):
        for l in open(f):
            if l.strip(): s = json.loads(l); items[s["id"]] = s
    keep = [i for i in sorted(items) if A[i] == B[i] and len(A[i]) == 1]
    out = []
    for i in keep:
        (code,) = A[i]; s = items[i]
        for r in range(a.reps):
            out.append({"id": f"{i}__r{r}", "domain": s["domain"], "options": s["options"], "option_text": s["option_text"],
                        "question": s["question"], "prompts": {"base": s["prompts"]["base"]},
                        "acceptable": {"base": [code]}, "expected": {"base": code}, "margin": None, "margin_bin": "none"})
    with open(a.out, "w") as f:
        for s in out: f.write(json.dumps(s) + "\n")
    agreed = [i for i in items if A[i] == B[i]]
    print(f"agreed {len(agreed)}, of these decisive (one option) {len(keep)}, two-option close calls not run {len(agreed)-len(keep)}; "
          f"wrote {len(out)} rows ({a.reps} copies each) to {a.out}")
    import collections
    print("expected code kinds:", dict(collections.Counter("need_more_information" if list(A[i])[0] == "need_more_information" else "concrete option" for i in keep)))
main()
