"""Round-2 comparison: annotators vs context-blind baseline vs computed gold vs auditor.

Run from research/warranted_revision:
    python v2/ai_precalibration/round2/analysis/compare.py
Writes round2/analysis/compare.json and round2/analysis/human_review_ids.json.

The human-review selection rule is fixed here, before the auditor's findings were read:
  difficult = adjudicated items + auditor high/medium flags + items any AI judge wrote an
              alternative advisor action for (capped at 16, highest severity first, then id);
  controls  = 10 items drawn at random (seed 20261026) from the rest, stratified by label.
"""

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

R = Path(__file__).resolve().parents[1]
P = R.parent
key = json.loads((R / "coordinator/key.json").read_text())["items"]
items = json.loads((P / "candidate_v2/items.json").read_text())
text = {it["item_id"]: it["followup"] for f in items["families"] for it in f["items"]}


def rows(path):
    return {r["uid"]: r for r in csv.DictReader((R / path).open(newline=""))}


A, B = rows("annotations/annotator_A/items.csv"), rows("annotations/annotator_B/items.csv")
F = rows("annotations/followup_only/items.csv")
J = rows("adjudication/final.csv")
flag_path = P / "audit_r2/gold_vs_text_flags.json"
flags = json.loads(flag_path.read_text()) if flag_path.exists() else []
flags_by = defaultdict(list)
for f in flags:
    flags_by[f["item_id"]].append(f)


def gold(u):
    b = key[u]["behavior_under_design_label"]
    return {"KEEP": "keep", "REVISE": "revise:" + str(b.get("action")), "HEDGE": "ask_or_conditional"}[b["behavior"]]


def cls(s):
    return s.split(":")[0]


out_items = []
for u, k in key.items():
    iid = k["item_id"]
    rec = {
        "item_id": iid,
        "uid": u,
        "design": k["design_label"],
        "gold": gold(u),
        "A": [A[u]["label"], A[u]["advisor_should"].strip()],
        "B": [B[u]["label"], B[u]["advisor_should"].strip()],
        "baseline": [F[u]["label"], F[u]["advisor_should_guess"].strip()],
        "adjudicated": [J[u]["final_label"], J[u]["final_advisor_should"]] if u in J else None,
        "auditor_flags": [{"severity": f.get("severity"), "problem": f.get("problem"),
                           "alternative": f.get("careful_reader_alternative")} for f in flags_by.get(iid, [])],
        "A_notes": A[u]["computation_notes"], "B_notes": B[u]["computation_notes"],
        "A_alt": A[u]["alternative_readings"], "B_alt": B[u]["alternative_readings"],
    }
    rec["annotators_agree_with_gold"] = rec["A"][1] == rec["B"][1] == rec["gold"]
    rec["shared_error_candidate"] = rec["annotators_agree_with_gold"] and any(
        f["severity"] in ("high", "medium") for f in rec["auditor_flags"]
    )
    out_items.append(rec)

# paired strings
by_text = defaultdict(list)
for r in out_items:
    by_text[text[r["item_id"]]].append(r)
pairs = [rs for rs in by_text.values() if len(rs) > 1]
pair_summary = [
    {
        "items": [r["item_id"] for r in rs],
        "labels": [r["design"] for r in rs],
        "gold": [r["gold"] for r in rs],
        "annotators_right_on_both": all(r["A"][1] == r["gold"] and r["B"][1] == r["gold"] for r in rs),
        "baseline_class_right_on_both": all(cls(r["baseline"][1]) == cls(r["gold"]) for r in rs),
        "auditor_flagged": [r["item_id"] for r in rs if r["auditor_flags"]],
    }
    for rs in pairs
]

summary = {
    "n": len(out_items),
    "A_label_eq_design": sum(r["A"][0] == r["design"] for r in out_items),
    "B_label_eq_design": sum(r["B"][0] == r["design"] for r in out_items),
    "A_advisor_eq_gold": sum(r["A"][1] == r["gold"] for r in out_items),
    "B_advisor_eq_gold": sum(r["B"][1] == r["gold"] for r in out_items),
    "baseline_label_eq_design": sum(r["baseline"][0] == r["design"] for r in out_items),
    "baseline_class_eq_gold": sum(cls(r["baseline"][1]) == cls(r["gold"]) for r in out_items),
    "best_constant_class": max(Counter(cls(r["gold"]) for r in out_items).values()),
    "auditor_flagged_items": sum(bool(r["auditor_flags"]) for r in out_items),
    "auditor_high_medium": sum(any(f["severity"] in ("high", "medium") for f in r["auditor_flags"]) for r in out_items),
    "shared_error_candidates": [r["item_id"] for r in out_items if r["shared_error_candidate"]],
    "pairs": len(pairs),
    "pairs_annotators_right_on_both": sum(p["annotators_right_on_both"] for p in pair_summary),
    "pairs_baseline_right_on_both": sum(p["baseline_class_right_on_both"] for p in pair_summary),
}

# human review selection (rule in the docstring)
sev_rank = {"high": 0, "medium": 1}
difficult = []
for r in out_items:
    sev = min([sev_rank.get(f["severity"], 9) for f in r["auditor_flags"]] or [9])
    if r["adjudicated"] or sev < 9:
        difficult.append((0 if r["adjudicated"] and sev == 0 else sev if sev < 9 else 2, r["item_id"]))
difficult = [i for _, i in sorted(difficult)][:16]
rest = [r for r in out_items if r["item_id"] not in difficult]
rng = random.Random(20261026)
by_label = defaultdict(list)
for r in rest:
    by_label[r["design"]].append(r["item_id"])
controls = []
labels = sorted(by_label)
while len(controls) < 10 and any(by_label.values()):
    for lab in labels:
        if by_label[lab] and len(controls) < 10:
            controls.append(by_label[lab].pop(rng.randrange(len(by_label[lab]))))
(R / "analysis/human_review_ids.json").write_text(json.dumps({"difficult": difficult, "controls": controls}, indent=2) + "\n")
(R / "analysis/compare.json").write_text(json.dumps({"summary": summary, "pairs": pair_summary, "items": out_items}, indent=2) + "\n")
print(json.dumps(summary, indent=1))
