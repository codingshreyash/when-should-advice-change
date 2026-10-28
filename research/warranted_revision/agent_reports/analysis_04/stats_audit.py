"""Audit of the family-cluster bootstrap with few clusters (read-only).
Run from research/warranted_revision: python3 agent_reports/analysis_04/stats_audit.py

For each run and protocol comparison: per-family joint-accuracy table, families where arms
differ, exact bootstrap distribution (all G^G ordered family draws enumerated, equivalent to
infinitely many draws), the reported 2,000-draw interval (stats.paired_diff_ci), an exact
family-level sign-flip permutation p-value, and design effect / effective sample size.
"""
import gzip, itertools, json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, "src")
from warranted_revision import stats
from warranted_revision.evaluate import evaluate_arm, load_jsonl
from warranted_revision.schema import DecisionRecord, GoldCase

RES = Path("../../results/warranted_revision")
gold = {g.case_id: g for g in load_jsonl(Path("data/v0/dev_gold.jsonl"), GoldCase)}

def load(run):
    p = RES / run / "decisions.jsonl"
    txt = p.read_text() if p.exists() else gzip.open(str(p) + ".gz", "rt").read()
    return [DecisionRecord.model_validate_json(l) for l in txt.splitlines() if l.strip()]

def fam_sums(units):
    out = defaultdict(lambda: [0.0, 0.0])
    for f, n, d in units:
        out[f][0] += n; out[f][1] += d
    return out

def exact_boot(ua, ub, fams):
    fa, fb = fam_sums(ua), fam_sums(ub)
    vals = []
    for draw in itertools.product(fams, repeat=len(fams)):
        na = sum(fa[f][0] for f in draw); da = sum(fa[f][1] for f in draw)
        nb = sum(fb[f][0] for f in draw); db = sum(fb[f][1] for f in draw)
        if da and db:
            vals.append(na / da - nb / db)
    vals.sort()
    q = lambda p: stats._percentile(vals, p)
    return q(0.025), q(0.975), sum(v == 0 for v in vals) / len(vals)

def signflip(ua, ub, fams):
    fa, fb = fam_sums(ua), fam_sums(ub)
    d = [fa[f][0] / fa[f][1] - fb[f][0] / fb[f][1] for f in fams]
    obs = abs(sum(d))
    cnt = tot = 0
    for signs in itertools.product((1, -1), repeat=len(d)):
        tot += 1
        cnt += abs(sum(s * x for s, x in zip(signs, d))) >= obs - 1e-12
    return cnt / tot, d

def deff(units):
    fs = fam_sums(units)
    n = sum(d for _, _, d in units)
    p = sum(x for _, x, _ in units) / n
    if p in (0, 1):
        return None
    G = len(fs)
    # cluster-robust variance of a ratio estimator vs binomial variance
    v_cl = G / (G - 1) * sum((fs[f][0] - p * fs[f][1]) ** 2 for f in fs) / n ** 2
    v_bin = p * (1 - p) / n
    return v_cl / v_bin

for run in ["smoke-004", "format-001", "smoke-003"]:
    decs = load(run)
    arms = defaultdict(list)
    for d in decs:
        arms[d.condition].append(d)
    units = {c: evaluate_arm(v, gold, n_draws=200)["_units"] for c, v in arms.items()}
    fams = sorted({f for u in units.values() for f, _, _ in u["i"]})
    print(f"\n=== {run}: {len(fams)} families -> {len(fams)**len(fams)} ordered bootstrap draws, "
          f"min two-sided sign-flip p = {2 / 2 ** len(fams):.3f}")
    print("per-family joint accuracy (axis i / axis ii):")
    for c in sorted(units):
        fi, fii = fam_sums(units[c]["i"]), fam_sums(units[c]["ii"])
        print(f"  {c:24s} " + "  ".join(f"{f[:5]}={fi[f][0]:.0f}/{fi[f][1]:.0f},{fii[f][0]:.0f}/{fii[f][1]:.0f}" for f in fams))
        for ax in ("i", "ii"):
            de = deff(units[c][ax])
            n = sum(d for _, _, d in units[c][ax])
            if de:
                print(f"     axis {ax}: n={n:.0f}, design effect {de:.1f}, effective n {n / de:.1f}")
    pairs = [("premise_search", "best_of_n"), ("structured", "direct"), ("premise_search", "direct"),
             ("best_of_n", "direct"), ("premise_search", "structured"), ("premise_search", "premise_search_noprov"),
             ("best_of_n", "structured")]
    print("comparison | axis | diff | reported-style CI (2000 draws) | exact bootstrap CI | P(boot diff = 0) | families differing | sign-flip p")
    for a, b in pairs:
        if a not in units or b not in units:
            continue
        for ax in ("i", "ii"):
            ua, ub = units[a][ax], units[b][ax]
            diff = stats.ratio(ua) - stats.ratio(ub)
            ci = stats.paired_diff_ci(ua, ub)
            lo, hi, p0 = exact_boot(ua, ub, fams)
            p, d = signflip(ua, ub, fams)
            nd = sum(abs(x) > 1e-12 for x in d)
            print(f"  {a} - {b} | {ax} | {diff:+.2f} | [{ci[0]:.2f}, {ci[1]:.2f}] | [{lo:.2f}, {hi:.2f}] | {p0:.2f} | {nd}/{len(fams)} | {p:.3f}")
print("\nFamilies available: dev 5 (refinance, relocation, certification, car, freelance); holdout 3 (from data/v0/FREEZE.json); challenge_v1 reuses the 5 dev families.")
