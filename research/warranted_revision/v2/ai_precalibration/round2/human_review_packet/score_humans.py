"""Score returned human reviews against the computed gold and the round-2 AI judgements.

Run from research/warranted_revision after both reviewers return their files:
    python v2/ai_precalibration/round2/human_review_packet/score_humans.py \
        --a <reviewer A items.csv> --b <reviewer B items.csv> --out <dir>

Human and AI numbers are reported in separate columns and are never pooled. Also run
`python -m warranted_revision.v2bench agree --key .../coordinator/key.json --a ... --b ... --out ...`
for the agreement statistics and the blind-first adjudication files.
"""

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R2 = HERE.parent


def norm(b):
    return {"KEEP": "keep", "REVISE": "revise:" + str(b.get("action")), "HEDGE": "ask_or_conditional"}[b["behavior"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    key = json.loads((HERE / "coordinator/key.json").read_text())["items"]
    sel = json.loads((R2 / "analysis/human_review_ids.json").read_text())
    shared = {"eld-08", "cc-06", "hp-05", "eb-10", "sol-07", "sol-01", "cc-03", "eb-05"}
    # AI judgements by item id (round-2 packet uids differ from this packet's uids)
    r2key = json.loads((R2 / "coordinator/key.json").read_text())["items"]
    ai = {}
    for who in ("annotator_A", "annotator_B"):
        for r in csv.DictReader((R2 / f"annotations/{who}/items.csv").open()):
            ai.setdefault(r2key[r["uid"]]["item_id"], {})[who] = (r["label"], r["advisor_should"].strip())
    H = {n: {r["uid"]: r for r in csv.DictReader(p.open())} for n, p in (("human_A", args.a), ("human_B", args.b))}
    rows = []
    for u, k in key.items():
        iid = k["item_id"]
        rows.append({
            "item_id": iid,
            "set": "difficult" if iid in sel["difficult"] else "control",
            "shared_error_candidate": iid in shared,
            "design_label": k["design_label"],
            "gold": norm(k["behavior_under_design_label"]),
            **{f"{n}_label": H[n][u]["label"] for n in H},
            **{f"{n}_advisor": H[n][u]["advisor_should"].strip() for n in H},
            "ai_A": ai[iid]["annotator_A"], "ai_B": ai[iid]["annotator_B"],
        })
    def rate(rs, f):
        return f"{sum(f(r) for r in rs)}/{len(rs)}"
    ctrl = [r for r in rows if r["set"] == "control"]
    shr = [r for r in rows if r["shared_error_candidate"]]
    summary = {
        "controls_both_humans_match_gold": rate(ctrl, lambda r: r["human_A_advisor"] == r["human_B_advisor"] == r["gold"]),
        "controls_any_human_disagrees_with_gold": rate(ctrl, lambda r: r["gold"] not in (r["human_A_advisor"],) or r["gold"] != r["human_B_advisor"]),
        "shared_candidates_both_humans_match_gold": rate(shr, lambda r: r["human_A_advisor"] == r["human_B_advisor"] == r["gold"]),
        "decision_rule": "README: >2 of 10 controls off gold -> revise item writing; humans side with auditor on most shared candidates -> rewrite boundary principles",
        "note": "Human results only. AI agreement is shown per item for comparison, never pooled.",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "human_vs_gold.json").write_text(json.dumps({"summary": summary, "items": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
