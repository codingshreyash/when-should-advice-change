"""Per-label and per-contrast disagreement across the AI pre-calibration sources.

Run from research/warranted_revision:  python v2/ai_precalibration/analysis/disagreement.py
Sources: design labels (coordinator key), annotators A and B, the context-blind baseline,
the adjudicator's final labels, and the auditor's gold-vs-text flags. Writes
analysis/disagreement.json.
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

P = Path(__file__).resolve().parents[1]
key = json.loads((P / "coordinator/key.json").read_text())["items"]


def rows(path):
    return {r["uid"]: r for r in csv.DictReader((P / path).open(newline=""))}


A, B = rows("annotations/annotator_A/items.csv"), rows("annotations/annotator_B/items.csv")
F = rows("annotations/followup_only/items.csv")
J = rows("adjudication/final.csv")
flags = json.loads((P / "audit/gold_vs_text_flags.json").read_text())
flag_by = defaultdict(list)
for f in flags:
    flag_by[f["item_id"]].append(f)


def behav(b):
    return {"KEEP": "keep", "REVISE": "revise:" + str(b.get("action")), "HEDGE": "ask_or_conditional"}[
        b["behavior"]
    ]


per_label: dict = defaultdict(Counter)
items = []
for u, k in key.items():
    lab = k["design_label"]
    final = J[u]["final_label"] if u in J else A[u]["label"] if A[u]["label"] == B[u]["label"] else "DISPUTED"
    gold = behav(k["behavior_under_design_label"])
    c = per_label[lab]
    c["n"] += 1
    c["A_eq_B"] += A[u]["label"] == B[u]["label"]
    c["A_eq_design"] += A[u]["label"] == lab
    c["B_eq_design"] += B[u]["label"] == lab
    c["final_eq_design"] += final == lab
    c["baseline_eq_consensus"] += F[u]["label"] == A[u]["label"]
    c["advisor_A_eq_gold"] += A[u]["advisor_should"].strip() == gold
    c["advisor_B_eq_gold"] += B[u]["advisor_should"].strip() == gold
    c["auditor_flagged"] += bool(flag_by.get(k["item_id"]))
    c["auditor_flagged_behavior_at_risk"] += any(f.get("computed_behavior_at_risk") for f in flag_by.get(k["item_id"], []))
    items.append({"item_id": k["item_id"], "uid": u, "design": lab, "A": A[u]["label"], "B": B[u]["label"],
                  "baseline": F[u]["label"], "final": final, "gold_behavior": gold,
                  "A_advisor": A[u]["advisor_should"].strip(), "B_advisor": B[u]["advisor_should"].strip(),
                  "auditor_flags": [f["severity"] for f in flag_by.get(k["item_id"], [])]})

contrasts = {
    "A_vs_B": Counter(f"{i['A']}|{i['B']}" for i in items if i["A"] != i["B"]),
    "design_vs_final": Counter(f"{i['design']}|{i['final']}" for i in items if i["design"] != i["final"]),
    "consensus_vs_baseline": Counter(f"{i['A']}|{i['baseline']}" for i in items if i["A"] != i["baseline"]),
}
agree_but_flagged = [i for i in items if i["A"] == i["B"] and i["A_advisor"] == i["B_advisor"] == i["gold_behavior"]
                     and i["auditor_flags"]]
out = {"per_label": {k: dict(v) for k, v in per_label.items()}, "contrasts": {k: dict(v) for k, v in contrasts.items()},
       "agree_with_gold_but_auditor_flagged": agree_but_flagged, "items": items}
(P / "analysis/disagreement.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: out[k] for k in ("per_label", "contrasts")}, indent=1))
print("agree with each other and with gold, but flagged by auditor:",
      [(i["item_id"], i["auditor_flags"]) for i in agree_but_flagged])
