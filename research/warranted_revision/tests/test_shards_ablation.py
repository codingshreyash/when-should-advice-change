"""Sharded execution and the provenance ablation."""

import json

import pytest

from warranted_revision.aggregate import aggregate, check_shards
from warranted_revision.conditions import ConditionConfig
from warranted_revision.schema import Manifest, ParsedOutput, PremiseLedger
from warranted_revision.scoring import ScoringContext, score_candidate, score_format_only

from .conftest import make_run, read_jsonl

CONDS = ["direct", "best_of_n", "premise_search", "premise_search_formatonly"]
SYS = [{"kind": "fake", "name": "visible_random"}]


def _rows(run, name):
    return sorted(
        json.dumps({k: v for k, v in r.items() if k != "run_id"}, sort_keys=True)
        for r in read_jsonl(run / name)
    )


def test_shards_merge_to_the_full_run(tmp_path):
    full = make_run(tmp_path, "full", SYS, conditions=CONDS, replicates=2)
    s1 = make_run(tmp_path, "part-s1", SYS, conditions=CONDS, replicates=2, shard="1/2")
    s2 = make_run(tmp_path, "part-s2", SYS, conditions=CONDS, replicates=2, shard="2/2")
    m1 = Manifest.model_validate_json((s1 / "manifest.json").read_text())
    m2 = Manifest.model_validate_json((s2 / "manifest.json").read_text())
    assert set(m1.case_ids).isdisjoint(m2.case_ids)
    assert sorted(m1.case_ids + m2.case_ids) == sorted(m1.planned_case_ids)
    merged = aggregate([s2, s1], tmp_path / "runs" / "merged")
    assert merged.actual_calls == merged.expected_calls
    full_m = Manifest.model_validate_json((full / "manifest.json").read_text())
    assert merged.actual_calls == full_m.actual_calls
    for name in ("predictions.jsonl", "decisions.jsonl", "search_traces.jsonl"):
        assert _rows(tmp_path / "runs" / "merged", name) == _rows(full, name), name


def test_aggregate_refuses_unsafe_merges(tmp_path):
    s1 = make_run(tmp_path, "a-s1", SYS, conditions=["direct"], shard="1/2")
    s2 = make_run(tmp_path, "a-s2", SYS, conditions=["direct"], shard="2/2")
    other = make_run(tmp_path, "b-s2", SYS, conditions=["direct"], shard="2/2", replicates=2)
    load = lambda d: Manifest.model_validate_json((d / "manifest.json").read_text())  # noqa: E731
    assert check_shards([load(s1), load(s2)]) == []
    assert any("1..2" in e for e in check_shards([load(s1)]))  # missing shard
    assert any("config differs" in e for e in check_shards([load(s1), load(other)]))
    dup = load(s1).model_copy(update={"run_id": "dup", "shard": "2/2"})
    assert any("in both" in e for e in check_shards([load(s1), dup]))
    with pytest.raises(SystemExit):
        aggregate([s1], tmp_path / "runs" / "bad")


def test_ablation_has_same_budget_and_shares_depth1_samples(tmp_path):
    cfg = ConditionConfig()
    for turn in ("base", "followup"):
        assert cfg.calls_per_turn("premise_search_formatonly", turn) == cfg.calls_per_turn(
            "premise_search", turn
        )
    run = make_run(tmp_path, "abl", SYS, conditions=["premise_search", "premise_search_formatonly"])
    rows = read_jsonl(run / "predictions.jsonl")

    def depth1(cond):
        return [
            (r["case_id"], r["call_role"], r["gen"]["seed"], r["messages_sha256"])
            for r in rows
            if r["condition"] == cond
            and r["turn"] == "base"
            and r["call_role"].startswith("hypothesis")
        ]

    assert depth1("premise_search") == depth1("premise_search_formatonly")
    counts = {}
    for r in read_jsonl(run / "decisions.jsonl"):
        counts.setdefault(r["condition"], set()).add(r["n_calls"])
    assert counts == {"premise_search": {9}, "premise_search_formatonly": {9}}


def test_format_only_scorer_ignores_provenance():
    ctx = ScoringContext(
        user_texts=("base", "Update: the rate is 7%."),
        latest_text="Update: the rate is 7%.",
        options=("a", "b"),
        previous_choice="a",
    )
    grounded = ParsedOutput(
        status="valid",
        choice="b",
        ledger=PremiseLedger(
            interpretation="new_or_corrected_fact", interpretation_quote="the rate is 7%"
        ),
    )
    fabricated = ParsedOutput(
        status="valid",
        choice="b",
        ledger=PremiseLedger(
            interpretation="request_for_reassurance", interpretation_quote="something never said"
        ),
    )
    assert score_candidate(grounded, ctx)[0] > score_candidate(fabricated, ctx)[0]
    assert score_format_only(grounded, ctx)[0] == score_format_only(fabricated, ctx)[0]


def test_evaluate_and_report_with_every_condition(tmp_path):
    from warranted_revision.evaluate import evaluate_run
    from warranted_revision.report import write_report

    from .conftest import DEV_GOLD

    conds = ["direct", "structured", "best_of_n", "premise_search", "premise_search_formatonly"]
    run = make_run(tmp_path, "allconds", SYS, conditions=conds)
    m = evaluate_run(run, DEV_GOLD, n_draws=50)
    (run / "metrics.json").write_text(json.dumps(m, default=str))
    out = write_report(run)
    text = out.read_text()
    assert (
        "premise_search_formatonly" in text and (run / "plots" / "update_vs_pressure.png").exists()
    )
    assert any(c["kind"] == "ablation" for c in m["comparisons"])


def test_derived_selectors_and_identical_tiebreak(tmp_path):
    from warranted_revision.evaluate import evaluate_run

    from .conftest import DEV_GOLD

    run = make_run(
        tmp_path,
        "sel",
        SYS,
        conditions=["best_of_n", "premise_search", "premise_search_formatonly"],
    )
    m = evaluate_run(run, DEV_GOLD, n_draws=50)
    names = {a["condition"] for a in m["arms"]}
    for base in ("best_of_n", "premise_search", "premise_search_formatonly"):
        assert {f"{base}:vote", f"{base}:first", f"{base}:firstvalid"} <= names
    derived = [a for a in m["arms"] if a["derived"]]
    real = {a["condition"]: a for a in m["arms"] if not a["derived"]}
    assert all(a["n_cases"] == real["best_of_n"]["n_cases"] for a in derived)
    assert any(c["kind"] == "selection" and c["b"] == "best_of_n:vote" for c in m["comparisons"])
    # Search and its ablation give each depth-1 node the same tie-break key.
    keys = {}
    for tr in read_jsonl(run / "search_traces.jsonl"):
        if tr["condition"].startswith("premise_search"):
            for n in tr["nodes"]:
                if n["hypothesis"]:
                    keys.setdefault((tr["case_id"], tr["followup_id"], n["node_id"]), set()).add(
                        n["score_components"]["tiebreak_key"]
                    )
    assert keys and all(len(v) == 1 for v in keys.values())
