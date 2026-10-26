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
    check_instance_type,
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
    check_pinned_model(cfg)  # the committed config is pinned to a commit
    for bad in ("main", "PIN_ME", "c2022362"):
        cfg["systems"][0]["params"]["revision"] = bad
        with pytest.raises(GuardError):
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
        "brev": f'echo "brev $*" >> {log}; '
        + '[ "$1" = create ] && [ "${@: -1}" = "--dry-run" ] '
        + '&& echo "g5.xlarge (500GB disk), L4 (500GB disk), g6.xlarge (500GB disk)"; exit 0',
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
                "--results-dir",
                str(tmp_path / "res"),
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
    assert ctl.main(args + ["--commands-verified", "--results-dir", str(tmp_path / "res")]) == 2
    assert fake_bin.read_text() == "" if fake_bin.exists() else True


def test_instance_type_must_be_single_and_explicit(tmp_path, fake_bin):
    check_instance_type("g5.xlarge")
    for bad in ("", "g5.xlarge,g5.2xlarge", "g5.xlarge g4dn", "--count 3"):
        with pytest.raises(GuardError):
            check_instance_type(bad)
    ctl = _controller()
    cfg = json.loads((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    cfg["systems"][0]["params"]["revision"] = "c" * 40
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    args = [
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
        "g5.xlarge,g5.2xlarge",
        "--state",
        str(tmp_path / "s.json"),
        "--commands-verified",
        "--results-dir",
        str(tmp_path / "res"),
    ]
    assert ctl.main(args) == 2
    assert not fake_bin.exists() or "create" not in fake_bin.read_text()


def test_launch_checks_type_before_creating(tmp_path, fake_bin):
    ctl = _controller()
    cfg = json.loads((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    cfg["systems"][0]["params"]["revision"] = "d" * 40
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    with pytest.raises(subprocess.CalledProcessError):
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
                "g5.xlarge",
                "--state",
                str(tmp_path / "s.json"),
                "--commands-verified",
                "--results-dir",
                str(tmp_path / "res"),
            ]
        )
    brev = [c for c in fake_bin.read_text().splitlines() if c.startswith("brev ")]
    assert brev[0].startswith("brev login --token")
    assert brev[1].endswith("--dry-run") and "--type" not in brev[1]
    assert brev[2].endswith("--type g5.xlarge --timeout 900")


def test_launch_reuses_planned_instance_name(tmp_path, fake_bin):
    ctl = _controller()
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    state = tmp_path / "s.json"
    common = [
        "--hourly",
        "1.0",
        "--max-usd",
        "10",
        "--run-id",
        "t",
        "--config",
        str(cfg_path),
        "--instance-type",
        "g5.xlarge",
        "--state",
        str(state),
    ]
    assert ctl.main(["plan", *common]) == 0
    planned = json.loads(state.read_text())["instance"]
    with pytest.raises(subprocess.CalledProcessError):
        ctl.main(["launch", *common, "--commands-verified", "--results-dir", str(tmp_path / "res")])
    assert json.loads(state.read_text())["instance"] == planned
    assert f"brev create {planned} --type g5.xlarge --timeout 900" in fake_bin.read_text()


def test_accepted_types_parsing_and_refusal(tmp_path, fake_bin):
    ctl = _controller()
    out = "massedcompute_L40S (625GB disk), g2-standard-4:nvidia-l4:1 (500GB disk), hyperstack_L40x2 (1650GB disk)"
    assert ctl.accepted_types(out) == {
        "massedcompute_L40S",
        "g2-standard-4:nvidia-l4:1",
        "hyperstack_L40x2",
    }
    assert ctl.accepted_types("") == set()
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    rc = ctl.main(
        [
            "launch",
            "--hourly",
            "0.6",
            "--max-usd",
            "10",
            "--run-id",
            "t",
            "--config",
            str(cfg_path),
            "--instance-type",
            "hyperstack_A6000",
            "--state",
            str(tmp_path / "s.json"),
            "--commands-verified",
            "--results-dir",
            str(tmp_path / "res"),
        ]
    )
    assert rc == 2  # not in create's accepted list: refused before any create
    assert "--timeout 900" not in fake_bin.read_text()


def test_launch_passes_config_shard_and_bench(tmp_path, fake_bin):
    ctl = _controller()
    cfg = json.loads((PKG_ROOT / "configs" / "gpu_smoke.json").read_text())
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    state = tmp_path / "s.json"
    common = [
        "--hourly",
        "1.0",
        "--max-usd",
        "10",
        "--run-id",
        "t-s2of3",
        "--config",
        str(cfg_path),
        "--instance-type",
        "g5.xlarge",
        "--state",
        str(state),
        "--shard",
        "2/3",
        "--bench",
    ]
    assert ctl.main(["plan", *common]) == 0
    plan = json.loads(state.read_text())
    assert plan["shard"] == "2/3" and plan["bench"] is True
    assert plan["budget"]["expected_calls"] < 900  # a third of the smoke cases
    assert plan["budget"]["setup_hours"] == 0.75
    with pytest.raises(subprocess.CalledProcessError):
        ctl.main(["launch", *common, "--commands-verified", "--results-dir", str(tmp_path / "res")])
    log = fake_bin.read_text()
    assert "bash gpu/remote_job.sh t-s2of3" in log and "configs/_launch_config.json 2/3 1" in log
    assert log.count("brev delete") == 1


def test_cancelled_pilot_config_is_refused(tmp_path, fake_bin):
    ctl = _controller()
    copy = tmp_path / "renamed.json"
    copy.write_bytes((PKG_ROOT / "configs" / "pilot_challenge.json").read_bytes())
    for cfg in (PKG_ROOT / "configs" / "pilot_challenge.json", copy):
        rc = ctl.main(
            [
                "plan",
                "--hourly",
                "1.06",
                "--max-usd",
                "5",
                "--run-id",
                "t",
                "--config",
                str(cfg),
                "--instance-type",
                "L40S",
            ]
        )
        assert rc == 2
    assert not fake_bin.exists() or "brev" not in fake_bin.read_text()


def test_probe_config_plans_its_own_call_count(tmp_path, fake_bin, capsys):
    ctl = _controller()
    rc = ctl.main(
        [
            "plan",
            "--hourly",
            "1.06",
            "--max-usd",
            "2.25",
            "--run-id",
            "probe-t",
            "--config",
            str(PKG_ROOT / "configs" / "scaffold_probe_stage1.json"),
            "--instance-type",
            "L40S",
            "--est-seconds-per-call",
            "3.9",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0 and '"expected_calls": 970' in out


def test_goal_screen_plans_its_own_call_count_and_needs_pinning(tmp_path, fake_bin, capsys):
    ctl = _controller()
    args = [
        "plan",
        "--hourly",
        "1.06",
        "--max-usd",
        "4",
        "--run-id",
        "gs-t",
        "--instance-type",
        "L40S",
        "--est-seconds-per-call",
        "8",
        "--config",
    ]
    rc = ctl.main(args + [str(PKG_ROOT / "configs" / "goal_screen_qwen.json")])
    assert rc == 0 and '"expected_calls": 1038' in capsys.readouterr().out  # 1,008 + 30 preflight
    cfg = json.loads((PKG_ROOT / "configs" / "goal_screen_qwen.json").read_text())
    cfg["system"]["params"]["revision"] = "main"
    with pytest.raises(GuardError):
        check_pinned_model(cfg)  # the single `system` of a goal screen is checked too
    api = tmp_path / "api.json"
    api.write_text((PKG_ROOT / "configs" / "goal_screen_sonnet.json").read_text())
    assert ctl.main(args + [str(api)]) != 0  # API subjects never go through the GPU controller
