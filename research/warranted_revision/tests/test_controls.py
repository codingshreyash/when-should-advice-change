"""Synthetic controls through all four conditions: the evaluator must score them as designed."""

import json

import pytest

from warranted_revision.evaluate import evaluate_run

from .conftest import DEV_GOLD


@pytest.fixture(scope="module")
def metrics(control_run):
    m = evaluate_run(control_run, DEV_GOLD, n_draws=200)
    return {(a["system"], a["condition"]): a for a in m["arms"]}, m


CONDS = ["direct", "structured", "best_of_n", "premise_search"]


def val(arm, key):
    return arm[key]["value"]


def test_oracle_is_perfect(metrics):
    arms, _ = metrics
    for c in CONDS:
        a = arms[("control:oracle", c)]
        assert val(a, "axis_warranted_update") == 1.0
        assert val(a, "axis_unwarranted_stability") == 1.0
        assert val(a, "abstention_missing_information") == 1.0


def test_stay_put_fails_valid_updates(metrics):
    arms, _ = metrics
    for c in CONDS:
        a = arms[("control:always_stay_put", c)]
        assert val(a, "axis_warranted_update") == 0.0  # cannot win by repeating itself
        assert val(a, "axis_unwarranted_stability") == 1.0
        assert val(a, "abstention_missing_information") == 0.0
        assert a["update_tpr"]["value"] == 0.0


def test_agree_and_oppose_fail_opposite_pressure_directions(metrics):
    arms, _ = metrics
    for c in CONDS:
        agree, oppose = arms[("control:always_agree", c)], arms[("control:always_oppose", c)]
        pc = lambda a, k: a["per_class"][k]["joint_correct"]["value"]  # noqa: E731
        assert (
            pc(agree, "pressure_for_incorrect") == 0.0 and pc(agree, "pressure_for_correct") == 1.0
        )
        assert (
            pc(oppose, "pressure_for_incorrect") == 1.0
            and pc(oppose, "pressure_for_correct") == 0.0
        )
        assert val(agree, "axis_unwarranted_stability") == 0.75
        assert val(oppose, "axis_unwarranted_stability") == 0.75
        assert agree["attack_target_movement"]["value"] == 1.0
        assert oppose["attack_target_movement"]["value"] == 0.0


def test_position_bias_cannot_score_under_counterbalanced_order(metrics):
    arms, _ = metrics
    a = arms[("fake:first_option", "direct")]
    assert val(a, "base_accuracy") == pytest.approx(1 / 3)
    assert val(a, "axis_warranted_update") == 0.0


def test_metrics_have_denominators_and_cluster_intervals(metrics, control_run):
    _, m = metrics
    assert m["bootstrap"]["unit"] == "scenario family"
    for a in m["arms"]:
        assert a["n_families"] == 5 and a["n_cases"] == 5 and a["n_replicates"] == 3
        assert a["axis_warranted_update"]["n"] == 5 * 3 * 2
        assert a["axis_unwarranted_stability"]["n"] == 5 * 3 * 4
    kinds = {(c["a"], c["b"]) for c in m["comparisons"] if c["kind"] == "primary"}
    assert kinds == {("premise_search", "best_of_n"), ("structured", "direct")}
    manifest = json.loads((control_run / "manifest.json").read_text())
    assert manifest["expected_calls"] == manifest["actual_calls"]
    assert all(
        manifest["systems"][s]["privileged"]
        for s in manifest["systems"]
        if s.startswith("control:")
    )
