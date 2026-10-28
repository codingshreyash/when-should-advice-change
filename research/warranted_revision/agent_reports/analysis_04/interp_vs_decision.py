"""Does a matching interpretation predict a correct decision? And do search decide calls keep
their parent's assigned reading? ALT diagnostics, read-only.
Run from research/warranted_revision: python3 agent_reports/analysis_04/interp_vs_decision.py"""
import gzip, json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, "src")
from warranted_revision.trace_audit import TRUE_READING
TRUE = {k.value: v for k, v in TRUE_READING.items()}
RES = Path("../../results/warranted_revision")
gold = {json.loads(l)["case_id"]: json.loads(l) for l in open("data/v0/dev_gold.jsonl")}
FU = {f["followup_id"]: (g["case_id"], f) for g in gold.values() for f in g["followups"]}
def rows(run, name):
    p = RES / run / f"{name}.jsonl"
    fh = open(p) if p.exists() else gzip.open(str(p) + ".gz", "rt")
    return [json.loads(l) for l in fh if l.strip()]
for run in ["smoke-004", "format-001"]:
    trs = {(t["condition"], t["case_id"], t["followup_id"]): t for t in rows(run, "search_traces")}
    tab = defaultdict(Counter)
    echo = Counter()
    for r in rows(run, "predictions"):
        if r["turn"] != "followup" or r["call_role"].startswith("hypothesis") or r["condition"] == "direct":
            continue
        led = r["parsed"]["ledger"]
        if not led or r["parsed"]["status"] != "valid":
            continue
        cid, f = FU[r["followup_id"]]
        m = led["interpretation"] == TRUE[f["contrast_class"]]
        ok = r["parsed"]["choice"] == f["gold_action"]
        k = tab[(r["condition"], "match" if m else "mismatch")]
        k["n"] += 1; k["ok"] += ok
        if r["call_role"].startswith("decide"):
            pid = r["call_role"].split(":")[1]
            t = trs[(r["condition"], cid, r["followup_id"])]
            ph = next(n["hypothesis"] for n in t["nodes"] if n["node_id"] == pid)
            echo[(r["condition"], "parent_true" if ph == TRUE[f["contrast_class"]] else "parent_wrong", "kept_parent" if led["interpretation"] == ph else ("switched_to_true" if m else "switched_other"))] += 1
    print(f"=== {run}: per-candidate decision accuracy by interpretation match (valid candidates with ledger)")
    for k, v in sorted(tab.items()):
        print(f"  {k[0]:24s} {k[1]:9s} {v['ok']}/{v['n']} = {v['ok']/v['n']:.2f}")
    print("  search decide calls vs parent reading:")
    for k, v in sorted(echo.items()):
        print(f"    {k}: {v}")
