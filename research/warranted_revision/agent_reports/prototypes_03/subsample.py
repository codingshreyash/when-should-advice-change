"""Vote accuracy of best-of-N restricted to k of its 9 samples, and leaf agreement structure
in premise search (within-parent vs across-parent). Agent 3 prototype, evaluator side.

    PYTHONPATH=src python3 agent_reports/prototypes_03/subsample.py ../../results/warranted_revision/smoke-004
"""
import itertools
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bottleneck import load  # noqa: E402


def vote_ok(choices, want):
    c = Counter(choices)
    if not c:
        return 0.0
    top = max(c.values())
    winners = [x for x in c if c[x] == top]
    return (want in winners) / len(winners)  # expected accuracy under a random tie-break


for run in sys.argv[1:]:
    gold, traces = load(Path(run), Path("data/v0/dev_gold.jsonl"))
    acc = Counter()
    n = Counter()
    agree = Counter()
    for t in traces:
        if t.followup_id is None:
            continue
        gf = next(f for f in gold[t.case_id].followups if f.followup_id == t.followup_id)
        want = gf.gold_action
        if t.condition == "best_of_n":
            ch = [x.choice for x in sorted(t.nodes, key=lambda x: x.call_index) if x.choice]
            for k in (1, 2, 3, 4, 5, 9):
                combos = list(itertools.combinations(ch, min(k, len(ch))))
                acc[k] += sum(vote_ok(c, want) for c in combos) / len(combos)
            n["bon"] += 1
        elif t.condition == "premise_search":
            lv = [x for x in t.nodes if x.depth == 2]
            for a, b in itertools.combinations(lv, 2):
                key = "within" if a.parent_id == b.parent_id else "across"
                agree[key + "_n"] += 1
                agree[key + "_same"] += a.choice == b.choice
    print(f"== {Path(run).name}: best-of-N vote accuracy using k of 9 samples (random tie-break), {n['bon']} follow-up turns")
    print("   " + "  ".join(f"k={k}: {acc[k] / n['bon']:.3f}" for k in (1, 2, 3, 4, 5, 9)))
    print(f"   premise_search leaf pair agreement: within-parent {agree['within_same']}/{agree['within_n']}, across-parent {agree['across_same']}/{agree['across_n']}")
