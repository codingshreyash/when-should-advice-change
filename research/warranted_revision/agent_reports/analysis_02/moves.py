"""Per-class movement of real-model decisions (dev only)."""
import json, sys
from collections import defaultdict, Counter
from pathlib import Path
from warranted_revision.schema import GoldCase
root = Path(__file__).resolve().parents[2]
gold = {}
for p in [root/"data/v0/dev_gold.jsonl", root/"data/challenge_v1/challenge_gold.jsonl"]:
    for ln in p.read_text().splitlines():
        g = GoldCase.model_validate_json(ln); gold[g.case_id] = g
for run in sys.argv[1:]:
    rows = [json.loads(l) for l in open(root/f"../../results/warranted_revision/{run}/decisions.jsonl")]
    base = {(r["system"], r["condition"], r["case_id"], r["replicate"]): r for r in rows if r["turn"] == "base"}
    tab = defaultdict(Counter)
    print(f"== {run}: {len(rows)} turns, cases {sorted({r['case_id'] for r in rows})}")
    for r in rows:
        if r["turn"] != "followup": continue
        g = gold[r["case_id"]]; gf = next(f for f in g.followups if f.followup_id == r["followup_id"])
        b = base[(r["system"], r["condition"], r["case_id"], r["replicate"])]
        bok = b["choice"] == g.gold_base_action
        key = (r["condition"], gf.contrast_class.value)
        tab[key]["n"] += 1
        tab[key]["base_ok"] += bok
        tab[key]["moved"] += r["choice"] != b["choice"]
        tab[key]["fu_ok"] += r["choice"] == gf.gold_action
        tab[key]["to_target"] += gf.pressure_target is not None and r["choice"] == gf.pressure_target and b["choice"] != gf.pressure_target
        tab[key]["nmi"] += r["choice"] == "need_more_information"
    for k in sorted(tab):
        c = tab[k]; print(f"{k[0]:28s} {k[1]:24s} n={c['n']:2d} base_ok={c['base_ok']:2d} moved={c['moved']:2d} fu_ok={c['fu_ok']:2d} nmi={c['nmi']}")
