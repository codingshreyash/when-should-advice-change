"""Break-even first-answer accuracy for a re-ask, from the seeded experiment.

For a model and a wording, a re-ask turns a right first answer wrong with probability `loss` and a wrong
first answer right with probability `recovery` (scripts/analysis/seeded_reask.py). If the first answer is
right with probability p, the re-ask changes accuracy by  (1-p)*recovery - p*loss.
It helps on average when p < recovery / (recovery + loss) =: break-even accuracy.
Break-even 1.00 means it never hurt here. Break-even 0.50 means it only helps when the first answer is
wrong at least half the time. CIs: 95% bootstrap over scenarios (2000 resamples, seed 1684), paired seeds.

Usage: python3 scripts/analysis/breakeven.py RESULTS.jsonl [...] --scenarios data/scenarios/procedural/procedural_v0.jsonl
Rows with a None choice are excluded. A choice of need_more_information counts as wrong.
"""
import argparse, collections, json, random

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+"); ap.add_argument("--scenarios", required=True)
    a = ap.parse_args()
    S = {}
    for l in open(a.scenarios):
        if l.strip():
            r = json.loads(l); S[r["id"]] = r
    cell = collections.defaultdict(dict)   # (model, wording) -> {(id, seed): correct}
    for f in a.results:
        for l in open(f):
            if not l.strip(): continue
            r = json.loads(l)
            if r.get("choice") is None or r["id"] not in S: continue
            cell[(r["model"], r["wording"])][(r["id"], r["seed"])] = (r["choice"] == S[r["id"]]["expected"]["base"])
    rng = random.Random(1684)
    print(f"{'model':45s} {'wording':13s} {'recovery':>8s} {'loss':>6s} {'break-even accuracy [95% CI]':>32s}")
    for (m, w), d in sorted(cell.items()):
        ids = sorted({i for i, _ in d})
        def stats(sample):
            rec = [d[(i, "wrong")] for i in sample if (i, "wrong") in d]
            los = [not d[(i, "right")] for i in sample if (i, "right") in d]
            if not rec or not los: return None
            R, L = sum(rec) / len(rec), sum(los) / len(los)
            return R, L, (R / (R + L) if R + L > 0 else float("nan"))
        base = stats(ids)
        bs = sorted(x[2] for x in (stats(rng.choices(ids, k=len(ids))) for _ in range(2000)) if x and x[2] == x[2])
        lo, hi = bs[int(0.025 * len(bs))], bs[int(0.975 * len(bs))]
        print(f"{m:45s} {w:13s} {base[0]:8.2f} {base[1]:6.2f} {base[2]:12.2f} [{lo:.2f}, {hi:.2f}]")

if __name__ == "__main__":
    main()
