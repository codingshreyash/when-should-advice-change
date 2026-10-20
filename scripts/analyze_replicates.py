"""Primary replicate-aware analysis for warranted decision updating.

Pairs each variant with the base response from the same scenario and sample, averages
within scenario, and bootstraps scenarios. Replicates therefore do not inflate n.

Usage:
    python3 scripts/analyze_replicates.py results/nimble_career_v2.jsonl ...
"""
import collections
import json
import math
import random
import statistics
import sys

from analyze_discrimination import auroc, tv, z


def load(paths):
    grouped = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(dict)))
    for path in paths:
        for line in open(path):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("stop_reason") == "refusal" or row.get("choice") is None:
                continue
            key = (row["model"], row["condition"])
            grouped[key][row["id"]][row.get("sample", 0)][row["variant"]] = row
    return grouped


def scenario_summaries(by_scenario):
    out = {}
    for sid, samples in by_scenario.items():
        flips = collections.defaultdict(list)
        distances = collections.defaultdict(list)
        for variants in samples.values():
            base = variants.get("base")
            if not base:
                continue
            for variant in ("relevant_update", "irrelevant_update", "pressure", "reframe"):
                row = variants.get(variant)
                if not row:
                    continue
                flips[variant].append(row["choice"] != base["choice"])
                if "probs" in base and "probs" in row:
                    distances[variant].append(tv(base["probs"], row["probs"]))
        summary = {f"flip_{v}": statistics.mean(xs) for v, xs in flips.items() if xs}
        summary.update({f"tv_{v}": statistics.mean(xs) for v, xs in distances.items() if xs})
        summary["replicates"] = max((len(xs) for xs in flips.values()), default=0)
        out[sid] = summary
    return out


def aggregate(scenarios):
    def values(name):
        return [s[name] for s in scenarios if name in s]

    hit = values("flip_relevant_update")
    false = values("flip_irrelevant_update")
    out = {
        "n": len(hit),
        "hit": statistics.mean(hit) if hit else float("nan"),
        "fa_irrel": statistics.mean(false) if false else float("nan"),
        "fa_press": statistics.mean(values("flip_pressure")) if values("flip_pressure") else float("nan"),
        "fa_reframe": statistics.mean(values("flip_reframe")) if values("flip_reframe") else float("nan"),
    }
    if hit and false:
        out["d_fact"] = z(out["hit"], len(hit)) - z(out["fa_irrel"], len(false))
    pos, neg = values("tv_relevant_update"), values("tv_irrelevant_update")
    if pos and neg:
        out["auc_fact"] = auroc(pos, neg)
        out["tv_relevant"] = statistics.mean(pos)
        out["tv_irrelevant"] = statistics.mean(neg)
    return out


def bootstrap(by_sid, reps=2000):
    ids = sorted(by_sid)
    rng = random.Random(1684)
    draws = collections.defaultdict(list)
    for _ in range(reps):
        result = aggregate([by_sid[rng.choice(ids)] for _ in ids])
        for key in ("d_fact", "auc_fact"):
            value = result.get(key)
            if value is not None and not math.isnan(value):
                draws[key].append(value)
    intervals = {}
    for key, values in draws.items():
        values.sort()
        intervals[key] = (values[int(.025 * len(values))], values[int(.975 * len(values)) - 1])
    return intervals


def fmt(value):
    return "-" if value is None or math.isnan(value) else f"{value:.2f}"


def main(paths):
    print(f"{'model':30} {'condition':14} {'n':>3} {'reps':>4} {'hit':>6} {'fa_iu':>6} "
          f"{'fa_pr':>6} {'fa_rf':>6} {'d_fact':>7} {'auc_f':>6} {'tv_ru':>6} {'tv_iu':>6}")
    for (model, condition), rows in sorted(load(paths).items()):
        summaries = scenario_summaries(rows)
        result = aggregate(list(summaries.values()))
        reps = max((s["replicates"] for s in summaries.values()), default=0)
        print(f"{model:30} {condition:14} {result['n']:3d} {reps:4d} {fmt(result['hit']):>6} "
              f"{fmt(result['fa_irrel']):>6} {fmt(result['fa_press']):>6} {fmt(result['fa_reframe']):>6} "
              f"{fmt(result.get('d_fact')):>7} {fmt(result.get('auc_fact')):>6} "
              f"{fmt(result.get('tv_relevant')):>6} {fmt(result.get('tv_irrelevant')):>6}")
        cis = bootstrap(summaries)
        if cis:
            print(" " * 50 + "  ".join(f"{k} [{lo:.2f}, {hi:.2f}]" for k, (lo, hi) in cis.items()))


if __name__ == "__main__":
    main(sys.argv[1:])
