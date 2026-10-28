"""Benchmark v2 sample-size calculations (CPU only, simulated; no model data used).

(a) Half-width of a per-label accuracy CI under family clustering (analytic, t_{G-1}).
(b) Power to detect a 10-pp paired between-condition difference, family-clustered, with an
    exact/MC sign-flip permutation test on family-mean differences (and a paired t-test on
    family means), plus the null false-positive rate of each test and of the repo's own
    percentile family bootstrap at small G.

Generative assumptions (stated, not estimated):
  baseline accuracy p0 = 0.75; family logit sd SIG_F = 0.75; item logit sd SIG_I = 0.75;
  condition effect delta_f ~ N(delta, SIG_D) on the logit, delta calibrated so the marginal
  difference is ~10 pp; outcomes of the two conditions on the same item are coupled through a
  common uniform with prob RHO = 0.7 (as in redteam_05/power_sim.py).
Run: python3 bench_power.py   (~1-3 min)
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats as st

RNG = np.random.default_rng(20261025)
P0, SIG_F, SIG_I, RHO = 0.75, 0.75, 0.75, 0.7


def expit(x):
    return 1 / (1 + np.exp(-x))


def logit(p):
    return math.log(p / (1 - p))


# ---------------------------------------------------------------- (a) accuracy half-widths
def halfwidth(p, G, m, icc, conf=0.95):
    de = 1 + (m - 1) * icc
    n = G * m
    t = st.t.ppf(1 - (1 - conf) / 2, G - 1)
    return t * math.sqrt(p * (1 - p) * de / n)


def families_for(p, m, icc, target, conf=0.95):
    for G in range(3, 2000):
        if halfwidth(p, G, m, icc, conf) <= target:
            return G
    return None


# ---------------------------------------------------------------- (b) paired power
def calibrate_delta(target=0.10, n=400_000):
    u = RNG.normal(0, SIG_F, n) + RNG.normal(0, SIG_I, n) + logit(P0)
    lo, hi = 0.0, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        diff = expit(u + mid).mean() - expit(u).mean()
        lo, hi = (mid, hi) if diff < target else (lo, mid)
    return (lo + hi) / 2


def sim_family_diffs(G, m, delta, sig_d, n_sims):
    uf = RNG.normal(0, SIG_F, (n_sims, G, 1))
    vi = RNG.normal(0, SIG_I, (n_sims, G, m))
    df = RNG.normal(delta, sig_d, (n_sims, G, 1))
    pa = expit(logit(P0) + uf + vi)
    pb = expit(logit(P0) + uf + vi + df)
    u = RNG.random((n_sims, G, m))
    ya = u < pa
    coupled = RNG.random((n_sims, G, m)) < RHO
    yb = np.where(coupled, u < pb, RNG.random((n_sims, G, m)) < pb)
    return (yb.astype(float) - ya.astype(float)).mean(axis=2), ya, yb  # (n_sims, G)


def signflip_p(d, n_flip=2000):
    """Two-sided sign-flip p for mean(d) per row; exact when G <= 14."""
    n_sims, G = d.shape
    obs = np.abs(d.mean(1))
    if G <= 14:
        signs = np.array(list(itertools.product([-1, 1], repeat=G)), dtype=float)
    else:
        signs = RNG.choice([-1.0, 1.0], size=(n_flip, G))
    null = np.abs(d @ signs.T / G)  # (n_sims, n_signs)
    return ((null >= obs[:, None] - 1e-12).sum(1)) / signs.shape[0]


def ttest_p(d):
    m = d.mean(1)
    s = d.std(1, ddof=1)
    G = d.shape[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = m / (s / math.sqrt(G))
    p = 2 * st.t.sf(np.abs(t), G - 1)
    return np.where(s == 0, np.where(m == 0, 1.0, 0.0), p)


def pct_boot_reject(ya, yb, n_boot=400):
    """Repo-style percentile family bootstrap of pooled difference; reject if CI excludes 0."""
    n_sims, G, m = ya.shape
    rej = 0
    for s in range(n_sims):
        da = ya[s].mean(1)
        db = yb[s].mean(1)
        idx = RNG.integers(0, G, (n_boot, G))
        diffs = db[idx].mean(1) - da[idx].mean(1)
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        rej += (lo > 0) or (hi < 0)
    return rej / n_sims


if __name__ == "__main__":
    print("(a) per-label accuracy: families G needed for a 95% CI half-width (t_{G-1})")
    print("  p    icc  m(items/family/label) | G for +-0.10 | G for +-0.075 | G for +-0.05")
    for p in (0.8, 0.5):
        for icc in (0.1, 0.2, 0.3):
            for m in (2, 4, 8):
                g = [families_for(p, m, icc, t) for t in (0.10, 0.075, 0.05)]
                print(f"  {p:.1f}  {icc:.1f}  {m:2d}                    | {g[0]:4d} ({g[0]*m:4d} items)"
                      f" | {g[1]:4d} ({g[1]*m:4d}) | {g[2]:4d} ({g[2]*m:4d})")
    print("  floor as m->inf: G >= (1.96^2 * icc * p(1-p)) / hw^2, e.g. p=.8, icc=.2, hw=.05 ->",
          math.ceil(1.96**2 * 0.2 * 0.16 / 0.05**2))

    delta = calibrate_delta(0.10)
    print(f"\n(b) paired 10-pp difference: calibrated logit delta = {delta:.3f}")
    print("  G  m  sig_d | power signflip  power t(fam)  | null FPR signflip  t(fam)  pct-boot")
    for sig_d in (0.0, 0.5):
        for G in (5, 8, 12, 16, 20, 30, 40):
            for m in (6, 12, 24):
                if G == 5 and m != 12:
                    continue
                n = 400
                d1, _, _ = sim_family_diffs(G, m, delta, sig_d, n)
                d0, ya0, yb0 = sim_family_diffs(G, m, 0.0, sig_d, n)
                pw_sf = (signflip_p(d1) < 0.05).mean()
                pw_t = (ttest_p(d1) < 0.05).mean()
                f_sf = (signflip_p(d0) < 0.05).mean()
                f_t = (ttest_p(d0) < 0.05).mean()
                f_b = pct_boot_reject(ya0[:200], yb0[:200]) if G <= 12 and m == 12 else float("nan")
                print(f"  {G:2d} {m:2d}  {sig_d:.1f}  |   {pw_sf:.2f}           {pw_t:.2f}        |"
                      f"   {f_sf:.3f}            {f_t:.3f}   {f_b:.3f}")
