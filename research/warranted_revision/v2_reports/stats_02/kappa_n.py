"""Inter-annotator agreement sample sizes for a 6-way label with an 'ambiguous' option.

Simulated two-rater data. Categories: goal_change, preference, validation_request,
unsupported_assertion, supported_fact_change, ambiguous. True prevalences 0.18 x 5 + 0.10.
Each rater gives the true label with prob ACC; otherwise errs, half of the time into a
designated 'neighbour' confusion (goal<->preference, validation<->preference,
unsupported<->supported, any->ambiguous) and half uniformly. Items are clustered in families
(m items per family) with a family-level difficulty shift on ACC (sd 0.08), so the
family-cluster bootstrap matters. Reported: overall Cohen kappa, Krippendorff alpha (nominal),
per-category one-vs-rest kappa for the hardest category, and the sd of each over simulations
(=> 95% half-width ~ 1.96 sd). Also: binomial detection probability for a systematic
confusion pattern in a calibration round of n items.
Run: python3 kappa_n.py  (~1 min)
"""
from __future__ import annotations

import numpy as np

RNG = np.random.default_rng(7)
K = 6
PREV = np.array([0.18] * 5 + [0.10])
NEIGH = {0: 1, 1: 0, 2: 1, 3: 4, 4: 3, 5: 5}


def raters(n, acc, m=8):
    G = int(np.ceil(n / m))
    fam = np.repeat(np.arange(G), m)[:n]
    acc_f = np.clip(acc + RNG.normal(0, 0.08, G), 0.3, 0.995)[fam]
    true = RNG.choice(K, n, p=PREV)
    out = []
    for _ in range(2):
        ok = RNG.random(n) < acc_f
        neigh = np.array([NEIGH[t] for t in true])
        neigh = np.where(RNG.random(n) < 0.3, 5, neigh)  # some errors go to 'ambiguous'
        unif = RNG.integers(0, K, n)
        err = np.where(RNG.random(n) < 0.5, neigh, unif)
        out.append(np.where(ok, true, err))
    return true, out[0], out[1], fam


def cohen(a, b, k=K):
    po = (a == b).mean()
    pa = np.bincount(a, minlength=k) / len(a)
    pb = np.bincount(b, minlength=k) / len(b)
    pe = (pa * pb).sum()
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def kripp_nominal(a, b, k=K):
    n = len(a)
    o = np.zeros((k, k))
    np.add.at(o, (a, b), 1)
    np.add.at(o, (b, a), 1)
    nc = o.sum(1)
    N = 2 * n
    do = (o.sum() - np.trace(o)) / N
    de = (N * N - (nc**2).sum()) / (N * (N - 1))
    return 1 - do / de


def per_cat(a, b, c):
    return cohen((a == c).astype(int), (b == c).astype(int), 2)


if __name__ == "__main__":
    print("ACC  n   | kappa mean (sd, ~95% hw) | alpha mean | per-cat kappa 'preference' mean (hw)"
          " | kappa excl. any-ambiguous (mean)")
    for acc in (0.80, 0.90):
        for n in (40, 80, 120, 160, 240, 320, 480):
            ks, als, pcs, kx = [], [], [], []
            for _ in range(600):
                _, a, b, _ = raters(n, acc)
                ks.append(cohen(a, b))
                als.append(kripp_nominal(a, b))
                pcs.append(per_cat(a, b, 1))
                keep = (a != 5) & (b != 5)
                kx.append(cohen(a[keep], b[keep], 5) if keep.sum() > 5 else np.nan)
            ks, pcs = np.array(ks), np.array(pcs)
            print(f"{acc:.2f} {n:3d} | {ks.mean():.3f} ({ks.std():.3f}, {1.96*ks.std():.3f}) |"
                  f" {np.mean(als):.3f}     | {pcs.mean():.3f} ({1.96*pcs.std():.3f})"
                  f"                     | {np.nanmean(kx):.3f}")
    print("\nCalibration round: P(a confusion affecting a fraction f of items appears >= 2 times)")
    for n in (24, 36, 48, 60):
        row = []
        for f in (0.05, 0.10, 0.15):
            p = 1 - (1 - f) ** n - n * f * (1 - f) ** (n - 1)
            row.append(f"f={f:.2f}: {p:.2f}")
        print(f"  n={n:2d}  " + "  ".join(row))
