"""Launch checks for the goal-screen API job, and a static check of its workflow."""

import json
import shutil

import pytest
import yaml

from warranted_revision import goal_screen as gs
from warranted_revision import goal_screen_job as job
from warranted_revision.runner import PKG_ROOT

SONNET = "configs/goal_screen_sonnet.json"
WORKFLOW = PKG_ROOT.parent.parent / ".github/workflows/warranted-revision-goal-screen-api.yml"


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
