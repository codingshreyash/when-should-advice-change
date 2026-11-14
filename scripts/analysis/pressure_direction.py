"""Does pressure push toward the named option, or just shake the answer?

For models with several samples per prompt (randomized option order), per scenario:
  p_target(variant) = share of samples whose choice is the pressure target.
Pressure is directional if p_target(pressure) - p_target(base) is clearly above the same
quantity for variants that name no option (reframe, irrelevant_update). Only scenarios whose
base answer (majority over samples) is not already the target are used.

  shift   mean over scenarios of p_target(variant) - p_target(base)
  95% CI  bootstrap over scenarios (2000 resamples, seed 1684)
  margin  for generated scenarios (field 'margin', size used), shift split at tau

Usage: python3 scripts/analysis/pressure_direction.py RESULTS.jsonl --scenarios a.jsonl [b.jsonl ...] [--tau 0.15]
"""
import argparse, collections, json, random, statistics

def load_scn(paths):
    S = {}
    for p in paths:
        for l in open(p):
            if l.strip():
                r = json.loads(l); S[r["id"]] = r
    return S

def shares(rows, target):
    """sample choices -> share equal to target (None choices dropped)."""
    ch = [r["choice"] for r in rows if r["choice"] is not None]
    return (sum(c == target for c in ch) / len(ch)) if ch else None

def majority(rows):
    c = collections.Counter(r["choice"] for r in rows if r["choice"] is not None)
    return c.most_common(1)[0][0] if c else None

def boot(xs, n=2000, seed=1684):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results"); ap.add_argument("--scenarios", nargs="+", required=True)
    ap.add_argument("--tau", type=float, default=0.15)
    a = ap.parse_args()
    S = load_scn(a.scenarios)
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for l in open(a.results):
        if l.strip():
            r = json.loads(l); by[(r["model"], r["id"])][r["variant"]].append(r)
    for model in sorted({m for m, _ in by}):
        print(f"=== {model}")
        per = collections.defaultdict(list)       # variant -> [shift per scenario]
        near = collections.defaultdict(lambda: {True: [], False: []})
        n_elig = 0
        for (m, i), v in by.items():
            if m != model or i not in S or "base" not in v: continue
            t = S[i].get("pressure_target")
            if not t or majority(v["base"]) == t: continue
            b = shares(v["base"], t)
            if b is None: continue
            n_elig += 1
            mg = S[i].get("margin")
            for var in ("pressure", "reframe", "irrelevant_update", "subthreshold_update"):
                if var in v:
                    p = shares(v[var], t)
                    if p is None: continue
                    per[var].append(p - b)
                    if mg is not None: near[var][abs(mg) < a.tau].append(p - b)
        print(f"  eligible scenarios (base answer is not the named option): {n_elig}")
        for var in ("pressure", "reframe", "irrelevant_update", "subthreshold_update"):
            xs = per.get(var)
            if not xs: print(f"  {var:20s} not run"); continue
            lo, hi = boot(xs)
            print(f"  {var:20s} shift toward named option {statistics.fmean(xs):+.3f} [{lo:+.3f}, {hi:+.3f}]  n={len(xs)}")
            if near[var][True] and near[var][False]:
                print(f"  {'':20s} margin<{a.tau}: {statistics.fmean(near[var][True]):+.3f} (n={len(near[var][True])})"
                      f"   margin>={a.tau}: {statistics.fmean(near[var][False]):+.3f} (n={len(near[var][False])})")

if __name__ == "__main__":
    main()
