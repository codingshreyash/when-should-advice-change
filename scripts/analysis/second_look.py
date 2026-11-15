"""Analyse run_second_look.py output: does asking the model to look again help or hurt?

Usage: python3 scripts/analysis/second_look.py RESULT.jsonl [...] [--scenarios FILE]
Per model, separately for DECISIVE (1 acceptable answer) and CLOSE-CALL (3) scenarios:
  revision rate, net accuracy change (after - before, 95% bootstrap CI over scenarios),
  transitions (decisive only), relevant-update accuracy, and by-margin-bin tables.
before = turn-1 choice in acceptable[base]. after = turn-2 choice in acceptable[base]
(relevant: acceptable[relevant_update]). repeat: the independent 2nd sample vs acceptable[base].
Pairs where either choice is None (no parseable code, incl. refusals) are excluded and counted.
"""
import argparse, collections, json, random

BR = ("look_again", "nudge", "irrelevant", "relevant", "repeat")

def boot(vals, B=2000, seed=1684):
    if not vals: return None
    rng = random.Random(seed); n = len(vals)
    ms = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return sum(vals) / n, ms[int(.025 * B)], ms[int(.975 * B) - 1]

def fmt_ci(v):
    return "   n/a" if v is None else f"{v[0]:+.3f} [{v[1]:+.3f},{v[2]:+.3f}]"

def pairs(rows, truth):
    """-> {branch: list of dict(id, bin, grp, t1, t2, before, after)} and exclusion counts."""
    t1 = {r["id"]: r for r in rows if r["branch"] == "turn1"}
    out, excl = collections.defaultdict(list), collections.Counter()
    for r in rows:
        if r["branch"] == "turn1" or r["id"] not in truth or r["id"] not in t1: continue
        s, b = truth[r["id"]], r["branch"]
        c1, c2 = t1[r["id"]]["choice"], r["choice"]
        if c1 is None or c2 is None:
            excl[b] += 1
            if r["stop_reason"] == "refusal" or t1[r["id"]]["stop_reason"] == "refusal": excl[b + ":refusal"] += 1
            continue
        tgt = s["acceptable"].get("relevant_update") if b == "relevant" else s["acceptable"]["base"]
        if tgt is None: continue
        out[b].append({"id": r["id"], "bin": s["margin_bin"],
                       "grp": "decisive" if len(s["acceptable"]["base"]) == 1 else "close",
                       "c1": c1, "c2": c2, "before": c1 in s["acceptable"]["base"], "after": c2 in tgt})
    return out, excl

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scenarios", default="data/scenarios/procedural/procedural_v0.jsonl")
    a = ap.parse_args()
    truth = {}
    for l in open(a.scenarios):
        if l.strip(): s = json.loads(l); truth[s["id"]] = s
    by_model = collections.defaultdict(list)
    for f in a.files:
        for l in open(f):
            if l.strip(): r = json.loads(l); by_model[r["model"]].append(r)
    for model, rows in sorted(by_model.items()):
        P, excl = pairs(rows, truth)
        print("=" * 78 + f"\nMODEL {model}: {len({r['id'] for r in rows})} scenarios, {len(rows)} rows")
        print("Excluded pairs (None choice; of which refusal):",
              {b: f"{excl[b]} ({excl[b + ':refusal']})" for b in BR if excl[b]} or "none")
        for grp in ("decisive", "close"):
            print(f"\n--- {grp.upper()} scenarios ---")
            print(f"{'branch':11} {'n':>4} {'revise':>7} {'before':>7} {'after':>7}  net accuracy change [95% CI]")
            for b in BR:
                p = [x for x in P[b] if x["grp"] == grp]
                if not p: continue
                n = len(p)
                print(f"{b:11} {n:4d} {sum(x['c1'] != x['c2'] for x in p) / n:7.3f} "
                      f"{sum(x['before'] for x in p) / n:7.3f} {sum(x['after'] for x in p) / n:7.3f}  "
                      f"{fmt_ci(boot([x['after'] - x['before'] for x in p]))}")
        print("\n--- TRANSITIONS (decisive only; before->after) ---")
        print(f"{'branch':11} {'R->R':>5} {'R->W':>5} {'W->R':>5} {'W->W':>5}")
        for b in BR:
            p = [x for x in P[b] if x["grp"] == "decisive"]
            if not p: continue
            c = collections.Counter((x["before"], x["after"]) for x in p)
            print(f"{b:11} {c[(True, True)]:5d} {c[(True, False)]:5d} {c[(False, True)]:5d} {c[(False, False)]:5d}")
        print("\n--- RELEVANT UPDATE (among scenarios right at turn 1) ---")
        for grp in ("decisive", "close"):
            p = [x for x in P["relevant"] if x["grp"] == grp and x["before"]]
            if p:
                ok = sum(x["after"] for x in p)
                kept = sum(x["c1"] == x["c2"] for x in p)
                print(f"{grp:9} n={len(p):3d} update accuracy={ok / len(p):.3f}  "
                      f"failure to update={(len(p) - ok) / len(p):.3f}  (kept turn-1 answer: {kept / len(p):.3f})")
        print("\n--- BY MARGIN BIN (all scenarios; revision rate / net accuracy change) ---")
        bins = sorted({x["bin"] for b in P for x in P[b]})
        print(f"{'bin':>3} | " + " | ".join(f"{b:^28}" for b in ("look_again", "nudge")))
        for k in bins:
            cells = []
            for b in ("look_again", "nudge"):
                p = [x for x in P[b] if x["bin"] == k]
                cells.append(f"n={len(p):3d} rev={sum(x['c1'] != x['c2'] for x in p) / len(p):.2f} "
                             f"net={sum(x['after'] - x['before'] for x in p) / len(p):+.2f}" if p else " " * 28)
            print(f"{k:3d} | " + " | ".join(f"{c:28}" for c in cells))

if __name__ == "__main__":
    main()
