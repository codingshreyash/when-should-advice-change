"""Own-error re-ask results split by pool (medqa / csqa). Same definitions as own_error_reask.py.

Per model and pool: n own-wrong E, control size C, recovery for resample and each wording, loss, and the
value-add of each wording over the resample (recovery diff, paired over items) with a 95% bootstrap CI
(2000 resamples, seed 1684, over own-wrong items). Control items are few per pool (about 50), so loss is a point only.
Usage: python3 scripts/analysis/own_error_by_pool.py RESULT.jsonl [...] --scenarios medqa.jsonl csqa.jsonl
"""
import argparse, collections, json, os, random

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--scenarios", nargs="+", required=True)
    a = ap.parse_args()
    truth = {}
    for p in a.scenarios:
        tag = os.path.splitext(os.path.basename(p))[0]
        for l in open(p):
            if l.strip(): s = json.loads(l); truth[(tag, s["id"])] = s["expected"]["base"]
    for f in a.files:
        rows = [json.loads(l) for l in open(f) if l.strip()]
        model = rows[0]["model"]
        own = {r["key"]: r["own_correct"] for r in rows if r["phase"] == "turn1" and r["choice"] is not None}
        cond = collections.defaultdict(dict)       # condition -> key -> correct
        for r in rows:
            if r["phase"] == "turn1" or r["choice"] is None: continue
            c = "resample" if r["phase"] == "resample" else r["wording"]
            cond[c][r["key"]] = (r["choice"] == truth[(r["pool"], r["orig_id"])])
        print(f"=== {model}")
        for pool in ("medqa", "csqa"):
            wrong = sorted(k for k, v in own.items() if not v and k.startswith(pool + ":"))
            right = [k for k, v in own.items() if v and k.startswith(pool + ":") and k in cond["resample"]]
            acc = sum(v for k, v in own.items() if k.startswith(pool + ":")) / max(1, sum(k.startswith(pool + ":") for k in own))
            print(f"  {pool}: own accuracy {acc:.2f}, E={len(wrong)}, control={len(right)}")
            rng = random.Random(1684)
            def rec(c, ks): 
                xs = [cond[c][k] for k in ks if k in cond[c]]; return sum(xs) / len(xs) if xs else float("nan")
            base = rec("resample", wrong)
            print(f"    resample recovery {base:.2f}  loss {1 - rec('resample', right):.2f}")
            for w in ("neutral", "look_again", "review"):
                pt = rec(w, wrong) - base
                bs = sorted(rec(w, s) - rec("resample", s) for s in (rng.choices(wrong, k=len(wrong)) for _ in range(2000)))
                print(f"    {w:10s} recovery {rec(w, wrong):.2f}  loss {1 - rec(w, right):.2f}  value-add {pt:+.2f} [{bs[50]:+.2f},{bs[1949]:+.2f}]")

if __name__ == "__main__":
    main()
