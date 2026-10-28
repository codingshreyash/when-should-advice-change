#!/usr/bin/env python3
"""Independent controller for one bounded Brev GPU smoke run.

Runs on a machine that is *not* the GPU instance (intended: the manual GitHub Actions
workflow ``.github/workflows/warranted-revision-gpu-smoke.yml``), so that stopping and
deleting the instance does not depend on the instance itself.

Subcommands::

    plan     --hourly 0.85 --max-usd 15 --run-id X     # dry run: budget, name, commands; no network
    launch   --hourly 0.85 --max-usd 15 --run-id X --instance-type T --commands-verified
    cleanup  --state STATE.json                        # idempotent delete of the recorded instance

Safety properties:

* ``plan`` and the guard checks run before any provider call; nothing is created on refusal.
* The instance name is generated here (``wrev-smoke-<run>-<hex>``) and written to the state
  file *before* creation; ``cleanup`` only ever deletes a name matching that pattern, so it
  cannot touch unrelated resources.
* ``launch`` deletes the instance in a ``finally`` block after copying results back, and the
  workflow runs ``cleanup`` again in an ``if: always()`` step (covers cancellation/timeouts).
* Every step gets a timeout derived from the remaining budget.

Brev CLI flags were NOT verified against the official documentation from the environment that
wrote this file (the docs host was unreachable). ``brev_commands.json`` holds every command
template; ``launch`` refuses to run until a person has checked them with ``brev <cmd> --help``
and passes ``--commands-verified``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent  # research/warranted_revision
sys.path.insert(0, str(PKG / "src"))

from warranted_revision.gpu_guard import (  # noqa: E402
    GuardError,
    check_instance_name,
    check_instance_type,
    check_pinned_model,
    instance_name,
    plan_budget,
)
from warranted_revision.runner import (  # noqa: E402
    RunConfig,
    expected_calls,
    load_cases,
    shard_cases,
)

COMMANDS = json.loads((HERE / "brev_commands.json").read_text())


def render(key: str, **kw: str) -> list[str]:
    return [part.format(**kw) for part in COMMANDS[key]["argv"]]


#: Configs whose experiment was cancelled. They are kept unchanged as a record, and the
#: controller refuses them (matched on the file's sha256, so a renamed copy is refused too).
CANCELLED_CONFIGS = {
    "configs/pilot_challenge.json": "challenge_v1 pilot, cancelled 2026-10-25 after the research review",
}


def _cancelled_reason(path: Path) -> str | None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for rel, why in CANCELLED_CONFIGS.items():
        ref = PKG / rel
        if ref.exists() and hashlib.sha256(ref.read_bytes()).hexdigest() == digest:
            return why
    return None


def build_plan(args: argparse.Namespace) -> dict:
    why = _cancelled_reason(Path(args.config))
    if why:
        raise GuardError(f"config is cancelled: {why}")
    raw = json.loads(Path(args.config).read_text())
    raw["run_id"] = args.run_id
    raw["shard"] = args.shard
    check_pinned_model(raw)
    extra_calls = 0  # calls made on the box besides the planned run (the goal screen preflight)
    if raw.get("experiment") == "scaffold_probe":
        from warranted_revision import scaffold_probe

        pcfg = scaffold_probe.ProbeConfig.model_validate(raw)
        scaffold_probe.validate_plan(pcfg)
        n_calls, max_calls = scaffold_probe.expected_calls(pcfg), pcfg.max_calls
    elif raw.get("experiment") == "goal_screen":
        from warranted_revision import goal_screen

        gcfg = goal_screen.ScreenConfig.model_validate(raw)
        if gcfg.system.kind != "hf":
            raise GuardError("the GPU controller runs open-weights (hf) goal screens only")
        items, controls = goal_screen.load_screen_items(
            goal_screen.PKG_ROOT / gcfg.items, goal_screen.PKG_ROOT / gcfg.manifest
        )
        n_calls, max_calls = goal_screen.plan_calls(gcfg, items, controls)["total"], gcfg.max_calls
        extra_calls = goal_screen.preflight_plan(gcfg, items, controls)
    else:
        cfg = RunConfig.model_validate(raw)
        n_calls, max_calls = expected_calls(cfg, shard_cases(cfg, load_cases(cfg))), cfg.max_calls
    if max_calls is not None and n_calls > max_calls:
        raise GuardError(f"plan needs {n_calls} calls > max_calls {max_calls}")
    budget = plan_budget(
        args.hourly,
        args.max_usd,
        expected_calls=n_calls + extra_calls,
        est_seconds_per_call=args.est_seconds_per_call,
        # The optional benchmark runs before the experiment; reserve time for it.
        setup_hours=args.setup_hours + (0.25 if args.bench else 0.0),
    )
    if args.instance_type:
        check_instance_type(args.instance_type)
    name = instance_name(args.run_id)
    return {
        "run_id": args.run_id,
        "shard": args.shard,
        "bench": bool(args.bench),
        "instance": name,
        "instance_type": args.instance_type,
        "budget": budget.as_dict(),
        "config": raw,
        "created": False,
        "deleted": False,
        "commands": {
            k: render(
                k,
                name=name,
                instance_type=args.instance_type or "<type>",
                token="***",
                remote_cmd="<remote>",
                src="<src>",
                dst="<dst>",
            )
            for k in COMMANDS
            if not k.startswith("_")
        },
    }


#: What the GPU box receives. ``v2`` holds the goal screen's frozen items, manifests and
#: prompts (format-002 and the first goal-screen launch both failed on files left out);
#: tests/test_gpu_guard.py runs the suite and the goal-screen dry run from a real bundle.
BUNDLE = ("pyproject.toml", "PROTOCOL.md", "src", "configs", "data", "gpu", "tests", "v2")


def write_bundle(path: Path, config: Path) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for sub in BUNDLE:
            tar.add(PKG / sub, arcname=f"warranted_revision/{sub}")
        # The exact config the plan was checked against.
        tar.add(config, arcname="warranted_revision/configs/_launch_config.json")
    return path


def listed_hourly(search_output: str, instance_type: str) -> float | None:
    """Hourly price of exactly ``instance_type`` from `brev search gpu` (TYPE first, $/HR last)."""
    for line in search_output.splitlines():
        cols = line.split()
        if cols and cols[0] == instance_type and cols[-1].startswith("$"):
            try:
                return float(cols[-1].lstrip("$"))
            except ValueError:
                return None
    return None


def accepted_types(dry_run_output: str) -> set[str]:
    """Parse `brev create --dry-run` output: 'type (NNNGB disk), type (NNNGB disk), ...'."""
    return set(re.findall(r"([^\s,()]+) \(\d+GB disk\)", dry_run_output))


def run_step(
    argv: list[str], timeout_s: float, *, secret: str | None = None
) -> subprocess.CompletedProcess:
    shown = " ".join(shlex.quote(a if a != secret else "***") for a in argv)
    print(f"[controller] $ {shown}  (timeout {timeout_s:.0f}s)", flush=True)
    return subprocess.run(
        argv, timeout=max(timeout_s, 1), check=True, text=True, capture_output=False
    )


def cmd_plan(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    print(json.dumps({k: v for k, v in plan.items() if k != "config"}, indent=2))
    if args.state:
        Path(args.state).write_text(json.dumps(plan, indent=2))
    print("[controller] dry run only: no provider call was made")
    return 0


def delete_instance(name: str, deadline_s: float = 300) -> bool:
    """Delete exactly ``name`` and confirm it no longer appears in the listing."""
    check_instance_name(name)
    try:
        run_step(render("delete", name=name), deadline_s)
    except subprocess.CalledProcessError as exc:
        print(f"[controller] delete returned {exc.returncode}; checking listing", flush=True)
    # Piped `brev ls` prints one instance name per line; match whole lines. Deletion can take
    # a few minutes, so poll for up to ~10 minutes.
    for _ in range(24):
        out = subprocess.run(render("list"), capture_output=True, text=True, timeout=120)
        listed = {ln.strip() for ln in out.stdout.splitlines()}
        if out.returncode == 0 and name not in listed:
            print(f"[controller] confirmed: {name} not listed", flush=True)
            return True
        time.sleep(25)
    print(
        f"[controller] WARNING: {name} still listed; delete it by hand and check billing",
        flush=True,
    )
    return False


def cmd_launch(args: argparse.Namespace) -> int:
    if not args.commands_verified:
        print(
            "[controller] refusing: check brev_commands.json against `brev <cmd> --help`, "
            "then pass --commands-verified"
        )
        return 2
    token = os.environ.get("BREV_API_TOKEN")
    if not token:
        print("[controller] refusing: BREV_API_TOKEN is not set")
        return 2
    if not args.instance_type:
        print("[controller] refusing: --instance-type is required")
        return 2
    plan = build_plan(args)
    state_path = Path(args.state)
    # Keep the instance name the plan step already printed, if it planned this same run.
    if state_path.exists():
        prev = json.loads(state_path.read_text())
        if prev.get("run_id") == args.run_id and not prev.get("created"):
            check_instance_name(prev["instance"])
            plan["instance"] = prev["instance"]
    state_path.write_text(json.dumps(plan, indent=2))  # name recorded before creation
    name = plan["instance"]
    t_end = time.time() + plan["budget"]["permitted_hours"] * 3600
    remaining = lambda: t_end - time.time()  # noqa: E731
    results_local = Path(args.results_dir)
    try:
        run_step(render("login", token=token), 120, secret=token)
        # The caps are computed from --hourly; refuse unless Brev's current listing for this
        # exact type is no higher (read-only, creates nothing).
        search = subprocess.run(render("price"), capture_output=True, text=True, timeout=300)
        listed = listed_hourly(search.stdout, args.instance_type)
        hourly = float(args.hourly)
        print(
            f"[controller] Brev lists {args.instance_type} at ${listed}/h; caps use ${hourly}/h",
            flush=True,
        )
        if listed is None:
            raise GuardError(f"could not read the current price of {args.instance_type!r}")
        if listed > hourly + 1e-9:
            raise GuardError(
                f"{args.instance_type} is listed at ${listed}/h, above the ${hourly}/h "
                "the caps were computed from"
            )
        plan["listed_hourly_usd"] = listed
        # Ask create which types it accepts (creates nothing). `--type X --dry-run` only
        # echoes X back, and create silently applies default filters such as a 500 GB disk
        # minimum, so a type listed by `brev search` can still be rejected.
        check = subprocess.run(
            render("create_check", name=name), capture_output=True, text=True, timeout=300
        )
        accepted = accepted_types(check.stdout)
        if args.instance_type not in accepted:
            raise GuardError(
                f"brev create does not accept {args.instance_type!r}; "
                f"it lists {len(accepted)} types (e.g. {sorted(accepted)[:5]})"
            )
        plan["created"] = True  # set before the call: a timed-out create may still exist
        state_path.write_text(json.dumps(plan, indent=2))
        run_step(
            render("create", name=name, instance_type=args.instance_type), min(1200, remaining())
        )
        run_step(render("refresh"), 120)
        for _ in range(40):  # wait for SSH
            if (
                subprocess.run(render("exec", name=name, remote_cmd="true"), timeout=60).returncode
                == 0
            ):
                break
            time.sleep(20)
        bundle = write_bundle(Path(args.state).with_suffix(".tar.gz"), Path(args.config))
        run_step(render("copy_to", name=name, src=str(bundle), dst="wrev.tar.gz"), 600)
        deadline_min = int(min(plan["budget"]["run_deadline_minutes"], remaining() / 60 - 15))
        if deadline_min <= 5:
            raise GuardError("not enough budget left after setup")
        sha = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=PKG, capture_output=True, text=True
            ).stdout.strip()
            or "unknown"
        )
        remote = (
            f"tar xzf wrev.tar.gz && cd warranted_revision && WREV_GIT_SHA={sha} "
            f"bash gpu/remote_job.sh {shlex.quote(args.run_id)} {deadline_min} "
            f"configs/_launch_config.json {shlex.quote(args.shard)} {1 if args.bench else 0}"
        )
        try:
            run_step(render("exec", name=name, remote_cmd=remote), deadline_min * 60 + 900)
        finally:
            try:
                results_local.mkdir(parents=True, exist_ok=True)
                run_step(
                    render(
                        "copy_from",
                        name=name,
                        src=f"results/warranted_revision/{args.run_id}",
                        dst=str(results_local),
                    ),
                    900,
                )
            except Exception as exc:  # noqa: BLE001 - deletion must still happen
                print(f"[controller] copy-back failed: {exc}", flush=True)
    finally:
        if plan["created"]:
            plan["deleted"] = delete_instance(name)
            state_path.write_text(json.dumps(plan, indent=2))
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    if not state_path.exists():
        print("[controller] no state file: nothing was created")
        return 0
    plan = json.loads(state_path.read_text())
    if not plan.get("created") or plan.get("deleted"):
        print(
            f"[controller] nothing to clean (created={plan.get('created')}, deleted={plan.get('deleted')})"
        )
        return 0
    if args.dry_run:
        print(
            f"[controller] would delete {plan['instance']}: {render('delete', name=plan['instance'])}"
        )
        return 0
    token = os.environ.get("BREV_API_TOKEN")
    if token:
        run_step(render("login", token=token), 120, secret=token)
    plan["deleted"] = delete_instance(plan["instance"])
    state_path.write_text(json.dumps(plan, indent=2))
    return 0 if plan["deleted"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "launch"):
        p = sub.add_parser(name)
        p.add_argument("--hourly", required=True, help="GPU_HOURLY_USD from the launch screen")
        p.add_argument("--max-usd", required=True, help="MAX_GPU_USD, at most 15 for the first run")
        p.add_argument("--run-id", required=True)
        p.add_argument("--config", default=str(PKG / "configs" / "gpu_smoke.json"))
        p.add_argument("--instance-type", default="")
        p.add_argument("--est-seconds-per-call", type=float, default=6.0)
        p.add_argument("--setup-hours", type=float, default=0.5)
        p.add_argument("--shard", default="1/1", help="i/n: run only this slice of the cases")
        p.add_argument("--bench", action="store_true", help="benchmark kernels before the run")
        p.add_argument("--state", default="brev_state.json")
        if name == "launch":
            p.add_argument("--commands-verified", action="store_true")
            p.add_argument(
                "--results-dir",
                default=str(PKG.parents[1] / "results" / "warranted_revision"),
                help="where copied-back results go (default: the repo's results/)",
            )
    c = sub.add_parser("cleanup")
    c.add_argument("--state", default="brev_state.json")
    c.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        return {"plan": cmd_plan, "launch": cmd_launch, "cleanup": cmd_cleanup}[args.cmd](args)
    except GuardError as exc:
        print(f"[controller] refusing: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
