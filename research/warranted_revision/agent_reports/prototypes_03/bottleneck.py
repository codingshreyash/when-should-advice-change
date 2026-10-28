"""Offline per-turn bottleneck analysis for premise-search traces (Agent 3 prototype).

Reads saved traces + gold (evaluator side only; never imported by inference code).
Run from research/warranted_revision:

    python3 agent_reports/prototypes_03/bottleneck.py ../../results/warranted_revision/smoke-004

Per premise-search follow-up turn it reports: true reading in beam; correctness of leaves
whose parent had the true reading vs a wrong reading; vote vs selected; whether the leaf
(decide-call) ledger kept the parent's reading. For best-of-N it reports the reading each
sample wrote in its ledger and decision accuracy conditional on that reading being right.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from warranted_revision.schema import GoldCase, SearchTrace
from warranted_revision.trace_audit import TRUE_READING

SEARCH = {"premise_search", "premise_search_noprov", "premise_search_formatonly"}


def _open(p: Path):
    return p.open() if p.exists() else gzip.open(p.with_name(p.name + ".gz"), "rt")


def vote(choices):
    if not choices:
        return None
    c = Counter(choices)
    top = max(c.values())
    return next(x for x in choices if c[x] == top)


def load(run: Path, gold_path: Path):
    gold = {
        g.case_id: g
        for g in (GoldCase.model_validate_json(x) for x in gold_path.read_text().splitlines() if x)
    }
    traces = []
    with _open(run / "search_traces.jsonl") as fh:
        for ln in fh:
            if ln.strip():
                traces.append(SearchTrace.model_validate_json(ln))
    return gold, traces


def previous_choices(traces):
    """The condition's own base-turn answer per (condition, case)."""
    out = {}
    for t in traces:
        if t.followup_id is None:
            sel = next((n for n in t.nodes if n.node_id == t.selected_node_id), None)
            out[(t.condition, t.case_id)] = sel.choice if sel else None
    return out


