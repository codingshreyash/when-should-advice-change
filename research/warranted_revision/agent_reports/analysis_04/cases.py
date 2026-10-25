"""List turn-level events used for the representative-case table (read-only on results/).
Run from research/warranted_revision: python3 agent_reports/analysis_04/cases.py"""
import gzip, json
from collections import Counter
from pathlib import Path
RES = Path("../../results/warranted_revision")
gold = {json.loads(l)["case_id"]: json.loads(l) for l in open("data/v0/dev_gold.jsonl")}
FU = {f["followup_id"]: (g["case_id"], f) for g in gold.values() for f in g["followups"]}
def rows(run, name):
    p = RES / run / f"{name}.jsonl"
    fh = open(p) if p.exists() else gzip.open(str(p) + ".gz", "rt")
    return [json.loads(l) for l in fh if l.strip()]
def vote(ch):
    if not ch: return None
    c = Counter(ch); t = max(c.values()); return next(x for x in ch if c[x] == t)
for run in ["smoke-003", "smoke-004", "format-001"]:
    print(f"\n=== {run}")
    decs = rows(run, "decisions")
    by = {(d["condition"], d["case_id"], d["followup_id"]): d for d in decs}
    conds = sorted({d["condition"] for d in decs})
    for (c, cid, fid), d in sorted(by.items(), key=lambda kv: str(kv[0])):
        if fid is None: continue
        f = FU[fid][1]
        res = {cc: (by[(cc, cid, fid)]["choice"]) for cc in conds if (cc, cid, fid) in by}
        if c == conds[0] and len(set(r == f["gold_action"] for r in res.values())) > 1:
            print(f"DISCORDANT {cid} {fid} {f['contrast_class']} gold={f['gold_action']} " + " ".join(f"{k}={v}" for k, v in res.items()))
    for tr in rows(run, "search_traces"):
        leaves = sorted((n for n in tr["nodes"] if n["hypothesis"] is None), key=lambda n: n["call_index"])
        valid = [n for n in leaves if n["status"] == "valid" and n["choice"]]
        ch = next((n for n in tr["nodes"] if n["node_id"] == tr["selected_node_id"]), None)
        v = vote([n["choice"] for n in valid])
        if ch and ch["choice"] != v:
            fid = tr["followup_id"]
            want = gold[tr["case_id"]]["gold_base_action"] if fid is None else FU[fid][1]["gold_action"]
            cls = "base" if fid is None else FU[fid][1]["contrast_class"]
            print(f"SEL!=VOTE {tr['condition']} {tr['case_id']} {fid} {cls} gold={want} selected={ch['choice']} (score {ch['score']}) vote={v} leaves=" +
                  ",".join(f"{n['choice']}:{n['score']:.2f}" for n in leaves) +
                  " beam=" + ",".join(f"{n['hypothesis']}:{n['score']:.1f}{'*' if n['kept'] else ''}" for n in tr["nodes"] if n["hypothesis"]))
