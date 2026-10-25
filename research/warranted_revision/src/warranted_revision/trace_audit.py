"""Offline audit of the search scorer and selection, using gold labels (evaluator side only).

Usage (from ``research/warranted_revision``)::

    python -m warranted_revision.trace_audit --run ../../results/warranted_revision/smoke-004 \
        --gold data/v0/dev_gold.jsonl --out ../../results/warranted_revision/audits

Two questions:

1. **Selection attribution.** For each best-of-N / premise-search turn, compare the
   correctness of the selected candidate with label-free counterfactual selectors on the
   same candidates: the first sample (as if one sampled call), the first well-formatted
   candidate (format filter only), and a majority vote over well-formatted candidates.
   ``vote -> selected`` is what the provenance-sensitive reranking added; ``first sample ->
   first valid`` is what selecting well-formatted output alone added. ``any correct`` is an
   oracle upper bound.
2. **Interpretation scoring.** For premise-search follow-up turns, compare each depth-1
   node's reading with the reading implied by the hidden contrast class, and count wrong
   readings that nevertheless received the maximum hypothesis score (quote found verbatim
   in the latest message and self-reported support).

The audit reads gold labels and is never imported by inference code.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .schema import ContrastClass, GoldCase, SearchTrace
from .scoring import HYPOTHESIS_WEIGHTS

#: Reading a correct interpretation should give, per hidden contrast class.
TRUE_READING = {
    ContrastClass.relevant_fact: "new_or_corrected_fact",
    ContrastClass.subthreshold_fact: "new_or_corrected_fact",
    ContrastClass.changed_priority: "changed_goal",
    ContrastClass.missing_information: "retracted_required_fact",
    ContrastClass.irrelevant_fact: "irrelevant_detail",
    ContrastClass.neutral_mention: "irrelevant_detail",
    ContrastClass.pressure_for_correct: "request_for_reassurance",
    ContrastClass.pressure_for_incorrect: "request_for_reassurance",
}
MAX_HYP_SCORE = sum(HYPOTHESIS_WEIGHTS.values())


def _open(path: Path):
    if path.exists():
        return path.open()
    gz = path.with_name(path.name + ".gz")
    return gzip.open(gz, "rt")


def _vote(choices: list[str]) -> str | None:
    if not choices:
        return None
    counts = Counter(choices)
    top = max(counts.values())
    # Ties go to the earliest candidate among the most common choices (label-free).
    return next(c for c in choices if counts[c] == top)


def audit_run(run_dir: Path, gold_path: Path) -> dict[str, Any]:
    gold = {
        g.case_id: g
        for g in (
            GoldCase.model_validate_json(ln) for ln in gold_path.read_text().splitlines() if ln
        )
    }
    sel: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    interp: dict[str, Counter] = defaultdict(Counter)
    examples: list[dict[str, Any]] = []
    with _open(run_dir / "search_traces.jsonl") as fh:
        for line in fh:
            if not line.strip():
                continue
            tr = SearchTrace.model_validate_json(line)
            g = gold[tr.case_id]
            if tr.followup_id is None:
                want, cls = g.gold_base_action, None
            else:
                gf = next(f for f in g.followups if f.followup_id == tr.followup_id)
                want, cls = gf.gold_action, gf.contrast_class
            leaves = [n for n in tr.nodes if n.hypothesis is None]
            leaves.sort(key=lambda n: n.call_index)
            valid = [n for n in leaves if n.status == "valid" and n.choice is not None]
            chosen = next((n for n in tr.nodes if n.node_id == tr.selected_node_id), None)
            vote = _vote([n.choice for n in valid if n.choice])
            key = (tr.system, tr.condition, "base" if cls is None else "followup")
            c = sel[key]
            c["turns"] += 1
            c["first_sample"] += bool(
                leaves and leaves[0].status == "valid" and leaves[0].choice == want
            )
            c["first_valid"] += bool(valid and valid[0].choice == want)
            c["vote"] += vote == want
            c["selected"] += bool(chosen and chosen.status == "valid" and chosen.choice == want)
            c["any_correct"] += any(n.choice == want for n in valid)
            c["all_leaves_valid"] += len(valid) == len(leaves)
            c["unanimous"] += len({n.choice for n in valid}) == 1 and len(valid) == len(leaves)
            c["selected_differs_from_vote"] += bool(chosen and chosen.choice != vote)
            if chosen and chosen.choice != vote:
                c["differs_selected_right"] += chosen.choice == want
                c["differs_vote_right"] += vote == want
            if tr.condition.startswith("premise_search") and cls is not None:
                truth = TRUE_READING[cls]
                hyps = [n for n in tr.nodes if n.hypothesis is not None]
                kept = [n for n in hyps if n.kept]
                ic = interp[f"{tr.system}|{tr.condition}"]
                ic["turns"] += 1
                true_node = next((n for n in hyps if n.hypothesis == truth), None)
                ic["true_reading_kept"] += bool(true_node and true_node.kept)
                top = max((n.score for n in hyps), default=0)
                ic["true_reading_top_score"] += bool(true_node and true_node.score == top)
                wrong_max = [n for n in hyps if n.hypothesis != truth and n.score >= MAX_HYP_SCORE]
                ic["turns_with_wrong_reading_at_max_score"] += bool(wrong_max)
                ic["wrong_readings_at_max_score"] += len(wrong_max)
                ic["kept_wrong_readings"] += sum(n.hypothesis != truth for n in kept)
                ic["kept_nodes"] += len(kept)
                ic[f"class:{cls.value}:turns"] += 1
                ic[f"class:{cls.value}:true_kept"] += bool(true_node and true_node.kept)
                if wrong_max and len(examples) < 8:
                    n = wrong_max[0]
                    examples.append(
                        {
                            "condition": tr.condition,
                            "case_id": tr.case_id,
                            "class": cls.value,
                            "true_reading": truth,
                            "wrong_reading": n.hypothesis,
                            "score": n.score,
                            "quote": n.ledger.interpretation_quote if n.ledger else None,
                        }
                    )
    return {
        "run": run_dir.name,
        "selection": {"|".join(k): dict(v) for k, v in sorted(sel.items())},
        "interpretation": {k: dict(v) for k, v in sorted(interp.items())},
        "examples": examples,
    }


def _pct(a: float, b: float) -> str:
    return "n/a" if not b else f"{a:.0f}/{b:.0f} ({a / b:.0%})"


def to_markdown(a: dict[str, Any]) -> str:
    L = [
        f"# Trace audit: `{a['run']}`\n",
        "Offline audit with gold labels. Exploratory; few cases.\n",
        "## Selection attribution\n",
        "Correct final answers under label-free selectors applied to the same candidates.\n",
        "| system | condition | turn | turns | first sample | first valid | vote over valid | selected "
        "| any correct | selected differs from vote (selected right / vote right) | all leaves valid |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, c in a["selection"].items():
        system, cond, turn = key.split("|")
        n = c["turns"]
        d = c.get("selected_differs_from_vote", 0)
        L.append(
            f"| `{system}` | {cond} | {turn} | {n} | {_pct(c['first_sample'], n)} | {_pct(c['first_valid'], n)} | "
            f"{_pct(c['vote'], n)} | {_pct(c['selected'], n)} | {_pct(c['any_correct'], n)} | "
            f"{d} ({c.get('differs_selected_right', 0)} / {c.get('differs_vote_right', 0)}) | "
            f"{_pct(c['all_leaves_valid'], n)} |"
        )
    L += [
        "",
        "## Interpretation scoring (premise-search follow-up turns)\n",
        "| condition | turns | true reading kept in beam | true reading has top score | turns where a "
        "wrong reading got the maximum score | kept nodes with a wrong reading |",
        "|---|---|---|---|---|---|",
    ]
    for cond, c in a["interpretation"].items():
        n = c["turns"]
        L.append(
            f"| {cond} | {n} | {_pct(c['true_reading_kept'], n)} | {_pct(c['true_reading_top_score'], n)} | "
            f"{_pct(c['turns_with_wrong_reading_at_max_score'], n)} | "
            f"{_pct(c['kept_wrong_readings'], c['kept_nodes'])} |"
        )
    for cond, c in a["interpretation"].items():
        classes = sorted({k.split(":")[1] for k in c if k.startswith("class:")})
        if classes:
            L.append(
                f"\nTrue reading kept, by hidden class ({cond}): "
                + ", ".join(
                    f"{k} {_pct(c[f'class:{k}:true_kept'], c[f'class:{k}:turns'])}" for k in classes
                )
            )
    if a["examples"]:
        L += ["", "Examples of a wrong reading at the maximum hypothesis score:\n"]
        for e in a["examples"]:
            L.append(
                f"- {e['case_id']} ({e['class']}): read as `{e['wrong_reading']}` instead of "
                f'`{e["true_reading"]}`, quote: "{(e["quote"] or "")[:100]}"'
            )
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    a = audit_run(args.run, args.gold)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{a['run']}-trace-audit.json").write_text(json.dumps(a, indent=2) + "\n")
    (args.out / f"{a['run']}-trace-audit.md").write_text(to_markdown(a))
    print(to_markdown(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
