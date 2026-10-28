"""How well does each scorer component flag wrong leaves / wrong readings? (Agent 3 prototype)

Evaluator-side, offline. Run from research/warranted_revision:

    PYTHONPATH=src python3 agent_reports/prototypes_03/detectors.py ../../results/warranted_revision/smoke-004 [more runs]

Prints, per run, for every leaf-score component: n(fail), P(wrong | fail), P(wrong | pass).
Also: per contrast class, which wrong readings got SUPPORTED: yes; the expected rate of the
true reading entering the beam under a uniformly random tie-break (the current code's seeded
tie-break is pseudo-random per turn); and counterfactual selectors on the saved leaves.
"""

from __future__ import annotations

import itertools
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bottleneck import SEARCH, load, previous_choices, vote  # noqa: E402

from warranted_revision.scoring import CHANGE_LICENSING, NO_CHANGE_READINGS  # noqa: E402
from warranted_revision.trace_audit import TRUE_READING  # noqa: E402


def p_true_in_beam_random(d1, true_r, width=2):
    """Exact probability the true reading is kept if ties at the boundary are broken uniformly."""
    nodes = sorted(d1, key=lambda n: -n.score)
    scores = [n.score for n in nodes]
    if width >= len(nodes):
        return 1.0
    cut = scores[width - 1]
    above = [n for n in nodes if n.score > cut]
    tied = [n for n in nodes if n.score == cut]
    slots = width - len(above)
    if any(n.hypothesis == true_r for n in above):
        return 1.0
    if not any(n.hypothesis == true_r for n in tied):
        return 0.0
    return slots / len(tied)


def main(runs):
    for run in runs:
        run = Path(run)
        gold, traces = load(run, Path("data/v0/dev_gold.jsonl"))
        prev = previous_choices(traces)
        comp = defaultdict(Counter)
        yes_by_cls = defaultdict(Counter)
        beam_rand, beam_n = 0.0, 0
        sel = Counter()
        for t in traces:
            if t.followup_id is None:
                continue
            g = gold[t.case_id]
            gf = next(f for f in g.followups if f.followup_id == t.followup_id)
            want, cls = gf.gold_action, gf.contrast_class
            true_r = TRUE_READING[cls]
            leaves = [n for n in t.nodes if (n.depth == 2 if t.condition in SEARCH else True)]
            for lf in leaves:
                wrong = lf.choice != want
                for k, v in lf.score_components.items():
                    key = (t.condition, k)
                    if v < 1.0:
                        comp[key]["fail"] += 1
                        comp[key]["fail_wrong"] += wrong
                    else:
                        comp[key]["pass"] += 1
                        comp[key]["pass_wrong"] += wrong
                # leaf's own reading vs whether it changed the previous answer
                if lf.ledger is not None and lf.choice is not None:
                    changed = lf.choice != prev[(t.condition, t.case_id)]
                    r = lf.ledger.interpretation
                    tag = "lic" if r in CHANGE_LICENSING else ("nochg" if r in NO_CHANGE_READINGS else "other")
                    comp[(t.condition, f"own_reading={tag},changed={changed}")]["n"] += 1
                    comp[(t.condition, f"own_reading={tag},changed={changed}")]["wrong"] += wrong
            if t.condition in SEARCH:
                d1 = [n for n in t.nodes if n.depth == 1 and n.hypothesis]
                beam_rand += p_true_in_beam_random(d1, true_r)
                beam_n += 1
                if t.condition == "premise_search":
                    for n in d1:
                        if n.hypothesis != true_r:
                            yes_by_cls[cls.value][(n.hypothesis, bool(n.score_components.get("self_report")))] += 1
            # counterfactual selectors on the same leaves
            valid = [n for n in leaves if n.status == "valid" and n.choice]
            v_all = vote([n.choice for n in valid])
            ok_edit = [n for n in valid if n.score_components.get("supported_edit", 1.0) == 1.0]
            v_edit = vote([n.choice for n in ok_edit]) if ok_edit else v_all
            sel[(t.condition, "turns")] += 1
            sel[(t.condition, "vote")] += v_all == want
            sel[(t.condition, "vote|supported_edit")] += v_edit == want
            chosen = next((n for n in t.nodes if n.node_id == t.selected_node_id), None)
            sel[(t.condition, "selected")] += bool(chosen and chosen.choice == want)
        print(f"===== {run.name}")
        print("component                                   fail  P(wrong|fail)  pass  P(wrong|pass)")
        for (cond, k), c in sorted(comp.items()):
            if "fail" in c or "pass" in c:
                f, p = c["fail"], c["pass"]
                pf = f"{c['fail_wrong']}/{f}" if f else "-"
                pp = f"{c['pass_wrong']}/{p}" if p else "-"
                print(f"  {cond:28s} {k:22s} {f:4d} {pf:>9s} {p:6d} {pp:>9s}")
        print("leaf's own reading x changed-from-previous -> wrong rate")
        for (cond, k), c in sorted(comp.items()):
            if "n" in c:
                print(f"  {cond:28s} {k:40s} {c['wrong']}/{c['n']}")
        if beam_n:
            print(f"E[true reading in beam] under random tie-break (all search arms pooled): {beam_rand:.1f}/{beam_n}")
        print("SUPPORTED on wrong readings, premise_search, by class: (reading, yes) -> n")
        for cls, c in sorted(yes_by_cls.items()):
            print("  ", cls, dict(sorted(c.items())))
        print("counterfactual selectors:")
        conds = sorted({c for c, _ in sel})
        for cond in conds:
            n = sel[(cond, "turns")]
            print(f"  {cond:28s} vote {sel[(cond, 'vote')]}/{n}  vote|supported_edit {sel[(cond, 'vote|supported_edit')]}/{n}  selected {sel[(cond, 'selected')]}/{n}")


if __name__ == "__main__":
    main(sys.argv[1:])
