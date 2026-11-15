"""Analyse run_seeded_reask.py output.

Usage: python3 scripts/analysis/seeded_reask.py RESULT.jsonl [...] [--scenarios FILE]
Per model and wording: revise rate (choice != seeded_choice) for seed right and seed wrong;
recovery = P(correct | seed wrong); loss = P(wrong | seed right); balanced net = 0.5*(recovery-loss)
(change in accuracy from a 50/50 mix). correct = choice == expected[base]; need_more_information
counts as wrong. 95% bootstrap CIs (2000 resamples, seed 1684) over scenarios, paired: each
resample draws scenarios once and both seeds (and all wordings) use that same draw. Rows with
choice None or stop_reason 'error' are excluded and counted; a statistic averages over the drawn
scenarios that have a valid row for it. Also: revise-rate difference of each wording vs neutral
(paired per scenario), and a near (margin bins 2-3) / far (4-7) split of recovery and loss.
"""
import argparse, collections, json, random

WORDINGS = ("neutral", "look_again", "double_check", "are_you_sure", "review")

def mean(draw, d):
    xs = [d[i] for i in draw if i in d]
    return sum(xs) / len(xs) if xs else None

def ci(draws, f):
    pt = f(None)
    vals = sorted(v for v in (f(d) for d in draws) if v is not None)
    if pt is None or not vals: return None
    B = len(vals)
    return pt, vals[int(.025 * B)], vals[min(B - 1, int(.975 * B))]

def fmt(v, signed=True):
    if v is None: return "        n/a        "
    return (f"{v[0]:+.2f} [{v[1]:+.2f},{v[2]:+.2f}]" if signed else f"{v[0]:.2f} [{v[1]:.2f},{v[2]:.2f}]")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scenarios", default="data/scenarios/procedural/procedural_v0.jsonl")
    ap.add_argument("--resamples", type=int, default=2000)
    a = ap.parse_args()
    truth = {}
    for l in open(a.scenarios):
        if l.strip(): s = json.loads(l); truth[s["id"]] = s
    by_model = collections.defaultdict(list)
    for f in a.files:
        for l in open(f):
            if l.strip(): r = json.loads(l); by_model[r["model"]].append(r)
    for model, rows in sorted(by_model.items()):
        rows = [r for r in rows if r["id"] in truth]
        ids = sorted({r["id"] for r in rows}); bins = {r["id"]: r["margin_bin"] for r in rows}
        wordings = [w for w in WORDINGS if any(r["wording"] == w for r in rows)]
        rev, cor, excl = {}, {}, collections.Counter()
        for r in rows:
            k = (r["wording"], r["seed"])
            if r["choice"] is None or r["stop_reason"] == "error":
                excl[k] += 1; continue
            rev.setdefault(k, {})[r["id"]] = int(r["choice"] != r["seeded_choice"])
            cor.setdefault(k, {})[r["id"]] = int(r["choice"] == truth[r["id"]]["expected"]["base"])
        rec = {w: cor.get((w, "wrong"), {}) for w in wordings}
        los = {w: {i: 1 - v for i, v in cor.get((w, "right"), {}).items()} for w in wordings}
        rng = random.Random(1684)
        draws = [[ids[rng.randrange(len(ids))] for _ in ids] for _ in range(a.resamples)]
        def C(f): return ci(draws, f)
        print("=" * 78 + f"\nMODEL {model}: {len(ids)} scenarios, {len(rows)} rows")
        print("Excluded rows (None / error):",
              {f"{w}/{s}": n for (w, s), n in sorted(excl.items())} or "none")
        print("\n--- PER WORDING (95% bootstrap CI over scenarios, paired seeds) ---")
        print(f"{'wording':13} {'rev|right':>18} {'rev|wrong':>18} {'recovery':>18} {'loss':>18} {'balanced net':>20}")
        for w in wordings:
            def net(d, w=w):
                r, l = mean(d or ids, rec[w]), mean(d or ids, los[w])
                return None if r is None or l is None else 0.5 * (r - l)
            print(f"{w:13} {fmt(C(lambda d: mean(d or ids, rev.get((w, 'right'), {})), ), False):>18} "
                  f"{fmt(C(lambda d: mean(d or ids, rev.get((w, 'wrong'), {}))), False):>18} "
                  f"{fmt(C(lambda d: mean(d or ids, rec[w])), False):>18} "
                  f"{fmt(C(lambda d: mean(d or ids, los[w])), False):>18} {fmt(C(net)):>20}")
        if "neutral" in wordings:
            print("\n--- REVISE-RATE DIFFERENCE vs neutral (paired) ---")
            print(f"{'wording':13} {'seed right':>20} {'seed wrong':>20}")
            for w in wordings:
                if w == "neutral": continue
                cells = []
                for sd in ("right", "wrong"):
                    x, y = rev.get((w, sd), {}), rev.get(("neutral", sd), {})
                    both = {i: x[i] - y[i] for i in x if i in y}
                    cells.append(fmt(C(lambda d, both=both: mean(d or ids, both))))
                print(f"{w:13} {cells[0]:>20} {cells[1]:>20}")
        print("\n--- MARGIN SPLIT: near = bins 2-3, far = bins 4-7 (recovery / loss) ---")
        print(f"{'wording':13} {'recovery near':>18} {'recovery far':>18} {'loss near':>18} {'loss far':>18}")
        near = {i for i in ids if bins[i] <= 3}; far = set(ids) - near
        def sub(d, keep): return {i: v for i, v in d.items() if i in keep}
        for w in wordings:
            cells = [fmt(C(lambda d, x=sub(src[w], keep): mean(d or ids, x)), False)
                     for src in (rec, los) for keep in (near, far)]
            print(f"{w:13} {cells[0]:>18} {cells[1]:>18} {cells[2]:>18} {cells[3]:>18}")
        print(f"(scenarios: near={len(near)}, far={len(far)}; CIs resample all scenarios, so the near/far n varies per draw)")

if __name__ == "__main__":
    main()
