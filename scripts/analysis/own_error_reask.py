"""Analyse run_own_error_reask.py output: does a second look fix the model's OWN mistakes?

Usage: python3 scripts/analysis/own_error_reask.py RESULT.jsonl [...] --scenarios v0.jsonl L1.jsonl L2.jsonl L3.jsonl
Scenario files map to pools by file name (procedural_v0 -> v0, hard_pool_L1 -> L1, ...).
Per model: own accuracy (turn 1, by pool), E = own-wrong items, control sample of own-right items.
For 'resample' (fresh independent turn 1, the baseline) and each wording:
  recovery = P(correct | own wrong); loss = P(wrong | own right control sample);
  value-add = recovery(wording) - recovery(resample), loss diff likewise (paired: same items, same bootstrap draw);
  revise = choice != own turn-1 choice (own-wrong / own-right);
  break-even accuracy = recovery / (recovery + loss).
correct = choice == expected[base]; need_more_information is wrong. Unparsed/error rows are excluded and counted.
95% bootstrap CIs, 2000 resamples, seed 1684, over ITEMS (own-wrong items and control items drawn separately,
once per draw, shared by all conditions).
"""
import argparse, collections, json, os, random

def mean(xs):
    xs = list(xs); return sum(xs) / len(xs) if xs else None

def ci(vals, pt):
    v = sorted(x for x in vals if x is not None)
    if pt is None or not v: return None
    B = len(v); return pt, v[int(.025 * B)], v[min(B - 1, int(.975 * B))]

def fmt(v, signed=False):
    if v is None: return "       n/a       "
    return f"{v[0]:+.2f} [{v[1]:+.2f},{v[2]:+.2f}]" if signed else f"{v[0]:.2f} [{v[1]:.2f},{v[2]:.2f}]"

def pool_of(path):
    b = os.path.basename(path)
    for tag in ("L1", "L2", "L3"):
        if f"hard_pool_{tag}" in b: return tag
    return "v0" if "v0" in b else os.path.splitext(b)[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scenarios", nargs="+", required=True)
    ap.add_argument("--resamples", type=int, default=2000)
    a = ap.parse_args()
    truth = {}
    for p in a.scenarios:
        tag = pool_of(p)
        for l in open(p):
            if l.strip(): s = json.loads(l); truth[(tag, s["id"])] = s["expected"]["base"]
    by_model = collections.defaultdict(list)
    for f in a.files:
        for l in open(f):
            if l.strip(): r = json.loads(l); by_model[r["model"]].append(r)
    for model, rows in sorted(by_model.items()):
        rows = [r for r in rows if (r["pool"], r["orig_id"]) in truth]
        exp = lambda r: truth[(r["pool"], r["orig_id"])]
        t1, excl, cond = {}, collections.Counter(), collections.defaultdict(dict)
        for r in rows:
            bad = r["choice"] is None or r["stop_reason"] == "error"
            if r["phase"] == "turn1":
                if bad: excl["turn1"] += 1
                else: t1[r["key"]] = r
            else:
                c = "resample" if r["phase"] == "resample" else r["wording"]
                if bad: excl[c] += 1
                else: cond[c][r["key"]] = r
        # re-derive own correctness from the scenario truth (do not trust the stored field)
        ok = {k: r["choice"] == exp(r) for k, r in t1.items()}
        wrong = sorted(k for k, v in ok.items() if not v)
        # control sample = own-right items that have later-phase rows
        later = {k for c in cond.values() for k in c}
        right = sorted(k for k in later if ok.get(k))
        conds = [c for c in ("resample", *[w for w in ("neutral", "look_again", "review")]) if c in cond]
        corr = {c: {k: int(r["choice"] == exp(r)) for k, r in cond[c].items()} for c in conds}
        rev = {c: {k: int(r["choice"] != t1[k]["choice"]) for k, r in cond[c].items() if k in t1} for c in conds}
        print("=" * 78 + f"\nMODEL {model}: pool {len(t1) + excl['turn1']} items, valid turn-1 {len(t1)}, "
              f"own accuracy {mean(ok.values()):.3f}, E (own wrong) = {len(wrong)}, "
              f"control sample (own right) = {len(right)}")
        print("Excluded rows (unparsed/error):", dict(excl) or "none")
        if len(wrong) < 15: print(f"WARNING: few own errors (E={len(wrong)}): wide intervals")
        print("Own accuracy by pool: " + "  ".join(
            f"{p}={mean(v for k, v in ok.items() if k.split(':')[0] == p):.2f} (n={sum(k.split(':')[0] == p for k in ok)})"
            for p in sorted({k.split(':')[0] for k in ok})))
        if not wrong or not right or not conds: print("(nothing to compare)"); continue
        rng = random.Random(1684)
        draws = [([wrong[rng.randrange(len(wrong))] for _ in wrong], [right[rng.randrange(len(right))] for _ in right])
                 for _ in range(a.resamples)]
        def rec(c, d=None):   # recovery
            return mean(corr[c][k] for k in (d or wrong) if k in corr[c])
        def los(c, d=None):
            return mean(1 - corr[c][k] for k in (d or right) if k in corr[c])
        def be(c, d=None, dr=None):
            R, L = rec(c, d), los(c, dr)
            return None if R is None or L is None or R + L == 0 else R / (R + L)
        def C(f):   # f(wrong_draw, right_draw)
            return ci([f(dw, dr) for dw, dr in draws], f(None, None))
        print("\n--- RECOVERY, LOSS, BREAK-EVEN (95% bootstrap CI over items) ---")
        print(f"{'condition':11} {'recovery':>18} {'loss':>18} {'revise|wrong':>18} {'revise|right':>18} {'break-even acc':>18}")
        for c in conds:
            print(f"{c:11} {fmt(C(lambda dw, dr: rec(c, dw))):>18} {fmt(C(lambda dw, dr: los(c, dr))):>18} "
                  f"{fmt(C(lambda dw, dr: mean(rev[c][k] for k in (dw or wrong) if k in rev[c]))):>18} "
                  f"{fmt(C(lambda dw, dr: mean(rev[c][k] for k in (dr or right) if k in rev[c]))):>18} "
                  f"{fmt(C(lambda dw, dr: be(c, dw, dr))):>18}")
        if "resample" in conds:
            print("\n--- VALUE-ADD vs plain resample (paired over the same items) ---")
            print(f"{'wording':11} {'recovery diff':>20} {'loss diff':>20}")
            for c in conds:
                if c == "resample": continue
                print(f"{c:11} {fmt(C(lambda dw, dr: None if rec(c, dw) is None or rec('resample', dw) is None else rec(c, dw) - rec('resample', dw)), True):>20} "
                      f"{fmt(C(lambda dw, dr: None if los(c, dr) is None or los('resample', dr) is None else los(c, dr) - los('resample', dr)), True):>20}")
        print("(value-add: positive recovery diff = the wording fixes more own errors than just asking again; "
              "positive loss diff = it breaks more right answers)")

if __name__ == "__main__":
    main()
