"""Red-team power/precision simulation for the challenge pilot (configs/pilot_challenge.json).

Design mirrored: 5 families x 4 cases, 1 replicate; per case 1 base turn, 2 warranted-update
follow-ups (relevant_fact, changed_priority) and 6 pressure follow-ups (3 styles x 2 directions,
the 'ch' axis). Outcome = joint correctness (base correct AND follow-up correct), as in
evaluate.py. Paired comparison arm B - arm A with the repo's own family-cluster percentile
bootstrap (stats.paired_diff_ci, 2,000 draws) -- here 400 draws for speed (checked: same
decisions at 2,000 on a subset).

Generative assumptions (stated, not estimated -- no challenge-set model output exists):
- family random intercept on the logit scale, sd SIG_F (0.75 default);
- case random intercept, sd SIG_C (0.75), shared by both arms (same scenario);
- family-specific treatment effect delta_f ~ N(delta, SIG_D) on the follow-up logit
  (SIG_D 0.0 / 0.5);
- base-turn correctness shared across arms with prob RHO_BASE, else independent draws at the
  same rate (smoke-004: base differs rarely between the two 9-call arms);
- follow-up outcomes coupled across arms by a common uniform with prob RHO_FU (0.7), so
  discordance is realistic (smoke-004 BoN vs search: 2/40 discordant joint outcomes).
Run: python3 power_sim.py   (CPU, ~1-2 min)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from warranted_revision import stats  # noqa: E402

G, C = 5, 4
N_WU, N_CH = 2, 6


def expit(x):
    return 1 / (1 + np.exp(-x))


def logit(p):
    return np.log(p / (1 - p))


def sim_once(rng, p_base, p_fu, delta, sig_f=0.75, sig_c=0.75, sig_d=0.0, n_items=N_CH,
             rho_base=0.9, rho_fu=0.7):
    ua, ub = [], []
    for f in range(G):
        uf = rng.normal(0, sig_f)
        df = rng.normal(delta, sig_d)
        for c in range(C):
            vc = rng.normal(0, sig_c)
            pb = expit(logit(p_base) + uf + vc)
            u0 = rng.random()
            ba = u0 < pb
            bb = ba if rng.random() < rho_base else (rng.random() < pb)
            pa = expit(logit(p_fu) + uf + vc)
            pbb = expit(logit(p_fu) + uf + vc + df)
            for _ in range(n_items):
                u = rng.random()
                fa = u < pa
                fb = (u < pbb) if rng.random() < rho_fu else (rng.random() < pbb)
                ua.append((str(f), float(ba and fa), 1.0))
                ub.append((str(f), float(bb and fb), 1.0))
    return ua, ub


def power(delta, n_sims=300, draws=400, seed=0, **kw):
    rng = np.random.default_rng(seed)
    hits_pos = hits_neg = 0
    widths, diffs = [], []
    for s in range(n_sims):
        ua, ub = sim_once(rng, delta=delta, **kw)
        ci = stats.paired_diff_ci(ub, ua, n_draws=draws, seed=s)
        d = stats.ratio(ub) - stats.ratio(ua)
        diffs.append(d)
        if ci is None:
            continue
        widths.append(ci[1] - ci[0])
        hits_pos += ci[0] > 0
        hits_neg += ci[1] < 0
    return hits_pos / n_sims, hits_neg / n_sims, float(np.median(widths)), float(np.std(diffs))


if __name__ == "__main__":
    print("axis | p_base p_fu | delta(logit) sig_d | P(CI>0) P(CI<0) median_CI_width sd(diff)")
    for axis, n_items, p_fu in (("ch(6/case)", N_CH, 0.75), ("wu(2/case)", N_WU, 0.85)):
        for sig_d in (0.0, 0.5):
            for delta in (0.0, 0.5, 1.0, 1.5):
                pp, pn, w, sd = power(delta, n_items=n_items, p_base=0.9, p_fu=p_fu, sig_d=sig_d)
                print(f"{axis} | 0.90 {p_fu:.2f} | {delta:.1f} {sig_d:.1f} | "
                      f"{pp:.2f} {pn:.2f} {w:.3f} {sd:.3f}")
