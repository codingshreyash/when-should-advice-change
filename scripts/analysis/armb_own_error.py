"""Arm B own-error re-ask analysis with a cluster bootstrap (R4 in docs/real_world_check.md).

Input: run_own_error_reask.py output on data/scenarios/realworld/armb.jsonl (rows key "armb:<id>__rK"; copies of one
item share the prefix <id>). Copies are not independent, so the bootstrap resamples ORIGINAL ITEMS (2000 draws, seed
1684) and takes all their copies. Same definitions as own_error_reask.py: correct = choice == expected; need_more_information
counts as wrong unless it is the expected answer; unparsed/error rows are excluded.
Per model: own accuracy, E (own-wrong copies), n distinct items with an error, recovery and loss for the resample and each
wording, and value-add = recovery(wording) - recovery(resample) with a 95% interval.
R4 (written before the run): no model's re-ask recovery exceeds its resample recovery by more than its 95% interval,
i.e. the value-add interval does not lie wholly above 0. Verdict per model and wording is printed.
Usage: python3 scripts/analysis/armb_own_error.py RESULT.jsonl [...] --scenarios data/scenarios/realworld/armb.jsonl
"""
import argparse, collections, json, random

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--scenarios", required=True)
    a = ap.parse_args()
    truth = {json.loads(l)["id"]: json.loads(l)["expected"]["base"] for l in open(a.scenarios) if l.strip()}
    for f in a.files:
        rows = [json.loads(l) for l in open(f) if l.strip()]
        model = rows[0]["model"]
        item = lambda k: k.split(":", 1)[1].split("__r")[0]
        own = {r["key"]: r["own_correct"] for r in rows if r["phase"] == "turn1" and r["choice"] is not None}
        cond = collections.defaultdict(dict)
        for r in rows:
            if r["phase"] == "turn1" or r["choice"] is None: continue
            cond["resample" if r["phase"] == "resample" else r["wording"]][r["key"]] = (r["choice"] == truth[r["orig_id"]])
        wrong = sorted(k for k, v in own.items() if not v)
        right = sorted(k for k, v in own.items() if v and k in cond["resample"])
        by_item_w, by_item_r = collections.defaultdict(list), collections.defaultdict(list)
        for k in wrong: by_item_w[item(k)].append(k)
        for k in right: by_item_r[item(k)].append(k)
        iw, ir = sorted(by_item_w), sorted(by_item_r)
        print("=" * 78)
        print(f"MODEL {model}: own accuracy {sum(own.values())/len(own):.3f} (n={len(own)}), E={len(wrong)} copies on {len(iw)} distinct items, control {len(right)} copies")
        if len(wrong) < 5:
            print("  too few own errors to say anything (E < 5)"); continue
        def rec(c, items, d):
            ks = [k for i in items for k in d[i] if k in cond[c]]
            return sum(cond[c][k] for k in ks) / len(ks) if ks else float("nan")
        def loss(c, items):
            ks = [k for i in items for k in by_item_r[i] if k in cond[c]]
            return 1 - sum(cond[c][k] for k in ks) / len(ks) if ks else float("nan")
        rng = random.Random(1684)
        draws = [(rng.choices(iw, k=len(iw)), rng.choices(ir, k=len(ir)) if ir else []) for _ in range(2000)]
        print(f"  resample: recovery {rec('resample', iw, by_item_w):.2f}  loss {loss('resample', ir):.2f}")
        for w in ("neutral", "look_again", "review"):
            if w not in cond: continue
            va = sorted(rec(w, s, by_item_w) - rec("resample", s, by_item_w) for s, _ in draws)
            lo, hi = va[50], va[1949]
            pt = rec(w, iw, by_item_w) - rec("resample", iw, by_item_w)
            lv = sorted(loss(w, t) - loss("resample", t) for _, t in draws if t)
            # power flag added AFTER seeing the first results (see docs/real_world_check.md): with fewer than 10 distinct items
            # that have an own error, "R4 holds" says nothing, because the interval is too wide to fail.
            verdict = "R4 FAILS (interval wholly above 0)" if lo > 0 else ("R4 holds" if len(iw) >= 10 else "R4 uninformative (<10 items with an error)")
            ltxt = f"  loss diff {loss(w, ir) - loss('resample', ir):+.2f} [{lv[int(.025*len(lv))]:+.2f},{lv[int(.975*len(lv))-1]:+.2f}]" if lv else ""
            print(f"  {w:10s} recovery {rec(w, iw, by_item_w):.2f}  loss {loss(w, ir):.2f}  value-add {pt:+.2f} [{lo:+.2f},{hi:+.2f}]{ltxt}  -> {verdict}")

if __name__ == "__main__":
    main()
