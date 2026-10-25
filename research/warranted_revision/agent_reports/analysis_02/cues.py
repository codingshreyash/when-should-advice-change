"""Lexical/template cues, change magnitudes, shortcut-policy scores (dev + challenge only)."""
import json, re
from collections import Counter, defaultdict
from pathlib import Path
root = Path(__file__).resolve().parents[2]
def load(p): return [json.loads(l) for l in open(root/p)]
sets = {"v0dev": ("data/v0/dev_inputs.jsonl", "data/v0/dev_gold.jsonl"),
        "chal1": ("data/challenge_v1/challenge_inputs.jsonl", "data/challenge_v1/challenge_gold.jsonl")}
for name, (vi, gi) in sets.items():
    vis = load(vi); gold = {g["case_id"]: g for g in load(gi)}
    pref = defaultdict(Counter); mags = defaultdict(list); texts = Counter()
    shortcut = Counter(); n = Counter(); base_counts = Counter(); prio = Counter()
    for v in vis:
        g = gold[v["case_id"]]; base_counts[g["gold_base_action"]] += 1; prio[(g["family_id"], g["priority_id"])] += 1
        byid = {f["followup_id"]: f for f in g["followups"]}
        for f in v["followups"]:
            gf = byid[f["followup_id"]]; c = gf["contrast_class"]
            p = " ".join(f["text"].split()[:3]); pref[p][c] += 1
            texts[re.sub(r"\$?[\d,.]+", "#", f["text"])] += 1
            if gf.get("new_value") is not None and gf.get("old_value"):
                mags[c].append(gf["new_value"] / gf["old_value"])
            # template-only policy: flip on "Something has changed"/"Update:", NMI on "Correction:", else stay
            other = next(o["code"] for o in v["options"][:2] if o["code"] != g["gold_base_action"])
            t = f["text"]
            act = other if t.startswith(("Something has changed", "Update:")) else ("need_more_information" if t.startswith("Correction:") else g["gold_base_action"])
            n[c] += 1; shortcut[c] += act == gf["gold_action"]
    print(f"===== {name}: {len(vis)} cases; base actions {dict(base_counts)}")
    print("priorities:", dict(prio))
    for p, c in sorted(pref.items()): print(f"  prefix {p!r:35s} -> {dict(c)}")
    print("  distinct follow-up texts after masking numbers:", len(texts), "of", sum(texts.values()))
    for c, m in mags.items():
        d = sorted(abs(x - 1) for x in m)
        print(f"  {c}: |rel change| min={d[0]:.2f} median={d[len(d)//2]:.2f} max={d[-1]:.2f} n={len(d)}")
    print("  template-only policy accuracy (given correct base):", {c: f"{shortcut[c]}/{n[c]}" for c in n})
