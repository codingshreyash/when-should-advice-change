"""Budget equalization and call accounting."""

from collections import Counter, defaultdict

import pytest
from pydantic import ValidationError

from warranted_revision.conditions import ConditionConfig
from warranted_revision.runner import RunConfig, run

from .conftest import DEV_INPUTS, read_jsonl


def test_config_rejects_unmatched_budgets():
    ConditionConfig()
    with pytest.raises(ValidationError):
        ConditionConfig(best_of_n=8)
    with pytest.raises(ValidationError):
        ConditionConfig(beam_width=3)
    ConditionConfig(best_of_n=11, beam_width=3, decisions_per_node=2)


def test_actual_calls_and_tokens_matched(control_run):
    per_turn = defaultdict(Counter)
    max_tokens = defaultdict(set)
    for r in read_jsonl(control_run / "predictions.jsonl"):
        per_turn[(r["system"], r["condition"])][
            (r["case_id"], r["followup_id"], r["replicate"])
        ] += 1
        max_tokens[r["condition"]].add(r["gen"]["max_new_tokens"])
    for (system, cond), counts in per_turn.items():
        want = {"direct": 1, "structured": 1, "best_of_n": 9, "premise_search": 9}[cond]
        assert set(counts.values()) == {want}, (system, cond)
    assert max_tokens["best_of_n"] == max_tokens["premise_search"]
    for r in read_jsonl(control_run / "decisions.jsonl"):
        assert (
            r["n_calls"]
            == {"direct": 1, "structured": 1, "best_of_n": 9, "premise_search": 9}[r["condition"]]
        )


def test_max_calls_preflight_refuses(tmp_path):
    cfg = RunConfig(
        run_id="big",
        label="t",
        split="dev",
        inputs=str(DEV_INPUTS),
        conditions=["premise_search"],
        systems=[{"kind": "fake", "name": "visible_random"}],
        max_calls=10,
    )
    with pytest.raises(SystemExit):
        run(cfg, out_root=tmp_path)
    assert not (tmp_path / "big").exists()


def test_gpu_runs_require_max_calls(tmp_path):
    cfg = RunConfig(
        run_id="gpu",
        label="t",
        split="dev",
        inputs=str(DEV_INPUTS),
        conditions=["direct"],
        systems=[{"kind": "hf", "name": "some/model"}],
    )
    with pytest.raises(SystemExit):
        run(cfg, dry_run=True, out_root=tmp_path)


def test_runs_are_immutable(tmp_path):
    from .conftest import make_run

    make_run(tmp_path, "once", [{"kind": "fake", "name": "visible_random"}], conditions=["direct"])
    with pytest.raises(SystemExit):
        make_run(
            tmp_path, "once", [{"kind": "fake", "name": "visible_random"}], conditions=["direct"]
        )
