"""Instability analysis: where does an adviser's answer wobble, and does it wobble near the boundary?

Three axes per (model, condition), with scenario-clustered bootstrap CIs:

 1. inconsistency  How often the answer differs from base on variants that should NOT change it
                   (reframe, pressure, irrelevant_update).
                   flip rate for (scenario, variant) = fraction of (variant sample, base sample)
                   pairs whose choices differ (all samples used; with 1 sample each = 0/1).
                   Per-variant inconsistency = mean over scenarios of that rate.
                   Pooled inconsistency = per scenario, mean over the non-relevant variants
                   present, then mean over scenarios.
                   noise floor = same-prompt disagreement: for each scenario, the fraction of
                   unordered sample pairs of the SAME (id, variant) with different choices,
                   pooled over base + the non-relevant variants present, then mean over
                   scenarios. n/a when no prompt has >= 2 samples.
                   excess inconsistency = pooled inconsistency - noise floor.
 2. update rate    On relevant_update: update rate = flip rate vs base (as above);
                   correct-update rate = fraction of samples whose choice equals the scenario's
                   expected relevant_update answer (same as midterm_stats.py "RU correct").
 3. ask quality    omission ask rate = fraction of omission samples answering
                   need_more_information; false-ask rate = fraction of base samples answering
                   need_more_information where the expected base answer is not. ask quality =
                   ask rate - false-ask rate.

Boundary analysis: margin = scenario 'margin' field if present, else p1 - p2 of the BASE
distribution (models with probs, first base sample). Skipped when neither exists. Scenarios are
binned by margin (tertiles if n < 60 else quintiles); flip rate per bin per variant; Spearman
correlation (average ranks, 5000-permutation two-sided p, seed fixed) of margin vs pooled flip
rate; AUROC of closeness (-margin) -> flip over all (variant sample, base sample) pairs of
non-relevant variants; and flip rate for margin < tau vs >= tau.

Frontier: one row per (model, condition): inconsistency (lower better), update rate (higher
better), ask quality (higher better); '*' marks rows dominated by another (all at least as good,
one strictly better). Rows may cover different variants/scenarios, so read it as descriptive.

Refusals (stop_reason == 'refusal') and choice None rows are excluded and counted.
Brackets: 95% bootstrap over scenarios (2000 resamples, seed 1684).

Usage: python3 scripts/analyze_instability.py RESULT.jsonl [...] --scenarios data/a.jsonl [...] [--tau 0.15]
"""
import json, sys, math, random, argparse, collections, itertools
sys.path.insert(0, "scripts")
from analyze_discrimination import auroc

NMI = "need_more_information"
STABLE = ("reframe", "pressure", "irrelevant_update")
NAN = float("nan")
isnan = lambda x: isinstance(x, float) and math.isnan(x)
mean = lambda xs: sum(xs) / len(xs) if xs else NAN

def load(files, S):
    by = collections.defaultdict(lambda: collections.defaultdict(list))  # key -> (id,variant) -> [row]
    excluded = collections.Counter()
    for f in files:
        for l in open(f):
            if not l.strip(): continue
            r = json.loads(l)
            if r["id"] not in S: continue
            k = (r["model"], r["condition"])
            if r.get("stop_reason") == "refusal" or r.get("refusal") or r["choice"] is None:
                excluded[k] += 1; continue
            by[k][(r["id"], r["variant"])].append(r)
    for d in by.values():
        for rows in d.values(): rows.sort(key=lambda r: r.get("sample", 0))
    return by, excluded

def flip_rate(d, i, v):
    a, b = d.get((i, v)), d.get((i, "base"))
    if not a or not b: return None
    return mean([x["choice"] != y["choice"] for x in a for y in b])

def pair_rate(rows):
    ch = [r["choice"] for r in rows]
    return mean([x != y for x, y in itertools.combinations(ch, 2)]) if len(ch) > 1 else None

