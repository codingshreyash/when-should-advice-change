#!/usr/bin/env python3
"""Bounded, restartable overnight runner: a finite queue of headless Claude Code passes.

Each pass in ``passes.json`` is one fresh ``claude -p`` session with a fixed prompt, a turn
cap, a wall-clock timeout and a least-privilege tool list. After every pass the runner
itself checks the result before anything is kept:

* the required output file exists and has the required headings (and verdict line);
* every changed path is one the pass may write, and no protected path changed;
* the pass's checks pass (test suite, frozen-file lock, amendment when re-locked).

A pass that passes is committed by the runner on a dedicated branch in its own git worktree.
A pass that fails has its changes saved as a patch and stashed (recoverable, never deleted),
and it is retried at most once. A protected-path violation stops the queue. The morning
brief pass always runs last; if it fails, the runner writes a plain status brief itself.
State is saved after every step, so rerunning the same command resumes after the last
completed pass. The runner never pushes, merges, launches GPUs or calls paid APIs, and it
removes provider credentials (Brev, Hugging Face, GitHub, API keys) from the agent's
environment.

    python3 scripts/overnight/overnight.py run --smoke        # short read-only test
    python3 scripts/overnight/overnight.py run --hours 8      # the overnight queue
    python3 scripts/overnight/overnight.py status --worktree ../when-should-advice-change-overnight

Uses the Claude Code login already configured on the machine. ANTHROPIC_API_KEY is removed
from the agent's environment unless --keep-api-key is given, so the run uses that login and
not API billing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STATE_DIR = ".overnight"
SMOKE_STATE_DIR = ".overnight-smoke"
MAX_ATTEMPTS = 2  # one retry
RATE_LIMIT_WAIT_S = 15 * 60
RATE_LIMIT = re.compile(r"rate.?limit|usage limit|overloaded|\b429\b|\b529\b", re.I)

#: Read-only tools every pass gets. Write access comes only from the pass's own Edit(...) rules.
COMMON_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    *(
        f"Bash({c}:*)"
        for c in (
            "ls", "cat", "head", "tail", "wc", "grep", "find", "sort", "uniq", "diff", "cd",
            "git status", "git diff", "git log", "git show", "git ls-files", "git rev-parse",
            "python3", "python", "PYTHONPATH=research/warranted_revision/src python3",
        )
    ),
]
#: Never allowed, whatever a pass asks for (deny rules win over allow rules).
DENIED_TOOLS = [
    *(
        f"Bash({c}:*)"
        for c in (
            "git push", "git commit", "git reset", "git checkout", "git switch", "git rebase",
            "git merge", "git stash", "git clean", "git worktree", "git branch", "git tag",
            "git config", "rm", "brev", "gh", "curl", "wget", "ssh", "scp", "sudo", "pip",
            "pip3", "python3 -m pip", "python -m pip", "npm", "claude",
        )
    ),
]
#: Provider credentials removed from the agent's environment.
SCRUB = re.compile(
    r"^(BREV|HF_|HUGGING|GITHUB_TOKEN|GH_TOKEN|CS1684|AWS_|OPENAI|GOOGLE_API|ANTHROPIC_API_KEY)"
)
#: Files tools create as a side effect; never counted as a pass's writes.
IGNORED = ["**/__pycache__/**", "__pycache__/**", "*.pyc", "**/.pytest_cache/**", ".pytest_cache/**",
           f"{STATE_DIR}/**", f"{SMOKE_STATE_DIR}/**", "**/*.egg-info/**"]


# --------------------------------------------------------------------------- helpers


def now() -> float:
    return time.time()


def stamp(t: float | None = None) -> str:
    return dt.datetime.fromtimestamp(t or now()).strftime("%Y-%m-%d %H:%M:%S")


def sh(args: list[str], cwd: Path, check: bool = True, timeout: float | None = 120) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def match(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def changed_paths(wt: Path) -> list[str]:
    out = sh(["git", "status", "--porcelain=v1", "-uall", "--no-renames"], wt)
    paths = [line[3:].strip().strip('"') for line in out.splitlines() if line.strip()]
    return [p for p in paths if not match(p, IGNORED)]


def agent_env(keep_api_key: bool, pass_id: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not SCRUB.match(k)}
    if keep_api_key and "ANTHROPIC_API_KEY" in os.environ:
        env["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]
    env["OVERNIGHT_PASS"] = pass_id
    # Return the agent's shell to the project root after every command.
    env["CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"] = "1"
    return env


class Runner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.a = args
        self.wt = Path(args.worktree).resolve()
        self.sd = self.wt / (SMOKE_STATE_DIR if args.smoke else STATE_DIR)
        self.state_path = self.sd / "state.json"
        self.child: subprocess.Popen[str] | None = None

    # ----------------------------------------------------------------- setup

    def setup(self) -> None:
        repo = Path(self.a.repo).resolve()
        if not (self.wt / ".git").exists():
            base = self.a.base or sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
            branch = self.a.branch or f"overnight/{dt.datetime.now():%Y%m%d-%H%M}"
            sh(["git", "worktree", "add", "-b", branch, str(self.wt), base], repo)
            print(f"[runner] worktree {self.wt} on new branch {branch} from {base}")
        self.sd.mkdir(parents=True, exist_ok=True)
        (self.sd / "logs").mkdir(exist_ok=True)
        exclude = Path(sh(["git", "rev-parse", "--git-path", "info/exclude"], self.wt).strip())
        exclude = exclude if exclude.is_absolute() else self.wt / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text() if exclude.exists() else ""
        for d in (STATE_DIR, SMOKE_STATE_DIR):
            if f"/{d}/" not in text:
                text += f"\n/{d}/\n"
        exclude.write_text(text)
        cfg = json.loads((self.wt / "scripts/overnight/passes.json").read_text())
        self.cfg = cfg
        self.queue = cfg["smoke"] if self.a.smoke else cfg["passes"]
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
            print(f"[runner] resuming run started {self.state['started']}")
        else:
            self.state = {
                "started": stamp(),
                "deadline": now() + self.a.hours * 3600,
                "branch": sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], self.wt).strip(),
                "base_commit": sh(["git", "rev-parse", "HEAD"], self.wt).strip(),
                "smoke": self.a.smoke,
                "passes": {p["id"]: {"status": "pending", "attempts": []} for p in self.queue},
            }
        if self.a.hours_extend:
            self.state["deadline"] = now() + self.a.hours * 3600
        self.save()

    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=1))
        (self.sd / "RUN_STATUS.md").write_text(self.status_md())

    def preflight(self) -> None:
        pid_file = self.sd / "runner.pid"
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), 0)
                raise SystemExit(f"[runner] another runner (pid {pid_file.read_text()}) is active")
            except (ProcessLookupError, ValueError):
                pass
        pid_file.write_text(str(os.getpid()))
        if not shutil.which(self.a.claude.split()[0]):
            raise SystemExit(f"[runner] `{self.a.claude}` not found on PATH")
        for key in ("user.name", "user.email"):
            if not sh(["git", "config", key], self.wt, check=False).strip():
                raise SystemExit(f"[runner] git {key} is not set; the runner commits each pass")
        dirty = changed_paths(self.wt)
        if dirty:
            # Leftovers of an interrupted pass: keep them, out of the way.
            self.stash("leftover changes found at start", dirty)
        if not self.a.skip_auth_check:
            out = self.claude("Reply with exactly the word OK.", "auth_check", [], 2, 180)
            if out.get("is_error") or "OK" not in str(out.get("result", "")):
                raise SystemExit(f"[runner] Claude Code is not usable headless: {out}")
            print("[runner] Claude Code login works headless")

    # ----------------------------------------------------------------- one pass

    def tools_for(self, p: dict[str, Any]) -> tuple[list[str], list[str]]:
        # Edit rules are anchored to the worktree's absolute path ("//" prefix): a relative rule
        # is resolved against the session's current directory, so after `cd sub && ...` an
        # allowed write was refused and a protected path could slip past a relative deny rule
        # (found by the real smoke run).
        root = f"/{self.wt}"
        allowed = COMMON_TOOLS + list(p.get("tools", [])) + [f"Edit({root}/{g})" for g in p["writes"]]
        denied = DENIED_TOOLS + [f"Edit({root}/{g})" for g in self.cfg["protected"]]
        return allowed, denied

    def claude(
        self, prompt: str, pass_id: str, allowed: list[str], max_turns: int, timeout_s: float,
        denied: list[str] | None = None,
    ) -> dict[str, Any]:
        cmd = [
            *shlex.split(self.a.claude), "-p", "--output-format", "json",
            "--max-turns", str(max_turns), "--permission-mode", "dontAsk", "--strict-mcp-config",
        ]
        if allowed:
            cmd += ["--allowedTools", *allowed]
        cmd += ["--disallowedTools", *(denied or DENIED_TOOLS)]
        if self.a.model:
            cmd += ["--model", self.a.model]
        if self.a.max_budget_usd:
            cmd += ["--max-budget-usd", str(self.a.max_budget_usd)]
        if self.a.no_session_persistence:
            cmd += ["--no-session-persistence"]
        log = self.sd / "logs" / f"{pass_id}-{int(now())}"
        log.with_suffix(".cmd.json").write_text(json.dumps(cmd, indent=1))
        t0 = now()
        self.child = subprocess.Popen(
            cmd, cwd=self.wt, env=agent_env(self.a.keep_api_key, pass_id), text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out, err = self.child.communicate(prompt, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(self.child.pid, signal.SIGTERM)
            try:
                out, err = self.child.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.child.pid, signal.SIGKILL)
                out, err = self.child.communicate()
            res = {"is_error": True, "subtype": "runner_timeout", "result": f"timed out after {timeout_s:.0f} s"}
        else:
            try:
                res = json.loads(out)
            except json.JSONDecodeError:
                res = {"is_error": True, "subtype": "bad_output", "result": (out or "")[-2000:]}
            if self.child.returncode != 0 and not res.get("is_error"):
                res["is_error"] = True
                res.setdefault("subtype", f"exit_{self.child.returncode}")
        finally:
            self.child = None
        res["elapsed_s"] = round(now() - t0, 1)
        log.with_suffix(".out.json").write_text(json.dumps(res, indent=1))
        log.with_suffix(".stderr.txt").write_text(err or "")
        return res

    def prompt_for(self, p: dict[str, Any], note: str | None) -> str:
        common = (self.wt / "scripts/overnight/prompts/common.md").read_text()
        body = (self.wt / "scripts/overnight" / p["prompt"]).read_text()
        writes = "\n".join(f"- `{w}`" for w in p["writes"])
        extra = f"\n\n**You may create or change only:**\n{writes}\n"
        if note:
            extra += f"\n**Retry note:** the previous attempt was rejected: {note}\n"
        return f"{common}\n\n---\n\n{body}{extra}"

    def verify(self, p: dict[str, Any]) -> tuple[bool, bool, list[str], list[str]]:
        """(ok, fatal, problems, changed). Fatal = a protected path changed."""
        problems, fatal = [], False
        changed = changed_paths(self.wt)
        for path in changed:
            if match(path, self.cfg["protected"]):
                problems.append(f"protected path changed: {path}")
                fatal = True
            elif not match(path, p["writes"]):
                problems.append(f"path outside this pass's scope: {path}")
        out = self.wt / p["output"]
        if not out.exists() or out.stat().st_size < 200:
            problems.append(f"output {p['output']} missing or under 200 bytes")
        else:
            text = out.read_text(errors="replace")
            lines = {ln.strip() for ln in text.splitlines()}
            missing = [h for h in p["headings"] if h not in lines]
            if missing:
                problems.append(f"missing headings: {missing}")
            if p.get("verdict_line"):
                last = [ln.strip() for ln in text.splitlines() if ln.strip()][-1:]
                if last not in (["VERDICT: GO"], ["VERDICT: NO-GO"], ["VERDICT: INCONCLUSIVE"]):
                    problems.append("last line is not VERDICT: GO / NO-GO / INCONCLUSIVE")
        for path in p.get("must_not_exist", []):
            if (self.wt / path).exists():
                problems.append(f"{path} exists but must not")
        for check in p.get("checks", []):
            if check == "amendment_if_relocked":
                lock = "research/warranted_revision/configs/decision_procedure_lock.json"
                if lock in changed and not any(match(c, ["docs/PREREG_AMENDMENT_*.md"]) for c in changed):
                    problems.append("the lock was rewritten without a docs/PREREG_AMENDMENT_*.md")
                continue
            cmd = self.cfg["check_commands"][check]
            r = subprocess.run(cmd, shell=True, cwd=self.wt, capture_output=True, text=True,
                               timeout=1800, env=agent_env(False, p["id"]))
            (self.sd / "logs" / f"{p['id']}-check-{check}.txt").write_text(r.stdout + r.stderr)
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                problems.append(f"check {check} failed: {' | '.join(tail)}")
        return not problems, fatal, problems, changed

    def stash(self, why: str, changed: list[str]) -> str | None:
        if not changed:
            return None
        patch = self.sd / "logs" / f"rejected-{int(now())}.patch"
        diff = sh(["git", "diff", "HEAD"], self.wt, check=False)
        untracked = sh(["git", "ls-files", "--others", "--exclude-standard"], self.wt, check=False)
        patch.write_text(f"# {why}\n# untracked:\n{untracked}\n{diff}")
        sh(["git", "stash", "push", "-u", "-m", f"overnight: {why}"], self.wt)
        return str(patch)

    def run_pass(self, p: dict[str, Any], reserve_s: float) -> None:
        st = self.state["passes"][p["id"]]
        note = None
        while len(st["attempts"]) < MAX_ATTEMPTS + (1 if st.get("rate_limited") else 0):
            left = self.state["deadline"] - now() - reserve_s
            if left < 5 * 60:
                st["status"] = "skipped_deadline"
                self.save()
                return
            timeout_s = min(p["timeout_min"] * 60, left)
            allowed, denied = self.tools_for(p)
            print(f"[runner] {stamp()} pass {p['id']} attempt {len(st['attempts']) + 1} "
                  f"(timeout {timeout_s / 60:.0f} min, max {p['max_turns']} turns)", flush=True)
            st["status"] = "running"
            self.save()
            hidden = self.hide(p)
            try:
                res = self.claude(self.prompt_for(p, note), p["id"], allowed, p["max_turns"], timeout_s, denied)
            finally:
                self.unhide(hidden)
            ok, fatal, problems, changed = self.verify(p)
            if res.get("is_error"):
                problems.insert(0, f"claude: {res.get('subtype')}: {str(res.get('result'))[:300]}")
                ok = False
            att = {
                "started": stamp(now() - res.get("elapsed_s", 0)), "elapsed_s": res.get("elapsed_s"),
                "subtype": res.get("subtype"), "turns": res.get("num_turns"),
                "cost_usd_reported": res.get("total_cost_usd"), "session_id": res.get("session_id"),
                "denials": len(res.get("permission_denials") or []), "problems": problems,
            }
            st["attempts"].append(att)
            if ok:
                sh(["git", "add", "-A", "--", *changed], self.wt)
                sh(["git", "commit", "-q", "-m", f"overnight {p['id']}: {Path(p['output']).name}",
                    "-m", "Written by an unattended overnight pass; verified by scripts/overnight/overnight.py."],
                   self.wt)
                st["status"] = "done"
                st["commit"] = sh(["git", "rev-parse", "--short", "HEAD"], self.wt).strip()
                self.save()
                print(f"[runner] pass {p['id']} done: {st['commit']}", flush=True)
                return
            att["stashed_patch"] = self.stash(f"rejected {p['id']} attempt {len(st['attempts'])}", changed_paths(self.wt))
            print(f"[runner] pass {p['id']} rejected: {problems}", flush=True)
            if fatal:
                st["status"] = "failed_protected"
                self.state["stopped"] = f"{p['id']} changed a protected path"
                self.save()
                return
            if res.get("is_error") and RATE_LIMIT.search(str(res.get("result", ""))) and not st.get("rate_limited"):
                st["rate_limited"] = True
                wait = min(RATE_LIMIT_WAIT_S, max(0.0, self.state["deadline"] - now() - reserve_s - 10 * 60))
                print(f"[runner] usage/rate limit; waiting {wait / 60:.0f} min", flush=True)
                self.save()
                time.sleep(wait)
            note = "; ".join(problems)[:1500]
            self.save()
        st["status"] = "failed"
        self.save()

    def hide(self, p: dict[str, Any]) -> list[tuple[Path, Path]]:
        """Move files this pass must not see (for independence) out of the worktree."""
        moved = []
        for rel in p.get("hide", []):
            src = self.wt / rel
            if src.exists():
                dst = self.sd / "hidden" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), dst)
                moved.append((src, dst))
        return moved

    def unhide(self, moved: list[tuple[Path, Path]]) -> None:
        for src, dst in moved:
            if src.exists():  # the agent recreated it: keep the agent's copy for the record
                shutil.move(str(src), self.sd / "logs" / f"recreated-{src.name}")
            shutil.move(str(dst), src)

    # ----------------------------------------------------------------- queue

    def run(self) -> int:
        self.setup()
        self.preflight()
        signal.signal(signal.SIGTERM, self.interrupt)
        signal.signal(signal.SIGINT, self.interrupt)
        try:
            brief = [p for p in self.queue if p.get("always_run")]
            reserve = sum(p["timeout_min"] * 60 for p in brief)
            for p in self.queue:
                st = self.state["passes"][p["id"]]
                if st["status"] in ("done", "failed", "failed_protected", "skipped_deadline", "skipped_dependency"):
                    continue
                if p.get("always_run"):
                    reserve = 0
                elif self.state.get("stopped"):
                    st["status"] = "skipped_stopped"
                    continue
                missing = [r for r in p.get("requires", []) if self.state["passes"].get(r, {}).get("status") != "done"]
                if missing:
                    st["status"] = "skipped_dependency"
                    st["why"] = f"requires {missing}"
                    self.save()
                    continue
                self.run_pass(p, reserve)
            for p in brief:
                if self.state["passes"][p["id"]]["status"] != "done":
                    self.fallback_brief(p)
        finally:
            (self.sd / "runner.pid").unlink(missing_ok=True)
            self.state["finished"] = stamp()
            self.save()
        if not self.a.smoke:
            self.commit_status()
        print(self.status_md())
        return 0 if all(s["status"] == "done" for s in self.state["passes"].values()) else 1

    def interrupt(self, signum: int, _frame: Any) -> None:
        if self.child is not None:
            try:
                os.killpg(self.child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for st in self.state["passes"].values():
            if st["status"] == "running":
                st["status"] = "pending"  # resume repeats it; its partial changes get stashed
        self.state["interrupted"] = stamp()
        self.save()
        (self.sd / "runner.pid").unlink(missing_ok=True)
        raise SystemExit(f"[runner] interrupted (signal {signum}); rerun the same command to resume")

    def fallback_brief(self, p: dict[str, Any]) -> None:
        """The brief pass failed: write a plain status brief so the morning still has one."""
        out = self.wt / p["output"]
        out.parent.mkdir(parents=True, exist_ok=True)
        heads = p["headings"]
        body = {
            heads[0]: self.status_md(),
            heads[4]: "The morning-brief pass did not complete, so this brief was written by the "
                      "runner from its own records. It contains no research judgement.",
            heads[-1]: "Not assessed: the brief pass failed.",
        }
        text = "# Morning brief (runner fallback)\n\n" + "\n\n".join(
            f"{h}\n\n{body.get(h, 'See section 1 and the pass reports in docs/overnight/.')}" for h in heads
        ) + "\n\nVERDICT: INCONCLUSIVE\n"
        out.write_text(text)
        sh(["git", "add", "--", p["output"]], self.wt)
        sh(["git", "commit", "-q", "-m", "overnight: runner fallback brief (brief pass failed)"], self.wt)
        self.state["passes"][p["id"]]["fallback"] = True

    def commit_status(self) -> None:
        dst = self.wt / "docs/overnight/RUN_STATUS.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(self.status_md())
        sh(["git", "add", "--", "docs/overnight/RUN_STATUS.md"], self.wt)
        if sh(["git", "diff", "--cached", "--name-only"], self.wt).strip():
            sh(["git", "commit", "-q", "-m", "overnight: run status"], self.wt)

    def status_md(self) -> str:
        s = self.state
        rows = []
        for pid, st in s["passes"].items():
            last = st["attempts"][-1] if st["attempts"] else {}
            rows.append(
                f"| {pid} | {st['status']}{' (runner fallback)' if st.get('fallback') else ''} | "
                f"{len(st['attempts'])} | {last.get('turns', '')} | {last.get('elapsed_s', '')} | "
                f"{st.get('commit', '')} | {'; '.join(last.get('problems', []))[:300]} |"
            )
        dl = stamp(s["deadline"]) if isinstance(s.get("deadline"), (int, float)) else s.get("deadline")
        return (
            "# Overnight run status (written by the runner)\n\n"
            f"- branch `{s.get('branch')}`, base commit `{str(s.get('base_commit', ''))[:10]}`\n"
            f"- started {s.get('started')}, deadline {dl}, finished {s.get('finished', '-')}\n"
            f"- stopped early: {s.get('stopped', 'no')}; interrupted: {s.get('interrupted', 'no')}\n"
            "- no GPU, Brev or paid API call is made by the runner; provider credentials are removed "
            "from the agent environment\n\n"
            "| pass | status | attempts | turns (last) | seconds (last) | commit | problems (last attempt) |\n"
            "|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--repo", default=".")
    r.add_argument("--worktree", help="default: <repo>/../<repo name>-overnight")
    r.add_argument("--base", help="branch or commit to start from (default: the repo's current branch)")
    r.add_argument("--branch", help="new branch for the run (default: overnight/<date-time>)")
    r.add_argument("--hours", type=float, default=8.0, help="wall-clock deadline for the whole run")
    r.add_argument("--hours-extend", action="store_true", help="on resume, reset the deadline to now + --hours")
    r.add_argument("--smoke", action="store_true", help="run only the short read-only smoke pass")
    r.add_argument("--claude", default="claude", help="Claude Code command")
    r.add_argument("--model", help="model for every pass (default: the CLI's default)")
    r.add_argument("--max-budget-usd", type=float, help="per-pass cap; applies only to API billing")
    r.add_argument("--keep-api-key", action="store_true")
    r.add_argument("--no-session-persistence", action="store_true")
    r.add_argument("--skip-auth-check", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("--worktree", required=True)
    s.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        p = Path(a.worktree) / (SMOKE_STATE_DIR if a.smoke else STATE_DIR) / "RUN_STATUS.md"
        print(p.read_text() if p.exists() else f"no run state at {p}")
        return 0
    repo = Path(sh(["git", "rev-parse", "--show-toplevel"], Path(a.repo)).strip())
    a.repo = str(repo)
    a.worktree = a.worktree or str(repo.parent / f"{repo.name}-overnight{'-smoke' if a.smoke else ''}")
    return Runner(a).run()


if __name__ == "__main__":
    sys.exit(main())
