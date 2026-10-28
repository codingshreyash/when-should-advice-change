"""Tests for the overnight runner with a fake `claude` executable (no model, no network).

    python3 -m pytest -q scripts/overnight/test_overnight.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("overnight", HERE / "overnight.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)

FAKE = r'''
import json, os, sys, time
from pathlib import Path
prompt = sys.stdin.read()
pid = os.environ.get("OVERNIGHT_PASS", "")
log = Path(os.environ["FAKE_LOG"])
calls = json.loads(log.read_text()) if log.exists() else []
calls.append({"pass": pid, "argv": sys.argv[1:], "env": sorted(os.environ), "prompt": prompt[:20000],
              "hidden_visible": Path("docs/overnight/00_INITIAL_ASSESSMENT.md").exists()})
log.write_text(json.dumps(calls))
n = sum(c["pass"] == pid for c in calls)
if pid == "auth_check":
    print(json.dumps({"result": "OK", "is_error": False, "subtype": "success"})); sys.exit(0)
beh = json.loads(os.environ.get("FAKE_BEHAVIOR", "{}")).get(pid, "ok")
cfg = json.loads(Path("scripts/overnight/passes.json").read_text())
p = next(x for x in cfg["passes"] + cfg["smoke"] if x["id"] == pid)
def write_output(heads=p["headings"]):
    out = Path(p["output"]); out.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(f"{h}\n\nText for the section, long enough to pass the size check." for h in heads)
    if p.get("verdict_line"): body += "\n\nVERDICT: GO"
    out.write_text("# Report\n\n" + body + "\n")
if beh == "timeout":
    time.sleep(60)
elif beh == "error":
    print(json.dumps({"is_error": True, "subtype": "error_during_execution", "result": "boom"})); sys.exit(1)
elif beh == "ratelimit_once" and n == 1:
    print(json.dumps({"is_error": True, "subtype": "error", "result": "API Error: 429 rate limit"})); sys.exit(1)
elif beh == "protected":
    Path("data").mkdir(exist_ok=True); Path("data/x.txt").write_text("changed"); write_output()
elif beh == "outside_once" and n == 1:
    Path("stray.txt").write_text("x"); write_output()
elif beh == "missing_heading":
    write_output(p["headings"][:1])
elif beh == "relock_no_amendment":
    lk = Path("research/warranted_revision/configs/decision_procedure_lock.json")
    lk.write_text('{"changed": true}'); write_output()
else:
    write_output()
print(json.dumps({"result": "done", "is_error": False, "subtype": "success", "num_turns": 3,
                  "total_cost_usd": 0.01, "session_id": "s-" + pid}))
'''


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "scripts/overnight").mkdir(parents=True)
    shutil.copy(HERE / "overnight.py", r / "scripts/overnight/")
    shutil.copytree(HERE / "prompts", r / "scripts/overnight/prompts")
    cfg = json.loads((HERE / "passes.json").read_text())
    cfg["check_commands"] = {"tests": "true", "lock": "true"}
    (r / "scripts/overnight/passes.json").write_text(json.dumps(cfg))
    (r / "data").mkdir()
    (r / "data/scenarios.jsonl").write_text("{}\n")
    (r / "docs/overnight").mkdir(parents=True)
    (r / "docs/overnight/00_INITIAL_ASSESSMENT.md").write_text("prior view\n")
    (r / "research/warranted_revision/configs").mkdir(parents=True)
    (r / "research/warranted_revision/configs/decision_procedure_lock.json").write_text("{}")
    (r / "fake_claude.py").write_text(FAKE)
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "Test")
    git(r, "config", "user.email", "t@example.com")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    return r


def run(repo, tmp_path, behavior=None, extra=(), env=None):
    os.environ["FAKE_LOG"] = str(tmp_path / "calls.json")
    os.environ["FAKE_BEHAVIOR"] = json.dumps(behavior or {})
    for k, v in (env or {}).items():
        os.environ[k] = v
    wt = tmp_path / "wt"
    code = ov.main(["run", "--repo", str(repo), "--worktree", str(wt), "--hours", "1",
                    "--claude", f"{sys.executable} {repo / 'fake_claude.py'}", *extra])
    state = json.loads((wt / (".overnight-smoke" if "--smoke" in extra else ".overnight") / "state.json").read_text())
    calls = json.loads((tmp_path / "calls.json").read_text())
    return code, wt, state, calls


def statuses(state):
    return {k: v["status"] for k, v in state["passes"].items()}


def test_full_queue_commits_each_pass_and_scrubs_credentials(repo, tmp_path):
    code, wt, state, calls = run(repo, tmp_path, env={"BREV_API_TOKEN": "secret", "HF_TOKEN": "x",
                                                       "ANTHROPIC_API_KEY": "k"})
    assert code == 0 and set(statuses(state).values()) == {"done"}
    log = git(wt, "log", "--format=%s")
    for pid in ("01_verdict", "02_evidence", "03_audit", "04_fixes", "05_brief"):
        assert f"overnight {pid}" in log
    assert "overnight: run status" in log
    assert git(wt, "status", "--porcelain") == ""
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"  # main checkout untouched
    for c in calls:
        assert not {"BREV_API_TOKEN", "HF_TOKEN", "ANTHROPIC_API_KEY"} & set(c["env"])
    argv = next(c["argv"] for c in calls if c["pass"] == "01_verdict")
    assert "--strict-mcp-config" in argv and argv[argv.index("--permission-mode") + 1] == "dontAsk"
    denied = argv[argv.index("--disallowedTools") + 1:]
    assert "Bash(git push:*)" in denied and "Bash(brev:*)" in denied and "Edit(data/**)" in denied
    assert "WebSearch" in argv and "Edit(docs/overnight/01_RESEARCH_VERDICT.md)" in argv
    argv2 = next(c["argv"] for c in calls if c["pass"] == "02_evidence")
    assert "WebSearch" not in argv2
    # pass 1 could not see the initial assessment; pass 5 could; it is back afterwards
    assert not next(c for c in calls if c["pass"] == "01_verdict")["hidden_visible"]
    assert next(c for c in calls if c["pass"] == "05_brief")["hidden_visible"]
    assert (wt / "docs/overnight/00_INITIAL_ASSESSMENT.md").read_text() == "prior view\n"
    assert "Hard rules" in next(c for c in calls if c["pass"] == "02_evidence")["prompt"]


def test_protected_change_stops_the_queue_is_stashed_and_brief_still_runs(repo, tmp_path):
    code, wt, state, _ = run(repo, tmp_path, {"02_evidence": "protected"})
    s = statuses(state)
    assert code == 1 and s["02_evidence"] == "failed_protected" and len(state["passes"]["02_evidence"]["attempts"]) == 1
    assert s["03_audit"] == s["04_fixes"] == "skipped_stopped" and s["05_brief"] == "done"
    assert (wt / "data/x.txt").exists() is False and "rejected 02_evidence" in git(wt, "stash", "list")
    assert Path(state["passes"]["02_evidence"]["attempts"][0]["stashed_patch"]).exists()


def test_out_of_scope_write_is_retried_once(repo, tmp_path):
    code, wt, state, _ = run(repo, tmp_path, {"03_audit": "outside_once"})
    st = state["passes"]["03_audit"]
    assert code == 0 and st["status"] == "done" and len(st["attempts"]) == 2
    assert "outside this pass's scope: stray.txt" in st["attempts"][0]["problems"][0]
    assert not (wt / "stray.txt").exists()


def test_failures_dependencies_and_fallback_brief(repo, tmp_path):
    code, wt, state, _ = run(repo, tmp_path, {"03_audit": "missing_heading", "05_brief": "error"})
    s = statuses(state)
    assert s["03_audit"] == "failed" and len(state["passes"]["03_audit"]["attempts"]) == 2
    assert s["04_fixes"] == "skipped_dependency"
    assert state["passes"]["05_brief"].get("fallback")
    brief = (wt / "docs/overnight/MORNING_BRIEF.md").read_text()
    assert brief.rstrip().endswith("VERDICT: INCONCLUSIVE") and "runner fallback" in brief


def test_relock_without_amendment_is_rejected(repo, tmp_path):
    _, _, state, _ = run(repo, tmp_path, {"04_fixes": "relock_no_amendment"})
    assert state["passes"]["04_fixes"]["status"] == "failed"
    assert any("PREREG_AMENDMENT" in p for p in state["passes"]["04_fixes"]["attempts"][0]["problems"])


def test_timeout_kills_the_session(repo, tmp_path):
    cfg_path = repo / "scripts/overnight/passes.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["passes"][1]["timeout_min"] = 0.05
    cfg_path.write_text(json.dumps(cfg))
    git(repo, "commit", "-qam", "short timeout")
    _, _, state, _ = run(repo, tmp_path, {"02_evidence": "timeout"})
    att = state["passes"]["02_evidence"]["attempts"]
    assert state["passes"]["02_evidence"]["status"] == "failed" and len(att) == 2
    assert all(a["subtype"] == "runner_timeout" and a["elapsed_s"] < 50 for a in att)


def test_rate_limit_waits_and_gets_one_extra_attempt(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(ov, "RATE_LIMIT_WAIT_S", 0)
    _, _, state, _ = run(repo, tmp_path, {"01_verdict": "ratelimit_once"})
    st = state["passes"]["01_verdict"]
    assert st["status"] == "done" and st["rate_limited"] and len(st["attempts"]) == 2


def test_resume_skips_completed_passes(repo, tmp_path):
    run(repo, tmp_path, {"03_audit": "error"})
    os.environ["FAKE_BEHAVIOR"] = "{}"
    wt = tmp_path / "wt"
    state_path = wt / ".overnight/state.json"
    state = json.loads(state_path.read_text())
    state["passes"]["03_audit"] = {"status": "pending", "attempts": []}  # e.g. interrupted
    state["passes"]["04_fixes"] = {"status": "pending", "attempts": []}
    state_path.write_text(json.dumps(state))
    before = len(json.loads((tmp_path / "calls.json").read_text()))
    code, _, state, calls = run(repo, tmp_path)
    new = [c["pass"] for c in calls[before:]]
    assert new == ["auth_check", "03_audit", "04_fixes"]  # 01/02 not rerun; brief already done
    assert statuses(state)["04_fixes"] == "done"


def test_deadline_skips_passes_but_keeps_the_brief(repo, tmp_path):
    wt = tmp_path / "wt"
    os.environ["FAKE_LOG"] = str(tmp_path / "calls.json")
    os.environ["FAKE_BEHAVIOR"] = "{}"
    ov.main(["run", "--repo", str(repo), "--worktree", str(wt), "--hours", "0.55",
             "--claude", f"{sys.executable} {repo / 'fake_claude.py'}"])
    s = statuses(json.loads((wt / ".overnight/state.json").read_text()))
    # 0.55 h minus the 30 min brief reserve leaves under 5 min: every research pass is skipped
    assert s["01_verdict"] == "skipped_deadline" and s["05_brief"] == "done"


def test_smoke_mode_uses_its_own_state(repo, tmp_path):
    code, wt, state, calls = run(repo, tmp_path, extra=("--smoke",))
    assert code == 0 and statuses(state) == {"00_smoke": "done"}
    assert not (wt / ".overnight").exists()
    assert [c["pass"] for c in calls] == ["auth_check", "00_smoke"]


def test_real_queue_definition_is_consistent():
    cfg = json.loads((HERE / "passes.json").read_text())
    for p in cfg["smoke"] + cfg["passes"]:
        assert (HERE / p["prompt"]).exists()
        assert ov.match(p["output"], p["writes"]), p["id"]
        assert not ov.match(p["output"], cfg["protected"]), p["id"]
        assert not any(ov.match(w.replace("**", "x").replace("*", "x"), cfg["protected"]) for w in p["writes"]), p["id"]
        for c in p.get("checks", []):
            assert c == "amendment_if_relocked" or c in cfg["check_commands"]
    assert cfg["passes"][-1].get("always_run") and cfg["passes"][-1].get("verdict_line")
    assert "scripts/overnight/**" in cfg["protected"] and "data/**" in cfg["protected"]
