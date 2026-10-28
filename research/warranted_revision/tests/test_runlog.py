"""Run log: every logged run is accounted for and totals add up from the rows."""

import json
import os

import pytest

from warranted_revision.runlog import RESULTS, build, render


def _entry(run_id, kind, outcome, minutes, hourly=None, actual=None):
    return {
        "run_id": run_id,
        "date": "2026-10-25",
        "kind": kind,
        "outcome": outcome,
        "launch_minutes": minutes,
        "hourly_usd": hourly,
        "actual_cost_usd": actual,
        "instance_created": kind == "gpu",
        "github_run": None,
    }


def test_runlog_totals_from_a_synthetic_log(tmp_path):
    """Totals logic on a self-contained log: a completed run, a failed launch with no files."""
    run = tmp_path / "done-001"
    run.mkdir()
    (run / "manifest.json").write_text(
        json.dumps(
            {"synthetic": True, "actual_calls": 2, "case_ids": ["c1"], "conditions": ["direct"]}
        )
    )
    (run / "decisions.jsonl").write_text(
        "\n".join(json.dumps({"prompt_tokens": 10, "completion_tokens": 3}) for _ in range(2))
        + "\n"
    )
    (tmp_path / "runs.json").write_text(
        json.dumps(
            [
                _entry("done-001", "gpu", "completed", 30, hourly=1.0, actual=0.4),
                _entry("fail-001", "gpu", "failed: preflight", 6, hourly=1.0),
            ]
        )
    )
    rows, t = build(tmp_path)
    assert t["runs"] == 2 and t["gpu_launches"] == 2 and t["gpu_runs_completed"] == 1
    assert t["real_model_calls"] == 2 and t["real_prompt_tokens"] == 20
    assert t["est_cost_usd"] == 0.6 and t["actual_cost_usd_known"] == 0.4
    assert t["runs_missing_actual_cost"] == 1
    assert "## Totals" in render(rows, t)


def test_repo_runlog_is_consistent():
    """The committed log. Its files are not shipped to the GPU box, where the controller sets
    WREV_GIT_SHA (format-002 failed here before this check knew that); anywhere else a missing
    log is a real error."""
    if not (RESULTS / "runs.json").exists():
        if os.environ.get("WREV_GIT_SHA"):
            pytest.skip("launch bundle: results/ is not shipped")
        pytest.fail(f"missing {RESULTS / 'runs.json'}")
    rows, t = build()
    assert t["runs"] == len(rows) and len({r["run_id"] for r in rows}) == len(rows)
    gpu = [r for r in rows if r["kind"] == "gpu"]
    assert t["real_model_calls"] == sum(r.get("calls") or 0 for r in gpu)
    assert t["est_cost_usd"] == round(sum(r["est_cost_usd"] for r in gpu), 2)
    for r in rows:  # completed real runs must have their files and match the manifest call count
        if r["kind"] == "gpu" and r["outcome"].startswith("completed"):
            assert r["calls"] and r["decision_calls"] > 0
