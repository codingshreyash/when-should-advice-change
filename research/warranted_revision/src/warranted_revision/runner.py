"""Run conditions over model-visible cases and write immutable run artifacts.

Usage (from ``research/warranted_revision``)::

    python -m warranted_revision.runner --config configs/synthetic_dev.json [--dry-run]

The runner reads the ``*_inputs.jsonl`` file only. It never opens a gold file, except
when a run explicitly includes a privileged ``control`` system, whose rows are labelled
``control:*`` and whose manifest entry says ``privileged: true``. Outputs go to
``<out_root>/<run_id>/``; an existing run directory is never overwritten.

Before any call the runner prints the exact number of model calls the run will make and,
for GPU runs, refuses to start if that exceeds ``max_calls``. After the run it checks the
number of calls actually made against the plan and exits non-zero on a mismatch.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from . import prompts as P
from .backends.base import Backend
from .conditions import RUNNERS, ConditionConfig, TurnInput, TurnResult
from .schema import (
    CallRecord,
    ConditionName,
    DecisionRecord,
    Manifest,
    SearchTrace,
    Split,
    VisibleCase,
)

PKG_ROOT = Path(__file__).resolve().parents[2]  # research/warranted_revision
REPO_ROOT = PKG_ROOT.parents[1]


class SystemSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["fake", "control", "hf"]
    name: str = Field(description="fake policy, control policy, or HF model id")
    params: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    label: str
    split: Split
    inputs: str  # path relative to research/warranted_revision
    case_ids_file: str | None = None
    allow_holdout: bool = False
    conditions: list[ConditionName]
    replicates: int = Field(default=1, gt=0)
    systems: list[SystemSpec]
    condition_config: ConditionConfig = Field(default_factory=ConditionConfig)
    option_order_seed: int = 1684
    sampling_seed: int = 20261025
    max_calls: int | None = None
    out_root: str = "../../results/warranted_revision"
    # Only privileged control systems may read this.
    gold_for_controls: str | None = None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state() -> tuple[str, bool]:
    """Commit and dirty flag. On a GPU box that received a source bundle instead of a clone,
    the controller passes the commit in ``WREV_GIT_SHA`` (dirty state is then unknown)."""
    if os.environ.get("WREV_GIT_SHA"):
        return os.environ["WREV_GIT_SHA"], True
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--", "research/warranted_revision"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return sha, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def load_cases(cfg: RunConfig) -> list[VisibleCase]:
    if cfg.split == "holdout" and not cfg.allow_holdout:
        raise SystemExit("holdout split is frozen; set allow_holdout only for the confirmatory run")
    path = PKG_ROOT / cfg.inputs
    if "gold" in path.name:
        raise SystemExit("runner inputs must be a model-visible *_inputs.jsonl file")
    cases = [VisibleCase.model_validate_json(ln) for ln in path.read_text().splitlines() if ln]
    if any(c.split != cfg.split for c in cases):
        raise SystemExit("inputs file does not match the configured split")
    if cfg.case_ids_file:
        wanted = json.loads((PKG_ROOT / cfg.case_ids_file).read_text())
        by_id = {c.case_id: c for c in cases}
        cases = [by_id[i] for i in wanted]
    return cases


def expected_calls(cfg: RunConfig, cases: list[VisibleCase]) -> int:
    n_fu = sum(len(c.followups) for c in cases)
    per_rep = sum(
        cfg.condition_config.calls_per_turn(cond, "base") * len(cases)
        + cfg.condition_config.calls_per_turn(cond, "followup") * n_fu
        for cond in cfg.conditions
    )
    return per_rep * cfg.replicates * len(cfg.systems)


def build_backend(spec: SystemSpec, cfg: RunConfig) -> Backend:
    if spec.kind == "fake":
        from .backends import fake

        policies = {
            "visible_random": fake.VisibleRandomPolicy,
            "first_option": fake.FirstOptionPolicy,
        }
        return fake.FakeBackend(policies[spec.name](), **spec.params)
    if spec.kind == "control":
        if not cfg.gold_for_controls:
            raise SystemExit("control systems need gold_for_controls")
        from .backends.controls import control_backend  # privileged; never used by arms

        return control_backend(spec.name, PKG_ROOT / cfg.inputs, PKG_ROOT / cfg.gold_for_controls)
    from .backends.hf import HFBackend

    return HFBackend(spec.name, **spec.params)


def _write(fh, row: BaseModel) -> None:
    fh.write(row.model_dump_json() + "\n")


def run(
    cfg: RunConfig,
    *,
    dry_run: bool = False,
    out_root: Path | None = None,
    backends: dict[str, Backend] | None = None,
) -> Path | None:
    """Execute a run. ``backends`` lets tests inject already-built backends by system name."""
    cases = load_cases(cfg)
    n_calls = expected_calls(cfg, cases)
    n_fu = sum(len(c.followups) for c in cases)
    print(
        f"[plan] run_id={cfg.run_id} split={cfg.split} cases={len(cases)} follow-ups={n_fu} "
        f"conditions={cfg.conditions} replicates={cfg.replicates} systems={[s.name for s in cfg.systems]}"
    )
    for cond in cfg.conditions:
        cc = cfg.condition_config
        print(
            f"[plan]   {cond}: {cc.calls_per_turn(cond, 'base')} calls/base turn, "
            f"{cc.calls_per_turn(cond, 'followup')} calls/follow-up turn"
        )
    print(f"[plan] expected model calls: {n_calls}")
    real = any(s.kind == "hf" for s in cfg.systems)
    if real and cfg.max_calls is None:
        raise SystemExit("GPU runs must set max_calls")
    if cfg.max_calls is not None and n_calls > cfg.max_calls:
        raise SystemExit(
            f"plan needs {n_calls} calls > max_calls={cfg.max_calls}; refusing to start"
        )
    if dry_run:
        return None

    root = out_root or (PKG_ROOT / cfg.out_root).resolve()
    out = root / cfg.run_id
    if out.exists():
        raise SystemExit(f"{out} exists; runs are immutable, choose a new run_id")
    out.mkdir(parents=True)
    built: dict[str, Backend] = {}
    for s in cfg.systems:
        b = (backends or {}).get(s.name) or build_backend(s, cfg)
        if b.label in built:
            raise SystemExit(f"duplicate system label {b.label}")
        built[b.label] = b
    sha, dirty = git_state()
    data_files = {cfg.inputs: _sha(PKG_ROOT / cfg.inputs)}
    if cfg.case_ids_file:
        data_files[cfg.case_ids_file] = _sha(PKG_ROOT / cfg.case_ids_file)
    if cfg.gold_for_controls and any(s.kind == "control" for s in cfg.systems):
        data_files[cfg.gold_for_controls + " (read by privileged controls only)"] = _sha(
            PKG_ROOT / cfg.gold_for_controls
        )

    actual = 0
    with (
        (out / "predictions.jsonl").open("w") as f_pred,
        (out / "decisions.jsonl").open("w") as f_dec,
        (out / "search_traces.jsonl").open("w") as f_tr,
    ):

        def record(
            system: str,
            cond: ConditionName,
            case: VisibleCase,
            fid: str | None,
            rep: int,
            order: list[str],
            res: TurnResult,
        ) -> None:
            nonlocal actual
            turn = "base" if fid is None else "followup"
            for i, c in enumerate(res.calls):
                _write(
                    f_pred,
                    CallRecord(
                        run_id=cfg.run_id,
                        system=system,
                        condition=cond,
                        case_id=case.case_id,
                        followup_id=fid,
                        turn=turn,
                        replicate=rep,
                        call_index=i,
                        call_role=c.role,
                        option_order=order,
                        gen=c.gen,
                        messages_sha256=P.messages_sha256(list(c.messages)),
                        messages=list(c.messages),
                        completion=c.completion,
                        parsed=c.parsed,
                    ),
                )
            actual += len(res.calls)
            if res.nodes:
                _write(
                    f_tr,
                    SearchTrace(
                        run_id=cfg.run_id,
                        system=system,
                        condition=cond,
                        case_id=case.case_id,
                        followup_id=fid,
                        turn=turn,
                        replicate=rep,
                        nodes=res.nodes,
                        selected_node_id=res.selected_node_id,
                        selection_rule=res.selection_rule,
                    ),
                )
            _write(
                f_dec,
                DecisionRecord(
                    run_id=cfg.run_id,
                    system=system,
                    condition=cond,
                    case_id=case.case_id,
                    family_id=case.family_id,
                    followup_id=fid,
                    turn=turn,
                    replicate=rep,
                    option_order=order,
                    status=res.status,
                    choice=res.choice,  # type: ignore[arg-type]
                    n_calls=len(res.calls),
                    prompt_tokens=sum(c.completion.prompt_tokens for c in res.calls),
                    completion_tokens=sum(c.completion.completion_tokens for c in res.calls),
                    latency_s=sum(c.completion.latency_s for c in res.calls),
                    final_text=res.final_text,
                ),
            )

        for backend in built.values():
            for cond in cfg.conditions:
                fn = RUNNERS[cond]
                for rep in range(cfg.replicates):
                    for case in cases:
                        order = P.option_order(case, rep, cfg.option_order_seed)
                        seed_root = (
                            f"{cfg.sampling_seed}:{backend.label}:{cond}:{case.case_id}:{rep}"
                        )
                        base = fn(
                            backend,
                            TurnInput(case, order, None, None, None, None, seed_root + ":base"),
                            cfg.condition_config,
                        )
                        record(backend.label, cond, case, None, rep, order, base)
                        for fu in case.followups:
                            ti = TurnInput(
                                case,
                                order,
                                fu.text,
                                base.final_text,
                                base.history_fmt,
                                base.choice,
                                f"{seed_root}:{fu.followup_id}",
                            )
                            record(
                                backend.label,
                                cond,
                                case,
                                fu.followup_id,
                                rep,
                                order,
                                fn(backend, ti, cfg.condition_config),
                            )

    systems_info = {b.label: b.info() for b in built.values()}
    protocol = PKG_ROOT / "PROTOCOL.md"
    manifest = Manifest(
        run_id=cfg.run_id,
        created_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        synthetic=all(b.synthetic for b in built.values()),
        label=cfg.label,
        git_sha=sha,
        git_dirty=dirty,
        protocol_sha256=_sha(protocol),
        data_files=data_files,
        split=cfg.split,
        case_ids=[c.case_id for c in cases],
        conditions=cfg.conditions,
        replicates=cfg.replicates,
        systems=systems_info,
        decoding=cfg.condition_config.model_dump(),
        budget={
            "max_calls": cfg.max_calls,
            "calls_per_turn": {
                c: {t: cfg.condition_config.calls_per_turn(c, t) for t in ("base", "followup")}
                for c in cfg.conditions
            },
        },
        seeds={"option_order_seed": cfg.option_order_seed, "sampling_seed": cfg.sampling_seed},
        hardware={"platform": platform.platform(), "python": platform.python_version()},
        expected_calls=n_calls,
        actual_calls=actual,
        notes=[f"config: {cfg.model_dump_json()}"],
    )
    (out / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    print(f"[done] {actual} calls written to {out}")
    if actual != n_calls:
        raise SystemExit(f"call count mismatch: planned {n_calls}, made {actual}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true", help="print the call plan and exit")
    ap.add_argument("--run-id", help="override run_id from the config")
    args = ap.parse_args(argv)
    raw = json.loads(args.config.read_text())
    if args.run_id:
        raw["run_id"] = args.run_id
    run(RunConfig.model_validate(raw), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