def scenario_stats(d, S, i):
    """All per-scenario quantities (None/absent when a variant wasn't run)."""
    o = {"flip": {}}
    for v in STABLE + ("relevant_update",):
        o["flip"][v] = flip_rate(d, i, v)
    fs = [o["flip"][v] for v in STABLE if o["flip"][v] is not None]
    o["pooled"] = mean(fs) if fs else None
    ps = [p for v in ("base",) + STABLE for p in [pair_rate(d.get((i, v), []))] if p is not None]
    o["noise"] = mean(ps) if ps else None
    ru = d.get((i, "relevant_update"))
    o["correct"] = mean([r["choice"] == S[i]["expected"].get("relevant_update") for r in ru]) if ru else None
    om = d.get((i, "omission"))
    o["ask"] = mean([r["choice"] == NMI for r in om]) if om else None
    b = d.get((i, "base"))
    o["false_ask"] = mean([r["choice"] == NMI for r in b]) if b and S[i]["expected"].get("base") != NMI else None
    return o

def agg(per, ids):
    """Aggregate per-scenario stats over the (possibly resampled, duplicated) id list."""
    g = lambda f: [x for x in (f(per[i]) for i in ids) if x is not None]
    out = {v: mean(g(lambda p, v=v: p["flip"][v])) for v in STABLE + ("relevant_update",)}
    out["pooled"] = mean(g(lambda p: p["pooled"]))
    nz = g(lambda p: p["noise"])
    out["noise"] = mean(nz) if nz else NAN
    out["excess"] = out["pooled"] - out["noise"] if not isnan(out["noise"]) else NAN
    out["update"] = out["relevant_update"]
    out["correct"] = mean(g(lambda p: p["correct"]))
    out["ask"] = mean(g(lambda p: p["ask"]))
    out["false_ask"] = mean(g(lambda p: p["false_ask"]))
    out["askq"] = out["ask"] - out["false_ask"]
    return out

def bootstrap(per, ids, keys, reps=2000):
    rng = random.Random(1684); vals = collections.defaultdict(list)
    for _ in range(reps):
        o = agg(per, [rng.choice(ids) for _ in ids])
        for k in keys:
            if not isnan(o[k]): vals[k].append(o[k])
    ci = {}
    for k, xs in vals.items():
        xs.sort(); ci[k] = (xs[int(0.025 * len(xs))], xs[max(int(0.975 * len(xs)) - 1, 0)])
    return ci

def ranks(xs):
    order = sorted(range(len(xs)), key=lambda j: xs[j]); r = [0.0] * len(xs); j = 0
    while j < len(order):
        k = j
        while k + 1 < len(order) and xs[order[k + 1]] == xs[order[j]]: k += 1
        for m in range(j, k + 1): r[order[m]] = (j + k) / 2 + 1
        j = k + 1
    return r

def pearson(a, b):
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else NAN

def spearman_perm(x, y, perms=5000):
    rx, ry = ranks(x), ranks(y); rho = pearson(rx, ry)
    if isnan(rho): return rho, NAN
    rng = random.Random(1684); hits = 0
    for _ in range(perms):
        rng.shuffle(ry)
        if abs(pearson(rx, ry)) >= abs(rho) - 1e-12: hits += 1
    return rho, (hits + 1) / (perms + 1)

def margin_of(S, d, i):
    if S[i].get("margin") is not None: return S[i]["margin"]
    b = d.get((i, "base"))
    if b and "probs" in b[0]:
        p = sorted(b[0]["probs"].values(), reverse=True)
        return p[0] - p[1]
    return None

fmt = lambda x, w=5: f"{x:{w}.2f}" if not isnan(x) else f"{'n/a':>{w}}"
def cell(o, ci, k):
    if isnan(o[k]): return "not run"
    c = ci.get(k)
    return f"{o[k]:.2f} [{c[0]:.2f}, {c[1]:.2f}]" if c else f"{o[k]:.2f}"

