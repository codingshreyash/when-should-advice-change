"""Sizing facts for the pressure-scaffold probe, from saved outputs only (read-only).

    python3 research/warranted_revision/v2_reports/offline_04/measurement.py [--results DIR]

Direct-arm completion-token distribution, finish reasons, strict validity, seconds/call,
answer-change rates by class (vs the arm's own base), base-answer agreement across arms,
and option-order bookkeeping.
"""

from __future__ import annotations

import argparse
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import common as C


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=C.RESULTS)
    args = ap.parse_args()
    g = C.gold()
    fidx = C.followup_index(g)
    for run in C.RUNS:
        rd = args.results / run
        man = __import__("json").loads((rd / "manifest.json").read_text())
        P = list(C.jsonl(rd / "predictions.jsonl"))
        D = list(C.jsonl(rd / "decisions.jsonl"))
        print(f"\n######## {run}  conditions={man['conditions']}  decoding.max_new_tokens_direct="
              f"{man['decoding']['max_new_tokens_direct']}  load_seconds="
              f"{next(iter(man['systems'].values()))['load_seconds']}")
        # tokens / latency per condition and turn
        for cond in man["conditions"]:
            for turn in ("base", "followup"):
                x = [p for p in P if p["condition"] == cond and p["turn"] == turn]
                if not x:
                    continue
                ct = [p["completion"]["completion_tokens"] for p in x]
                pt = [p["completion"]["prompt_tokens"] for p in x]
                lat = [p["completion"]["latency_s"] for p in x]
                fin = Counter(p["completion"]["finish_reason"] for p in x)
                stt = Counter(p["parsed"]["status"] for p in x if p["call_role"] not in ("hypothesis",))
                print(f"  {cond:22s} {turn:8s} calls={len(x):4d} completion tok min/med/p90/max="
                      f"{min(ct)}/{st.median(ct):.0f}/{q(ct, .9)}/{max(ct)} prompt tok "
                      f"{min(pt)}-{max(pt)} finish={dict(fin)} status={dict(stt)} "
                      f"s/call mean={st.mean(lat):.2f} med={st.median(lat):.2f} "
                      f"sum={sum(lat):.0f}s tok/s={sum(ct) / sum(lat):.1f}")
        # change vs own base, by class (decisions)
        base = {(d["condition"], d["case_id"]): d for d in D if d["turn"] == "base"}
        print("  changed-from-own-base on follow-ups [any change / valid->valid change]:")
        for cond in man["conditions"]:
            cnt = defaultdict(lambda: [0, 0, 0])
            for d in D:
                if d["condition"] != cond or d["turn"] != "followup":
                    continue
                b = base[(cond, d["case_id"])]
                cls = fidx[d["followup_id"]][1]["contrast_class"]
                ch = d["choice"] != b["choice"]
                cnt[cls][0] += 1
                cnt[cls][1] += ch
                cnt[cls][2] += ch and d["status"] == "valid" and b["status"] == "valid"
            print(f"    {cond}: " + ", ".join(f"{k} {v[1]}/{v[0]}" + (f" [vv {v[2]}]" if v[2] != v[1] else "")
                                           for k, v in sorted(cnt.items())))
        # base agreement + option order
        print("  base answers (gold | order | per arm):")
        for cid in man["case_ids"]:
            orders = {tuple(base[(c, cid)]["option_order"]) for c in man["conditions"]}
            gb = g[cid]["gold_base_action"]
            o = next(iter(orders))
            print(f"    {cid}: gold={gb} pos={o.index(gb)} orders={len(orders)} {list(o)} | "
                  + ", ".join(f"{c}={base[(c, cid)]['choice']}({base[(c, cid)]['status'][0]})"
                              for c in man["conditions"]))
        n_orders = Counter(len({tuple(d["option_order"]) for d in D if d["case_id"] == cid})
                           for cid in man["case_ids"])
        print(f"  distinct option orders per case: {dict(n_orders)}; replicates={man['replicates']}; "
              f"option_order recorded on every prediction: "
              f"{all(isinstance(p.get('option_order'), list) for p in P)}")


if __name__ == "__main__":
    main()
