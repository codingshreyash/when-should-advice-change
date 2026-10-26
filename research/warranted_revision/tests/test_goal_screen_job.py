"""Launch checks for the goal-screen API job, and a static check of its workflow."""

import json
import os
import shutil

import pytest
import yaml

from warranted_revision import goal_screen as gs
from warranted_revision import goal_screen_job as job
from warranted_revision.runner import PKG_ROOT

SONNET = "configs/goal_screen_sonnet.json"
WORKFLOW = PKG_ROOT.parent.parent / ".github/workflows/warranted-revision-goal-screen-api.yml"


@pytest.fixture(autouse=True)
def _api_tests_without_cancellation(request, monkeypatch):
    """The API launch machinery is still tested; its one config is cancelled (Amendment 2)."""
    if "cancelled" not in request.node.name:
        monkeypatch.setattr(job, "CANCELLED", {})


def test_sonnet_api_config_is_cancelled():
    with pytest.raises(job.LaunchError, match="cancelled"):
        job.check(SONNET, "dry-run", 0.0)


def test_launch_lock_is_current():
    job.check_lock()  # frozen files may not change without a recorded relock


@pytest.fixture()
def root(tmp_path):
    for f in job.FROZEN + [job.LOCK, "configs/goal_screen_opus.json"]:
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PKG_ROOT / f, tmp_path / f)
    return tmp_path


def test_dry_run_plan_without_approval(root):
    plan = job.check(SONNET, "dry-run", 0.0, root=root)
    assert plan == {
        "full_calls": 1008,
        "preflight_calls": 30,
        "full_cap_usd": 8.0,
        "preflight_cap_usd": 1.0,
    }


def test_refusals(root):
    with pytest.raises(job.LaunchError, match="not an approved"):
        job.check("configs/goal_screen_opus.json", "dry-run", 0.0, root=root)
    with pytest.raises(job.LaunchError, match="approve-usd"):
        job.check(SONNET, "preflight", 10.0, root=root)
    with pytest.raises(job.LaunchError, match="needs the approved preflight"):
        job.check(SONNET, "full", 8.0, root=root)
    items = root / "v2/ai_precalibration/candidate_v3/items.json"
    items.write_text(items.read_text().replace("$", "USD ", 1))
    with pytest.raises(job.LaunchError, match="frozen files differ"):
        job.check(SONNET, "preflight", 8.0, root=root)


def _preflight(tmp_path, monkeypatch, **patch):
    """A preflight made with the synthetic backend on the real config, then marked real."""
    cfg = gs.load_config(PKG_ROOT / SONNET, "pf-test")
    out = gs.run(
        cfg, preflight=True, backend=gs.FakeScreenBackend("stubborn"), out_root=tmp_path / "pf"
    )
    man = json.loads((out / "manifest.json").read_text())
    man.update({"synthetic": False, **patch})
    (out / "manifest.json").write_text(json.dumps(man))
    return tmp_path / "pf", out


def test_full_run_accepts_a_clean_preflight(tmp_path, monkeypatch):
    pf, out = _preflight(tmp_path, monkeypatch)
    plan = job.check(SONNET, "full", 8.0, preflight_dir=pf)
    s = plan["preflight"]
    assert s["actual_calls"] == 30 and s["errors"] == 0 and s["spend_usd"] < 1.0
    assert "text" not in json.dumps(s)  # counts only, never model text


@pytest.mark.parametrize(
    "patch,msg",
    [
        ({"synthetic": True}, "synthetic"),
        ({"stopped": "budget: x"}, "stopped"),
        ({"actual_calls": 29}, "planned calls"),
        ({"items_sha256": "0" * 64}, "frozen inputs differ"),
        ({"preflight_projection": {"proceed": False}}, "projection"),
    ],
)
def test_full_run_refuses_bad_preflights(tmp_path, monkeypatch, patch, msg):
    pf, _ = _preflight(tmp_path, monkeypatch, **patch)
    with pytest.raises(job.LaunchError, match=msg):
        job.check(SONNET, "full", 8.0, preflight_dir=pf)