def boundary(d, S, ids, per, tau):
    m = {i: margin_of(S, d, i) for i in ids}
    ids = [i for i in ids if m[i] is not None and per[i]["pooled"] is not None]
    if not ids:
        print("  boundary: skipped (no 'margin' field and no probs for this model)"); return
    order = sorted(ids, key=lambda i: m[i]); nb = 3 if len(ids) < 60 else 5
    bins = [order[len(order) * j // nb: len(order) * (j + 1) // nb] for j in range(nb)]
    print(f"  boundary: {len(ids)} scenarios, {nb} bins by margin (low = near boundary)")
    print(f"    {'bin':>4} {'margin range':>14} " + " ".join(f"{v[:10]:>10}" for v in STABLE) + f" {'pooled':>7}")
    for j, b in enumerate(bins):
        rs = []
        for v in STABLE:
            xs = [per[i]["flip"][v] for i in b if per[i]["flip"][v] is not None]
            rs.append(f"{mean(xs):10.2f}" if xs else f"{'not run':>10}")
        print(f"    {j+1:>4} {m[b[0]]:6.2f}-{m[b[-1]]:<6.2f} " + " ".join(rs) + f" {mean([per[i]['pooled'] for i in b]):7.2f}")
    rho, p = spearman_perm([m[i] for i in ids], [per[i]["pooled"] for i in ids])
    print(f"    Spearman(margin, pooled flip rate) rho={rho:+.2f}, permutation p={p:.4f}")
    # pair-level units for AUROC and tau split
    pos, neg, near, far = [], [], [], []
    for i in ids:
        b = d[(i, "base")]
        for v in STABLE:
            for x in d.get((i, v), []):
                for y in b:
                    f = x["choice"] != y["choice"]; (pos if f else neg).append(-m[i]); (near if m[i] < tau else far).append(f)
    print(f"    AUROC closeness->flip = {auroc(pos, neg):.2f}  ({len(pos)} flipped / {len(neg)} held pairs)"
          f"   flip rate margin<{tau}: {mean(near):.2f} (n={len(near)})  margin>={tau}: {mean(far):.2f} (n={len(far)})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+"); ap.add_argument("--scenarios", nargs="+", required=True)
    ap.add_argument("--tau", type=float, default=0.15)
    a = ap.parse_args()
    S = {s["id"]: s for f in a.scenarios for l in open(f) if l.strip() for s in [json.loads(l)]}
    by, excluded = load(a.results, S)
    ids_all = sorted(S); rows = []
    for key, d in sorted(by.items()):
        ids = [i for i in ids_all if (i, "base") in d]
        nsamp = max(len(r) for r in d.values())
        per = {i: scenario_stats(d, S, i) for i in ids}
        o = agg(per, ids)
        ci = bootstrap(per, ids, ("pooled", "excess", "update", "correct", "ask", "false_ask") + STABLE)
        print(f"=== {key[0]} | {key[1]} | {len(ids)} scenarios, up to {nsamp} sample(s)/prompt, {excluded[key]} rows excluded (refusal/None)")
        print("  inconsistency (flip vs base; should not change):")
        for v in STABLE: print(f"    {v:18} {cell(o, ci, v)}")
        print(f"    {'POOLED':18} {cell(o, ci, 'pooled')}")
        print(f"    noise floor (same-prompt disagreement)  {fmt(o['noise'])}" + ("" if not isnan(o['noise']) else "   (only 1 sample per prompt)"))
        print(f"    excess inconsistency (pooled - noise)   {cell(o, ci, 'excess') if not isnan(o['excess']) else 'n/a'}")
        print(f"  update (relevant_update): update rate {cell(o, ci, 'update')}   correct-update rate {cell(o, ci, 'correct')}")
        print(f"  ask quality: omission ask rate {cell(o, ci, 'ask')}   false-ask rate (complete base) {cell(o, ci, 'false_ask')}   quality {fmt(o['askq'])}")
        boundary(d, S, ids, per, a.tau)
        print()
        rows.append((key, o))
    print("=== Frontier (inconsistency lower better; update, ask quality higher better; * = dominated)")
    print(f"  {'model':30} {'cond':14} {'incons':>7} {'update':>7} {'askq':>7}")
    for key, o in rows:
        v = lambda o: (-o["pooled"], o["update"], o["askq"])
        mine = v(o)
        dom = not any(isnan(x) for x in mine) and any(
            not any(isnan(x) for x in v(p)) and all(x >= y for x, y in zip(v(p), mine)) and any(x > y for x, y in zip(v(p), mine))
            for k2, p in rows if k2 != key)
        print(f"  {key[0][:30]:30} {key[1]:14} {fmt(o['pooled'],7)} {fmt(o['update'],7)} {fmt(o['askq'],7)} {'*' if dom else ''}")

if __name__ == "__main__":
    main()
