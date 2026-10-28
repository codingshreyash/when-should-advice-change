"""Per-candidate (per-call) follow-up correctness by arm, call role and class; and per-leaf
pressure capitulation by parent reading (premise search). ALT diagnostics, read-only.
Run from research/warranted_revision: python3 agent_reports/analysis_04/candidates.py"""
import gzip, json
from collections import Counter, defaultdict
from pathlib import Path
RES = Path("../../results/warranted_revision")
gold = {json.loads(l)["case_id"]: json.loads(l) for l in open("data/v0/dev_gold.jsonl")}
FU = {f["followup_id"]: (g["case_id"], f) for g in gold.values() for f in g["followups"]}
def rows(run, name):
    p = RES / run / f"{name}.jsonl"
    fh = open(p) if p.exists() else gzip.open(str(p) + ".gz", "rt")
    return [json.loads(l) for l in fh if l.strip()]
for run in ["smoke-004", "format-001"]:
    print(f"\n=== {run}")
    decs = rows(run, "decisions")
    base = {(d["condition"], d["case_id"]): d["choice"] for d in decs if d["turn"] == "base"}
    trs = {(t["condition"], t["case_id"], t["followup_id"]): t for t in rows(run, "search_traces")}
    acc = defaultdict(Counter)
    cap = defaultdict(Counter)
    for r in rows(run, "predictions"):
        if r["turn"] != "followup" or r["call_role"].startswith("hypothesis"):
            continue
        cid, f = FU[r["followup_id"]]
        cls = f["contrast_class"]
        bok = base[(r["condition"], cid)] == gold[cid]["gold_base_action"]
        p = r["parsed"]
        k = acc[(r["condition"], "axis_i" if cls in ("relevant_fact", "changed_priority") else ("axis_ii" if cls in ("pressure_for_incorrect", "pressure_for_correct", "subthreshold_fact", "irrelevant_fact") else cls))]
        k["n"] += 1
        k["ok"] += p["status"] == "valid" and p["choice"] == f["gold_action"]
        k["ok_bok"] += bok and p["status"] == "valid" and p["choice"] == f["gold_action"]
        k["n_bok"] += bok
        if cls == "pressure_for_incorrect" and bok:
            reading = "-"
            if r["call_role"].startswith("decide"):
                pid = r["call_role"].split(":")[1]
                t = trs[(r["condition"], cid, r["followup_id"])]
                reading = next(n["hypothesis"] for n in t["nodes"] if n["node_id"] == pid)
            c = cap[(r["condition"], reading)]
            c["n"] += 1
            c["to_target"] += p["choice"] == f["pressure_target"]
    print("per-candidate follow-up correctness (all candidates, incl. unselected):")
    for (c, g), k in sorted(acc.items()):
        print(f"  {c:24s} {g:22s} {k['ok']}/{k['n']} = {k['ok']/k['n']:.2f}; on base-correct cases {k['ok_bok']}/{k['n_bok']}")
    print("per-candidate capitulation to pressure target on pressure_for_incorrect (base-correct cases), by parent reading:")
    for (c, rd), k in sorted(cap.items()):
        print(f"  {c:24s} {rd:26s} {k['to_target']}/{k['n']}")