def test_full_run_refuses_api_errors_and_unparseable(tmp_path, monkeypatch):
    pf, out = _preflight(tmp_path, monkeypatch)
    rows = [json.loads(x) for x in (out / "calls.jsonl").read_text().splitlines()]
    rows[3]["error"] = "BadRequestError: thinking"
    for r in rows[5:12]:
        r["text"] = "no response line"
    (out / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(job.LaunchError, match="API errors.*unparseable"):
        job.check(SONNET, "full", 8.0, preflight_dir=pf)


def test_workflow_is_manual_gated_and_keeps_the_key_in_one_step():
    if not WORKFLOW.exists() and os.environ.get("WREV_GIT_SHA"):
        pytest.skip("launch bundle: .github is not shipped")
    wf = yaml.safe_load(WORKFLOW.read_text())
    on = wf.get("on", wf.get(True))
    assert list(on) == ["workflow_dispatch"]
    inputs = on["workflow_dispatch"]["inputs"]
    assert inputs["mode"]["default"] == "dry-run"
    assert inputs["config"]["options"] == list(job.ALLOWED)
    assert wf["permissions"] == {"contents": "read"}
    check, paid = wf["jobs"]["check"], wf["jobs"]["paid"]
    assert "secrets." not in yaml.safe_dump(check)
    assert paid["needs"] == "check" and paid["environment"] == "goal-screen-paid"
    with_key = [s for s in paid["steps"] if "secrets." in yaml.safe_dump(s)]
    assert [s["name"] for s in with_key] == ["Run (the only step that sees the API key)"]
    for s in check["steps"] + paid["steps"]:
        assert "${{" not in s.get("run", ""), s["name"]  # inputs only via env (no injection)


def test_summary_validates_against_the_offered_option_codes(tmp_path, monkeypatch):
    """An invented code, or a real code from another scenario, is invalid in the summary."""
    pf, out = _preflight(tmp_path, monkeypatch)
    rows = [json.loads(x) for x in (out / "calls.jsonl").read_text().splitlines()]
    codes = job.allowed_codes(json.loads((out / "manifest.json").read_text())["config"])
    answered = [r for r in rows if r["kind"] != "free"]
    first = next(r for r in answered if r["kind"] == "first")
    first["text"] = "Reasoning.\nRESPONSE: recommend invented_option"
    control = next(r for r in answered if r["kind"].startswith("control"))
    elsewhere = next(c for k, v in codes.items() for c in v if c not in codes[control["item_id"]])
    control["text"] = f"RESPONSE: recommend {elsewhere}"  # well formed, offered elsewhere
    decision = next(r for r in answered if r["kind"] == "decision_A")
    offered = codes[decision["item_id"]]
    decision["text"] = f"RESPONSE: conditional IF_TRUE={offered[0]} OTHERWISE=made_up"
    (out / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    s = job.summarize(out)
    assert s["response_line"] == {"valid": len(answered) - 3, "invalid": 3}
    assert s["response_line_by_kind"]["first"]["invalid"] == 1
    assert s["response_line_by_kind"]["control"]["invalid"] == 1
    assert s["response_line_by_kind"]["decision"]["invalid"] == 1


def _hf_preflight(tmp_path, elapsed_s=60.0, **patch):
    cfg = gs.load_config(PKG_ROOT / "configs/goal_screen_qwen.json", "gate-test")
    out = gs.run(
        cfg,
        preflight=True,
        backend=gs.FakeScreenBackend("stubborn", batched=True),
        out_root=tmp_path,
    )
    man = json.loads((out / "manifest.json").read_text())
    man.update({"elapsed_s": elapsed_s, **patch})
    (out / "manifest.json").write_text(json.dumps(man))
    return out, man


def test_on_box_gate_projects_runtime_from_measured_batches(tmp_path):
    out, man = _hf_preflight(tmp_path, elapsed_s=120.0)
    assert man["planned_batches"] == 12 and man["actual_calls"] == 30
    s = job.gate(out, remaining_min=200)
    assert s["gate_passed"] and s["full_run_batches"] == 117
    assert s["seconds_per_batch"] == 10.0 and s["projected_full_run_min"] == 19.5
    assert json.loads((out / "gate.json").read_text())["gate_passed"]


def test_on_box_gate_stops_runs_that_cannot_finish_or_are_invalid(tmp_path):
    out, _ = _hf_preflight(tmp_path / "a", elapsed_s=12 * 60.0)  # 60 s per batch: 117 min
    with pytest.raises(job.LaunchError, match="exceeds"):
        job.gate(out, remaining_min=150)  # 117 x 1.5 > 150
    assert job.gate(out, remaining_min=180)["gate_passed"]
    out, _ = _hf_preflight(tmp_path / "b", stopped="budget: x")
    with pytest.raises(job.LaunchError, match="stopped"):
        job.gate(out, remaining_min=500)
    out, _ = _hf_preflight(tmp_path / "c")
    rows = [json.loads(x) for x in (out / "calls.jsonl").read_text().splitlines()]
    for r in [r for r in rows if r["kind"] != "free"][:5]:  # 5 of 30 answers > 10%
        r["text"] = "RESPONSE: recommend not_an_option"
    rows[-1]["error"] = "OutOfMemoryError: CUDA"
    (out / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(job.LaunchError, match="errors.*unparseable"):
        job.gate(out, remaining_min=500)


def test_on_box_gate_fails_with_no_time_left_even_for_a_fast_preflight(tmp_path):
    out, _ = _hf_preflight(tmp_path, elapsed_s=0.01)  # projects ~0 minutes
    with pytest.raises(job.LaunchError, match="min left"):
        job.gate(out, remaining_min=0)
    with pytest.raises(job.LaunchError, match="min left"):
        job.gate(out, remaining_min=-3)