def analyse(run: Path, gold_path: Path) -> dict:
    gold, traces = load(run, gold_path)
    prev = previous_choices(traces)
    agg: dict[str, Counter] = defaultdict(Counter)
    rows = []
    for t in traces:
        if t.followup_id is None:
            continue
        g = gold[t.case_id]
        gf = next(f for f in g.followups if f.followup_id == t.followup_id)
        want, cls = gf.gold_action, gf.contrast_class
        true_r = TRUE_READING[cls]
        base_ok = prev[(t.condition, t.case_id)] == g.gold_base_action
        c = agg[t.condition]
        c["turns"] += 1
        c["base_ok"] += base_ok
        leaves = sorted([n for n in t.nodes if n.depth == 2 or n.hypothesis is None], key=lambda n: n.call_index)
        if t.condition in SEARCH:
            d1 = {n.node_id: n for n in t.nodes if n.depth == 1 and n.hypothesis}
            leaves = [n for n in t.nodes if n.depth == 2]
            kept = [n for n in d1.values() if n.kept]
            in_beam = any(n.hypothesis == true_r for n in kept)
            c["true_in_beam"] += in_beam
            top = max(n.score for n in d1.values())
            tops = [n for n in d1.values() if n.score == top]
            c["true_at_top"] += any(n.hypothesis == true_r for n in tops)
            c["n_tied_top_sum"] += len(tops)
            c["top_unique_and_true"] += len(tops) == 1 and tops[0].hypothesis == true_r
            # self-report: SUPPORTED yes for true vs wrong readings
            for n in d1.values():
                key = "true" if n.hypothesis == true_r else "wrong"
                c[f"selfrep_{key}_n"] += 1
                c[f"selfrep_{key}_yes"] += n.score_components.get("self_report", 0) == 1.0
                c[f"quote_{key}_ok"] += n.score_components.get("quote_in_latest", 0) == 1.0
            for lf in leaves:
                par = d1[lf.parent_id]
                key = "true_par" if par.hypothesis == true_r else "wrong_par"
                c[f"leaf_{key}_n"] += 1
                c[f"leaf_{key}_ok"] += lf.choice == want
                if lf.ledger is not None:
                    c["leaf_ledger_n"] += 1
                    c["leaf_keeps_parent_reading"] += lf.ledger.interpretation == par.hypothesis
                    c["leaf_ledger_reading_true"] += lf.ledger.interpretation == true_r
            true_leaves = [lf for lf in leaves if d1[lf.parent_id].hypothesis == true_r]
            if true_leaves:
                c["turns_with_true_leaves"] += 1
                c["true_leaves_all_ok"] += all(lf.choice == want for lf in true_leaves)
                c["true_leaves_any_ok"] += any(lf.choice == want for lf in true_leaves)
        else:
            for lf in leaves:
                if lf.ledger is not None:
                    key = "rtrue" if lf.ledger.interpretation == true_r else "rwrong"
                    c[f"bon_{key}_n"] += 1
                    c[f"bon_{key}_ok"] += lf.choice == want
            in_beam = None
        valid = [n.choice for n in leaves if n.status == "valid" and n.choice]
        v = vote(valid)
        sel = next((n for n in t.nodes if n.node_id == t.selected_node_id), None)
        c["vote_ok"] += v == want
        c["sel_ok"] += bool(sel and sel.choice == want)
        c["any_ok"] += want in valid
        c["leaf_n"] += len(leaves)
        c["leaf_ok"] += sum(ch == want for ch in valid)
        rows.append(
            dict(
                cond=t.condition, case=t.case_id, fu=t.followup_id, cls=cls.value, want=want,
                base_ok=base_ok, true_in_beam=in_beam,
                kept=[(n.node_id, n.hypothesis, n.score) for n in t.nodes if n.depth == 1 and n.kept],
                leaves=[(n.node_id, n.parent_id, n.choice, n.score) for n in leaves],
                vote=v, sel=sel.choice if sel else None,
            )
        )
    return {"agg": {k: dict(v) for k, v in agg.items()}, "rows": rows}


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def main(argv):
    run = Path(argv[0])
    args = [a for a in argv if not a.startswith("--")]
    gold = Path(args[1]) if len(args) > 1 else Path("data/v0/dev_gold.jsonl")
    res = analyse(run, gold)
    for cond, c in res["agg"].items():
        print(f"== {run.name} / {cond}")
        print("  base turn correct (per follow-up turn):", pct(c["base_ok"], c["turns"]))
        print("  vote", pct(c["vote_ok"], c["turns"]), " selected", pct(c["sel_ok"], c["turns"]),
              " any", pct(c["any_ok"], c["turns"]), " leaf acc", pct(c["leaf_ok"], c["leaf_n"]))
        if "true_in_beam" in c or cond in SEARCH:
            print("  true reading in beam", pct(c.get("true_in_beam", 0), c["turns"]),
                  " true at top score", pct(c.get("true_at_top", 0), c["turns"]),
                  " unique top & true", pct(c.get("top_unique_and_true", 0), c["turns"]),
                  " mean #tied at top", f"{c.get('n_tied_top_sum', 0) / c['turns']:.2f}")
            print("  SUPPORTED=yes: true readings", pct(c.get("selfrep_true_yes", 0), c.get("selfrep_true_n", 0)),
                  " wrong readings", pct(c.get("selfrep_wrong_yes", 0), c.get("selfrep_wrong_n", 0)))
            print("  quote verbatim: true", pct(c.get("quote_true_ok", 0), c.get("selfrep_true_n", 0)),
                  " wrong", pct(c.get("quote_wrong_ok", 0), c.get("selfrep_wrong_n", 0)))
            print("  leaf acc | true-reading parent", pct(c.get("leaf_true_par_ok", 0), c.get("leaf_true_par_n", 0)),
                  " | wrong-reading parent", pct(c.get("leaf_wrong_par_ok", 0), c.get("leaf_wrong_par_n", 0)))
            print("  turns w/ true-parent leaves: all leaves right", pct(c.get("true_leaves_all_ok", 0), c.get("turns_with_true_leaves", 0)),
                  " any right", pct(c.get("true_leaves_any_ok", 0), c.get("turns_with_true_leaves", 0)))
            print("  decide-call ledger keeps parent reading", pct(c.get("leaf_keeps_parent_reading", 0), c.get("leaf_ledger_n", 0)),
                  " leaf ledger reading true", pct(c.get("leaf_ledger_reading_true", 0), c.get("leaf_ledger_n", 0)))
        if "bon_rtrue_n" in c or "bon_rwrong_n" in c:
            print("  best-of-N sample acc | own reading true", pct(c.get("bon_rtrue_ok", 0), c.get("bon_rtrue_n", 0)),
                  " | own reading wrong", pct(c.get("bon_rwrong_ok", 0), c.get("bon_rwrong_n", 0)))
    if "--rows" in argv:
        for r in res["rows"]:
            print(json.dumps(r))


if __name__ == "__main__":
    main(sys.argv[1:])
