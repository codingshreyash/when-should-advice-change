"""Label-free uncertainty flags on saved best-of-N candidates (Agent 3 prototype, offline).

Flag a turn when (a) the 9 decisions disagree, or (b) samples agree on every extracted fact
value but disagree on the derived numbers in rule_check (an arithmetic-uncertainty signal
that a decision vote cannot see), or (c) some sample's own reading is a no-change reading
while its decision differs from the previous answer. Reports how flags split between turns
the vote got right and wrong.

    PYTHONPATH=src python3 agent_reports/prototypes_03/dispersion.py ../../results/warranted_revision/smoke-004
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bottleneck import load, previous_choices, vote  # noqa: E402

from warranted_revision.scoring import NO_CHANGE_READINGS  # noqa: E402


def derived(rc):
    return tuple(sorted((round(rc.left_value, 2), round(rc.right_value, 2))))


def flags_for(nodes, prev):
    ch = [n.choice for n in nodes if n.choice]
    f = {}
    f["decision_disagree"] = len(set(ch)) > 1
    led = [n.ledger for n in nodes if n.ledger is not None and n.ledger.rule_check is not None]
    facts_sets = {tuple(sorted(x.value for x in L.facts)) for L in led}
    vals = Counter(derived(L.rule_check) for L in led)
    f["derived_disagree"] = len(vals) > 1
    f["derived_disagree_same_facts"] = len(vals) > 1 and len(facts_sets) == 1
    f["nochange_but_changed"] = any(
        n.ledger is not None and n.ledger.interpretation in NO_CHANGE_READINGS and n.choice and n.choice != prev
        for n in nodes
    )
    return f


for run in sys.argv[1:]:
    gold, traces = load(Path(run), Path("data/v0/dev_gold.jsonl"))
    prev = previous_choices(traces)
    tab = Counter()
    for t in traces:
        if t.followup_id is None or t.condition != "best_of_n":
            continue
        gf = next(f for f in gold[t.case_id].followups if f.followup_id == t.followup_id)
        ch = [n.choice for n in sorted(t.nodes, key=lambda n: n.call_index) if n.choice]
        ok = vote(ch) == gf.gold_action
        fl = flags_for(t.nodes, prev[(t.condition, t.case_id)])
        tab["ok" if ok else "wrong"] += 1
        for k, v in fl.items():
            tab[(k, "ok" if ok else "wrong")] += v
        anyf = fl["decision_disagree"] or fl["derived_disagree"] or fl["nochange_but_changed"]
        tab[("any", "ok" if ok else "wrong")] += anyf
        if not ok:
            print("  vote wrong:", t.case_id, t.followup_id, gf.contrast_class.value, fl)
    print(f"== {Path(run).name} best-of-N: vote right {tab['ok']}, wrong {tab['wrong']}")
    for k in ("decision_disagree", "derived_disagree", "derived_disagree_same_facts", "nochange_but_changed", "any"):
        print(f"   {k:28s} flagged among right {tab[(k, 'ok')]}/{tab['ok']}, among wrong {tab[(k, 'wrong')]}/{tab['wrong']}")
