"""Launch checks for the goal-screen API job (``.github/workflows/warranted-revision-goal-screen-api.yml``).

No model is called here. Usage (from ``research/warranted_revision``)::

    python -m warranted_revision.goal_screen_job check --config configs/goal_screen_sonnet.json \\
        --mode dry-run|preflight|full --approve-usd 8 [--preflight-dir DIR]
    python -m warranted_revision.goal_screen_job summarize --run DIR    # cost and validity only
    python -m warranted_revision.goal_screen_job lock                   # pre-run only

``check`` refuses unless:

* the config is on the allowlist, for the allowlisted model, with the approved cap;
* for a paid mode, ``--approve-usd`` equals that cap (a typed confirmation);
* every frozen file (items, manifests, prompts, runner, analysis, this module, the config)
  matches ``screen_v1/LAUNCH_LOCK.json``;
* for ``full``, a preflight from the same frozen inputs is supplied, made all its planned calls,
  had no API errors, at most 10% unparseable answers, did not stop, and projects the full run
  (with a 25% margin) under the cap.

``summarize`` reports counts only (tokens, cost, stop reasons, parse status, refusals, errors);
it never prints model text, so a preflight can be checked without reading its answers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from . import goal_screen as gs
from .runner import PKG_ROOT

LOCK = "v2/ai_precalibration/screen_v1/LAUNCH_LOCK.json"
#: The only API configs this job may run, and the spend each one was approved for.
ALLOWED = {"configs/goal_screen_sonnet.json": {"model": "claude-sonnet-5-5", "max_usd": 8.0}}
FROZEN = [
    "v2/ai_precalibration/candidate_v3/items.json",
    "v2/ai_precalibration/screen_v1/run_manifest.json",
    "v2/ai_precalibration/screen_v1/primary.json",
    "v2/ai_precalibration/screen_v1/system_prompts.json",
    "src/warranted_revision/goal_screen.py",
    "src/warranted_revision/goal_screen_analysis.py",
    "src/warranted_revision/goal_screen_job.py",
    "configs/goal_screen_sonnet.json",
    "configs/goal_screen_qwen.json",
    "configs/goal_screen_mistral_nemo.json",
]
MAX_PREFLIGHT_INVALID = 0.10
#: API configs withdrawn after approval; ``check`` refuses them before anything else.
CANCELLED = {
    "configs/goal_screen_sonnet.json": "Sonnet replaced by an open-weights model "
    "(screen_v1/AMENDMENT_2_OPEN_WEIGHTS.md); no API key is used",
}
#: The on-box gate starts the full run only if its projected runtime, times this margin,
#: fits in the minutes left before the controller's deadline.
RUNTIME_MARGIN = 1.5


class LaunchError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_lock(root: Path = PKG_ROOT) -> dict[str, str]:
    lock = {f: sha(root / f) for f in FROZEN}
    (root / LOCK).write_text(json.dumps(lock, indent=1) + "\n")
    return lock


def check_lock(root: Path = PKG_ROOT) -> None:
    lock = json.loads((root / LOCK).read_text())
    bad = [f for f in FROZEN if lock.get(f) != sha(root / f)]
    if bad:
        raise LaunchError(f"frozen files differ from {LOCK}: {bad}")


def _rows(run: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (run / "calls.jsonl").read_text().splitlines() if x.strip()]


def allowed_codes(cfg: dict[str, Any], root: Path = PKG_ROOT) -> dict[str, list[str]]:
    """The option codes offered in each scenario, keyed by base id, item id and control id."""
    items, controls = gs.load_screen_items(root / cfg["items"], root / cfg["manifest"])
    codes: dict[str, list[str]] = {}
    for it in items:
        offered = [o["code"] for o in it.base["options"]]
        codes[it.base["base_id"]] = codes[it.item_id] = offered
    for c in controls:
        codes[c.control_id] = [o["code"] for o in c.scenario["options"]]
    return codes


def summarize(run: Path, root: Path = PKG_ROOT) -> dict[str, Any]:
    """Counts only; no model text. A RESPONSE line is valid only if it is well formed and names
    options actually offered in that call's scenario; whether the choice is right is not
    examined here."""
    man = json.loads((run / "manifest.json").read_text())
    rows = _rows(run)
    codes = allowed_codes(man["config"], root)
    parse: Counter[str] = Counter()
    by_kind: dict[str, Counter[str]] = {}
    for r in rows:
        if r["kind"] == "free":
            continue
        key = r["base_id"] if r["kind"] == "first" else r["item_id"]
        status = gs.parse_response(r["text"], codes[key])["status"]
        parse[status] += 1
        kind = r["kind"].split("_")[0]
        by_kind.setdefault(kind, Counter())[status] += 1
    return {
        "run_id": man["run_id"],
        "preflight": man["preflight"],
        "system": man["system"],
        "expected_calls": man["expected_calls"],
        "actual_calls": man["actual_calls"],
        "stopped": man["stopped"],
        "spend_usd": man["spend_usd"],
        "input_tokens": sum(r["input_tokens"] or 0 for r in rows),
        "output_tokens": sum(r["output_tokens"] or 0 for r in rows),
        "stop_reasons": dict(Counter(str(r["stop_reason"]) for r in rows)),
        "refusals": sum(bool(r["refused"]) for r in rows),
        "errors": sum(bool(r["error"]) for r in rows),
        "error_types": dict(Counter(str(r["error"]).split(":")[0] for r in rows if r["error"])),
        "response_line": dict(parse),
        "response_line_by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
        "preflight_projection": man.get("preflight_projection"),
    }


def gate(run: Path, remaining_min: float, root: Path = PKG_ROOT) -> dict[str, Any]:
    """On-box preflight gate for an open-weights run: the full run starts only if the preflight
    made every planned call, had no errors, at most 10% unparseable answers, did not stop, and
    its measured time per batch projects the full run (times RUNTIME_MARGIN) within the minutes
    left. Raises LaunchError otherwise, so an over-long run is reported, not cut short."""
    man = json.loads((run / "manifest.json").read_text())
    s = summarize(run, root)
    cfg = gs.ScreenConfig.model_validate(man["config"])
    items, controls = gs.load_screen_items(root / cfg.items, root / cfg.manifest)
    full_batches = gs.plan_batches(cfg, items, controls)
    per_batch = man["elapsed_s"] / max(1, man["planned_batches"])
    projected_min = per_batch * full_batches / 60
    s.update(
        {
            "seconds_per_batch": round(per_batch, 1),
            "full_run_batches": full_batches,
            "projected_full_run_min": round(projected_min, 1),
            "remaining_min": round(remaining_min, 1),
        }
    )
    problems = [
        msg
        for bad, msg in [
            (s["stopped"], f"stopped: {s['stopped']}"),
            (s["actual_calls"] != s["expected_calls"], "did not make all planned calls"),
            (s["errors"] > 0, f"{s['errors']} errors {s['error_types']}"),
            (
                s["response_line"].get("invalid", 0) > MAX_PREFLIGHT_INVALID * s["actual_calls"],
                f"too many unparseable answers {s['response_line']}",
            ),
            (
                remaining_min < 2,
                f"only {remaining_min:.0f} min left before the deadline (and `timeout 0` would "
                "mean no limit)",
            ),
            (
                projected_min * RUNTIME_MARGIN > remaining_min,
                f"projected {projected_min:.0f} min x {RUNTIME_MARGIN} exceeds the "
                f"{remaining_min:.0f} min left before the deadline",
            ),
        ]
        if bad
    ]
    s["gate_passed"] = not problems
    s["gate_problems"] = problems
    (run / "gate.json").write_text(json.dumps(s, indent=1) + "\n")
    if problems:
        raise LaunchError("preflight gate failed: " + "; ".join(problems))
    return s


def check(
    config: str,
    mode: str,
    approve_usd: float,
    preflight_dir: Path | None = None,
    root: Path = PKG_ROOT,
) -> dict[str, Any]:
    if config in CANCELLED:
        raise LaunchError(f"{config} is cancelled: {CANCELLED[config]}")
    if config not in ALLOWED:
        raise LaunchError(f"{config} is not an approved API config: {sorted(ALLOWED)}")
    want = ALLOWED[config]
    cfg = gs.load_config(root / config)
    if cfg.system.kind != "anthropic" or cfg.system.name != want["model"]:
        raise LaunchError(f"config system {cfg.system.kind}:{cfg.system.name} != {want['model']}")
    if cfg.budget is None or cfg.budget.max_usd != want["max_usd"]:
        raise LaunchError(f"config cap must be ${want['max_usd']}")
    if mode != "dry-run" and approve_usd != want["max_usd"]:
        raise LaunchError(f"--approve-usd must equal the approved cap {want['max_usd']}")
    check_lock(root)
    items, controls = gs.load_screen_items(root / cfg.items, root / cfg.manifest)
    plan: dict[str, Any] = {
        "full_calls": gs.plan_calls(cfg, items, controls)["total"],
        "preflight_calls": gs.preflight_plan(cfg, items, controls),
        "full_cap_usd": cfg.budget.max_usd,
        "preflight_cap_usd": min(cfg.budget.max_usd, cfg.preflight_max_usd),
    }
    if mode == "full":
        if preflight_dir is None:
            raise LaunchError("a full run needs the approved preflight (--preflight-dir)")
        mans = list(preflight_dir.rglob("manifest.json"))
        if len(mans) != 1:
            raise LaunchError(
                f"expected one preflight manifest under {preflight_dir}, found {len(mans)}"
            )
        pre = mans[0].parent
        pm = json.loads(mans[0].read_text())
        s = summarize(pre, root)
        current = {
            "items_sha256": sha(root / cfg.items),
            "manifest_sha256": sha(root / cfg.manifest),
            "system_prompts_sha256": {
                k: hashlib.sha256(v.encode()).hexdigest() for k, v in gs.SYSTEM_PROMPTS.items()
            },
        }
        same_cfg = {**pm["config"], "run_id": None} == {**cfg.model_dump(), "run_id": None}
        problems = [
            msg
            for bad, msg in [
                (not pm.get("preflight"), "not a preflight"),
                (pm.get("synthetic"), "made with a synthetic backend"),
                (not same_cfg, "config differs from the current config"),
                (any(pm.get(k) != v for k, v in current.items()), "frozen inputs differ"),
                (pm.get("stopped"), f"stopped: {pm.get('stopped')}"),
                (pm["actual_calls"] != pm["expected_calls"], "did not make all planned calls"),
                (s["errors"] > 0, f"{s['errors']} API errors {s['error_types']}"),
                (
                    s["response_line"].get("invalid", 0)
                    > MAX_PREFLIGHT_INVALID * pm["actual_calls"],
                    f"too many unparseable answers {s['response_line']}",
                ),
                (
                    not (pm.get("preflight_projection") or {}).get("proceed"),
                    "projection over the cap",
                ),
            ]
            if bad
        ]
        if problems:
            raise LaunchError("preflight not acceptable: " + "; ".join(problems))
        plan["preflight"] = s
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--config", required=True)
    c.add_argument("--mode", choices=["dry-run", "preflight", "full"], required=True)
    c.add_argument("--approve-usd", type=float, default=0.0)
    c.add_argument("--preflight-dir", type=Path)
    s = sub.add_parser("summarize")
    s.add_argument("--run", type=Path, required=True)
    sub.add_parser("lock")
    g = sub.add_parser("gate")
    g.add_argument("--run", type=Path, required=True)
    g.add_argument("--remaining-min", type=float, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "gate":
        try:
            res = gate(args.run, args.remaining_min)
        except LaunchError as exc:
            print(f"[gate] FAILED: {exc}", file=sys.stderr)
            return 3
        print("[gate] OK " + json.dumps(res))
        return 0
    if args.cmd == "lock":
        print(json.dumps(write_lock(), indent=1))
        return 0
    if args.cmd == "summarize":
        out = summarize(args.run)
        (args.run / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps(out, indent=1))
        return 0
    try:
        plan = check(args.config, args.mode, args.approve_usd, args.preflight_dir)
    except LaunchError as exc:
        print(f"[launch] REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"[launch] OK mode={args.mode} " + json.dumps(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
