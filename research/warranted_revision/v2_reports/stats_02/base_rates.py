"""Base rates for the scaffold probe from saved Qwen3.5-9B dev runs (read-only).

Per run x condition x contrast class: follow-up turns, valid, switched away from the arm's own
base answer, moved to the pressure target / mentioned option. Also per-sample switching for the
T=0.7 best-of-N candidates (relative to the arm's selected base answer) and base-turn
dispersion across T=0.7 samples. Reads only results/warranted_revision/{smoke-003,smoke-004,
format-001} and data/v0/dev_gold.jsonl. Run from the repo root:
    python3 research/warranted_revision/v2_reports/stats_02/base_rates.py
"""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RES = ROOT / "results" / "warranted_revision"
GOLD = ROOT / "research" / "warranted_revision" / "data" / "v0" / "dev_gold.jsonl"


def jl(path: Path):
    op = gzip.open if path.suffix == ".gz" else open
    with op(path, "rt") as fh:
        for ln in fh:
            if ln.strip():
                yield json.loads(ln)


def first(run: Path, name: str) -> Path:
    for p in (run / name, run / (name + ".gz")):
        if p.exists():
            return p
    raise FileNotFoundError(run / name)


gold = {g["case_id"]: g for g in jl(GOLD)}
fu_info = {
    (cid, f["followup_id"]): f for cid, g in gold.items() for f in g["followups"]
}

for run_id in ("smoke-003", "smoke-004", "format-001"):
    run = RES / run_id
    decs = list(jl(first(run, "decisions.jsonl")))
    base = {(d["condition"], d["case_id"], d["replicate"]): d for d in decs if d["turn"] == "base"}
    tab = defaultdict(Counter)
    for d in decs:
        if d["turn"] != "followup":
            continue
        f = fu_info[(d["case_id"], d["followup_id"])]
        b = base[(d["condition"], d["case_id"], d["replicate"])]
        k = (d["condition"], f["contrast_class"])
        t = tab[k]
        t["n"] += 1
        both_valid = d["status"] == "valid" and b["status"] == "valid"
        t["valid"] += d["status"] == "valid"
        t["both_valid"] += both_valid
        if both_valid:
            t["switch"] += d["choice"] != b["choice"]
            tgt = f.get("pressure_target") or f.get("mentioned_option")
            if tgt and tgt != b["choice"]:
                t["tgt_den"] += 1
                t["to_tgt"] += d["choice"] == tgt
            t["base_ok_switch_den"] += b["choice"] == gold[d["case_id"]]["gold_base_action"]
            t["base_ok_switch"] += (
                b["choice"] == gold[d["case_id"]]["gold_base_action"] and d["choice"] != b["choice"]
            )
    print(f"\n=== {run_id}: decisions, by condition x class "
          "(n, valid, switched-from-own-base / both-valid, to-target / target!=base)")
    for (cond, cls), t in sorted(tab.items()):
        print(f"{cond:28s} {cls:24s} n={t['n']:2d} valid={t['valid']:2d} "
              f"switch={t['switch']}/{t['both_valid']} to_tgt={t['to_tgt']}/{t['tgt_den']}")
    # T=0.7 samples: per-candidate behaviour (best_of_n only; one decision per call)
    try:
        preds = list(jl(first(run, "predictions.jsonl")))
    except FileNotFoundError:
        continue
    samp_base = defaultdict(list)
    samp_fu = defaultdict(Counter)
    for p in preds:
        if p["condition"] != "best_of_n":
            continue
        par = p["parsed"]
        if par.get("kind") != "decision":
            continue
        if p["turn"] == "base":
            samp_base[p["case_id"]].append(par["choice"] if par["status"] == "valid" else None)
    for p in preds:
        if p["condition"] != "best_of_n" or p["turn"] != "followup":
            continue
        par = p["parsed"]
        if par.get("kind") != "decision":
            continue
        b = base.get(("best_of_n", p["case_id"], p["replicate"]))
        f = fu_info[(p["case_id"], p["followup_id"])]
        c = samp_fu[f["contrast_class"]]
        c["n"] += 1
        if par["status"] == "valid" and b and b["status"] == "valid":
            c["v"] += 1
            c["sw"] += par["choice"] != b["choice"]
    print(f"--- {run_id}: best_of_n T=0.7 base-turn samples per case (choice counts)")
    for cid, xs in sorted(samp_base.items()):
        cnt = Counter(xs)
        print(f"   {cid:24s} {dict(cnt)}  modal share={max(cnt.values())}/{len(xs)}")
    print(f"--- {run_id}: best_of_n T=0.7 follow-up samples, switched from selected base")
    for cls, c in sorted(samp_fu.items()):
        print(f"   {cls:24s} sw={c['sw']}/{c['v']} (calls {c['n']})")
