"""Staged pressure-scaffold probe: call counts, cost envelope, zero-event bounds, power.

Everything here is arithmetic or simulation; no model is called. Cell codes:
  A = options list re-attached to the follow-up message (1) or not (0)
  B = DECISION-format instruction attached to the follow-up message (1) or not (0)
  C = decision elicited in the same turn (0) or in a separate turn after a free reply (1)
  S0 = A1B1C0 (current runner)   S1 = A0B1C0
  S3 = A0B0C1 (bare pressure, free reply, then decision turn)
  S4 = A1B0C1   S5 = A1B1C1   S6 = A0B1C1
  (A0B0C0 / A1B0C0 produce no parseable decision and are not run.)
Run: python3 probe_plan.py
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as st

RATE = 1.06 / 3600  # $ per GPU-second (L40S)
SETUP = 0.53
S_FAST, S_PLAN, SLACK = 2.0, 3.9, 1.15
CALLS_PER_CELL = {"S0": 1, "S1": 1, "S3": 2, "S4": 2, "S5": 2, "S6": 2}


def cost(n_calls, sec):
    return n_calls * sec * RATE


def envelope(name, n, setup=True):
    s = SETUP if setup else 0.0
    lo, mid, mx = cost(n, S_FAST) + s, cost(n, S_PLAN) + s, cost(n, S_PLAN) * SLACK + s
    print(f"{name:34s} calls={n:5d}  optimistic ${lo:.2f}  planning ${mid:.2f}  max ${mx:.2f}")
    return mx


def stage1():
    conv = 10 * 2  # 10 cases (2/family) x 2 option orders
    items = 5  # away-insist, away-emotional, pushback, neutral-other, toward-insist
    base = conv
    repro = 10
    greedy = conv * items * (CALLS_PER_CELL["S0"] + CALLS_PER_CELL["S3"])
    repeat = conv * 2 * 2 * 2  # 2 items (away-insist, neutral) x 2 extra rounds x 2 calls (S3)
    sampled = conv * 3 * 2 * 4  # 3 items x 2 cells x k=4
    return {"base": base, "repro": repro, "greedy_followups": greedy, "repeat_rounds": repeat,
            "sampled_k4": sampled}


def stage2():
    fresh, old = 20, 20  # conversations
    items = 3  # away-insist, away-emotional, neutral-other
    all6 = sum(CALLS_PER_CELL.values())  # 10
    new4 = sum(CALLS_PER_CELL[c] for c in ("S1", "S4", "S5", "S6"))  # 7
    return {
        "base_fresh": fresh,
        "base_rerun_old": old,
        "fresh_all6": fresh * items * all6,
        "old_new4": old * items * new4,
        "repeat_S0_all": (fresh + old) * 2 * 2 * 1,
        "repeat_S3_fresh": fresh * 2 * 2 * 2,
    }


def stage2b():
    # k=2 sampled final decisions, away-insist + neutral, cells S1, S4, S5, 40 conversations
    return {"sampled_k2_S1_S4_S5": 40 * 2 * 3 * 2}


def stage2p():
    """Branch (b): latent deference only in samples. Old 20 conversations, 3 items, sampled
    final decision k=3 (free reply greedy). Per item: S1 3, S4 1+3, S5 1+3, S6 1+3 calls."""
    return {"base_rerun_old": 20, "sampled_new4": 20 * 3 * (3 + 4 + 4 + 4)}


def reduced2():
    """After the confirm branch: S1 and S5 only, all 40 conversations, 3 items."""
    return {"base_rerun": 40, "S1_S5": 40 * 3 * (1 + 2)}


def confirm_branch():
    conv = 20
    return {"base": conv, "greedy_S0_S3": conv * 5 * 3, "sampled_k4": conv * 3 * 2 * 4}


def cp_upper(k, n, conf=0.95):
    return 1.0 if k >= n else st.beta.ppf(conf, k + 1, n - k)


# ------------------------------------------------------------------ power by simulation
RNG = np.random.default_rng(5)


def expit(x):
    return 1 / (1 + np.exp(-x))


def sim_power(n_cases, turns, mu_away, mu_neut=0.01, sd_case=1.5, n_sims=2000, alpha=0.05,
              signflip=True):
    """Case-level paired test of away-switch rate vs neutral-switch rate.

    Each case has a latent logit propensity ~ N(logit(mu), sd_case) (strong clustering).
    `turns` away turns and turns/2 neutral turns per case. Test: one-sided exact sign-flip on
    per-case differences (enumerated when n_cases <= 14), plus a simple count rule.
    """
    la = math.log(mu_away / (1 - mu_away))
    ln = math.log(mu_neut / (1 - mu_neut))
    z = RNG.normal(0, sd_case, (n_sims, n_cases))
    pa = expit(la + z)
    pn = expit(ln + 0.5 * z)
    ya = RNG.binomial(turns, pa) / turns
    yn = RNG.binomial(max(turns // 2, 1), pn) / max(turns // 2, 1)
    d = ya - yn
    obs = d.mean(1)
    if n_cases <= 14:
        import itertools

        signs = np.array(list(itertools.product([-1, 1], repeat=n_cases)), dtype=float)
    else:
        signs = RNG.choice([-1.0, 1.0], (4000, n_cases))
    null = d @ signs.T / n_cases
    p = (null >= obs[:, None] - 1e-12).mean(1)
    events = RNG.binomial(turns, pa).sum(1)  # independent redraw for count rule check
    return (p < alpha).mean(), float(np.mean(ya.mean(1)))


def sim_count_rule(n_cases, turns, mu, sd_case=1.5, thr=4, min_cases=3, n_sims=20000):
    la = math.log(mu / (1 - mu))
    p = expit(la + RNG.normal(0, sd_case, (n_sims, n_cases)))
    y = RNG.binomial(turns, p)
    return ((y.sum(1) >= thr) & ((y > 0).sum(1) >= min_cases)).mean(), float(p.mean())


def sim_contrast_power(n_cases, turns, mu0, delta_logit, sd_case=1.5, n_sims=2000):
    """Between-cell factor contrast (paired within case), difference of away-switch rates;
    two-sided sign-flip over cases. Returns power and the implied marginal pp difference."""
    l0 = math.log(mu0 / (1 - mu0))
    z = RNG.normal(0, sd_case, (n_sims, n_cases))
    p0, p1 = expit(l0 + z), expit(l0 + z + delta_logit)
    y0 = RNG.binomial(turns, p0) / turns
    y1 = RNG.binomial(turns, p1) / turns
    d = y1 - y0
    signs = RNG.choice([-1.0, 1.0], (4000, n_cases))
    null = np.abs(d @ signs.T / n_cases)
    p = (null >= np.abs(d.mean(1))[:, None] - 1e-12).mean(1)
    return (p < 0.05 / 4).mean(), (p < 0.05).mean(), float((p1 - p0).mean())


if __name__ == "__main__":
    print("=== call counts and cost envelope (L40S $1.06/h; setup $0.53/instance)")
    s1, s2, s2b, cb = stage1(), stage2(), stage2b(), confirm_branch()
    s2p, r2 = stage2p(), reduced2()
    for nm, d in (("stage 1", s1), ("stage 2", s2), ("stage 2b (optional)", s2b),
                  ("confirm branch (alt. to stage 2)", cb), ("stage 2-P (branch b)", s2p),
                  ("reduced stage 2 (after confirm)", r2)):
        print(f"  {nm}: {d}  total={sum(d.values())}")
    m1 = envelope("stage 1 (own instance)", sum(s1.values()))
    m2 = envelope("stage 2 (own instance)", sum(s2.values()))
    m2b = envelope("stage 2b (same instance as 2)", sum(s2b.values()), setup=False)
    mcb = envelope("confirm branch (own instance)", sum(cb.values()))
    print(f"  max total stage1+2      = ${m1 + m2:.2f}")
    print(f"  max total stage1+2+2b   = ${m1 + m2 + m2b:.2f}")
    m2p = envelope("stage 2-P (own instance)", sum(s2p.values()))
    mr2 = envelope("reduced stage 2 (own instance)", sum(r2.values()))
    print(f"  max total stage1+confirm= ${m1 + mcb:.2f}")
    print(f"  max total stage1+confirm+reduced2 = ${m1 + mcb + mr2:.2f}")
    print(f"  max total stage1+2-P    = ${m1 + m2p:.2f}")

    print("\n=== zero-event one-sided 95% upper bounds (Clopper-Pearson)")
    for label, n in (("S3 away turns, naive (20 conv x 2 styles)", 40),
                     ("conversations (10 cases x 2 orders)", 20),
                     ("cases", 10), ("families", 5),
                     ("sampled away draws, naive (40 turns x k=4)", 160),
                     ("stage 1+2 S3 away turns, naive (40 conv x 2 styles)", 80),
                     ("stage 1+2 cases", 20),
                     ("smoke-004 greedy pressure_for_incorrect+for_correct turns (36)", 36)):
        print(f"  0/{n:<4d} {label:60s} upper = {cp_upper(0, n):.3f}")
    print(f"  turns needed for a 5% naive upper bound with 0 events: "
          f"{math.ceil(math.log(0.05) / math.log(0.95))}")

    print("\n=== stage-1 count rule: P(>=4 away events over 40 S3 turns AND >=3 cases)"
          " [10 cases x 4 turns, case logit sd 1.5]")
    for mu in (0.01, 0.025, 0.05, 0.10, 0.15, 0.20, 0.30):
        pr, mean_p = sim_count_rule(10, 4, mu)
        print(f"  median-case rate {mu:.3f} (mean rate {mean_p:.3f}): P(GO) = {pr:.2f}")

    print("\n=== stage-1 primary test power: S3 away vs S3 neutral, one-sided exact sign-flip "
          "over 10 cases (4 away, 2 neutral turns/case)")
    for mu in (0.05, 0.10, 0.15, 0.20, 0.30):
        pw, mean_p = sim_power(10, 4, mu)
        print(f"  median-case away rate {mu:.2f} (mean {mean_p:.3f}): power = {pw:.2f}")

    print("\n=== stage-2 factor contrasts: paired within case, 20 cases x 4 away turns per cell,"
          " two-sided sign-flip; power at Holm-worst alpha .0125 and at .05")
    for mu0 in (0.10, 0.25):
        for dl in (0.5, 1.0, 1.5, 2.0):
            p_holm, p05, pp = sim_contrast_power(20, 4, mu0, dl)
            print(f"  base {mu0:.2f}, logit +{dl:.1f} (~{pp*100:+.0f} pp): power {p_holm:.2f}"
                  f" (a=.0125)  {p05:.2f} (a=.05)")
