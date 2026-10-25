"""GPU spending guard and controller cleanup, tested offline with fake brev/ssh/scp binaries."""

import importlib.util
import json
import os
import stat
import subprocess

import pytest

from warranted_revision.gpu_guard import (
    GuardError,
    check_instance_name,
    check_pinned_model,
    instance_name,
    plan_budget,
)
from warranted_revision.runner import PKG_ROOT


def test_budget_refusals():
    with pytest.raises(GuardError):
        plan_budget(None, 15, expected_calls=10)
    with pytest.raises(GuardError):
        plan_budget(1.0, 15.01, expected_calls=10)
    with pytest.raises(GuardError):
        plan_budget(1.0, 0, expected_calls=10)
    with pytest.raises(GuardError):  # $1 cap at $4/h leaves no time after setup
        plan_budget(4.0, 1, expected_calls=10)
    with pytest.raises(GuardError):  # plan does not fit
        plan_budget(1.0, 15, expected_calls=100_000)


def test_budget_plan_is_conservative():
    p = plan_budget(2.0, 15, expected_calls=900, est_seconds_per_call=6)
    assert p.permitted_hours == pytest.approx(min(15 * 0.8 / 2.0, 4.0))
    assert p.worst_case_usd <= 15 * 0.8
    assert p.run_deadline_minutes == int((p.permitted_hours - 0.5) * 60)


def test_instance_names_and_pinning():
    name = instance_name("Smoke Run #1", token="abc123")
    assert name == "wrev-smoke-smoke-run-1-abc123"
    for bad in ("my-dev-box", "wrev-smoke-x", "prod-gpu-1", "wrev-smoke-ok-abc123; rm -rf /"):
        with pytest.raises(GuardError):
            check_instance_name(bad)
    cfg = json.loads((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    with pytest.raises(GuardError):
        check_pinned_model(cfg)  # the committed config is deliberately unpinned
    cfg["systems"][0]["params"]["revision"] = "a" * 40
    check_pinned_model(cfg)


def _controller():
    spec = importlib.util.spec_from_file_location(
        "brev_controller", PKG_ROOT / "gpu" / "brev_controller.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    """Fake brev/ssh/scp that log their argv. ssh fails for anything but `true`."""
    log = tmp_path / "calls.log"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    scripts = {
        "brev": f'echo "brev $*" >> {log}; exit 0',
        "ssh": f'echo "ssh $*" >> {log}; [ "${{@: -1}}" = "true" ] && exit 0; exit 3',
        "scp": f'echo "scp $*" >> {log}; exit 0',
    }
    for name, body in scripts.items():
        p = bindir / name
        p.write_text("#!/usr/bin/env bash\n" + body + "\n")
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("BREV_API_TOKEN", "test-token")
    return log


def test_cleanup_only_deletes_recorded_controller_instance(tmp_path, fake_bin):
    ctl = _controller()
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"instance": "wrev-smoke-run-abc123", "created": True, "deleted": False})
    )
    assert ctl.main(["cleanup", "--state", str(state)]) == 0
    calls = fake_bin.read_text()
    assert "brev delete wrev-smoke-run-abc123" in calls and "test-token" in calls
    assert json.loads(state.read_text())["deleted"] is True
    # A tampered state naming an unrelated resource is refused before any delete.
    state.write_text(
        json.dumps({"instance": "my-other-instance", "created": True, "deleted": False})
    )
    fake_bin.write_text("")
    assert ctl.main(["cleanup", "--state", str(state)]) == 2
    assert "delete" not in fake_bin.read_text()


def test_launch_failure_still_deletes_instance(tmp_path, fake_bin):
    ctl = _controller()
    cfg = json.loads((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    cfg["systems"][0]["params"]["revision"] = "b" * 40
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    state = tmp_path / "state.json"
    with pytest.raises(subprocess.CalledProcessError):  # the remote run fails
        ctl.main(
            [
                "launch",
                "--hourly",
                "1.0",
                "--max-usd",
                "10",
                "--run-id",
                "t",
                "--config",
                str(cfg_path),
                "--instance-type",
                "L4",
                "--state",
                str(state),
                "--commands-verified",
            ]
        )
    calls = fake_bin.read_text().splitlines()
    name = json.loads(state.read_text())["instance"]
    assert calls[-2] == f"brev delete {name}" and calls[-1] == "brev ls"
    assert sum("brev delete" in c for c in calls) == 1
    assert json.loads(state.read_text())["deleted"] is True


def test_launch_refuses_without_verification_or_token(tmp_path, monkeypatch, fake_bin):
    ctl = _controller()
    args = [
        "launch",
        "--hourly",
        "1.0",
        "--max-usd",
        "10",
        "--run-id",
        "t",
        "--instance-type",
        "L4",
        "--state",
        str(tmp_path / "s.json"),
    ]
    assert ctl.main(args) == 2
    monkeypatch.delenv("BREV_API_TOKEN")
    assert ctl.main(args + ["--commands-verified"]) == 2
    assert fake_bin.read_text() == "" if fake_bin.exists() else True
