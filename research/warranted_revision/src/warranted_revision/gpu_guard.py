"""Spending and safety guard for a bounded GPU smoke run (pure Python, testable on CPU).

The guard never talks to a cloud provider. It turns user-supplied limits into a plan:

* refuses without an explicit ``GPU_HOURLY_USD`` (read from the provider's launch screen),
* refuses ``MAX_GPU_USD`` above 15 (first unattended run cap),
* reserves setup overhead and a safety margin, and derives a hard wall-clock deadline,
* refuses when the run's own call plan, at a conservative per-call time, does not fit,
* refuses a GPU config whose model is not pinned to a 40-hex commit,
* requires exactly one explicit instance type (no auto-selection or fallback list),
* names a dedicated instance ``wrev-smoke-<run>-<random>`` so cleanup can only ever target
  the instance this run created.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import asdict, dataclass

FIRST_RUN_CAP_USD = 15.0
INSTANCE_PREFIX = "wrev-smoke-"
INSTANCE_RE = re.compile(r"^wrev-smoke-[a-z0-9-]{1,40}-[0-9a-f]{6}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
INSTANCE_TYPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


class GuardError(ValueError):
    """Raised when a launch must not proceed."""


@dataclass(frozen=True)
class BudgetPlan:
    gpu_hourly_usd: float
    max_gpu_usd: float
    safety_fraction: float
    setup_hours: float
    permitted_hours: float  # total instance lifetime allowed, setup included
    run_deadline_minutes: int  # wall-clock budget for the experiment step itself
    expected_calls: int
    est_seconds_per_call: float
    est_run_minutes: float
    worst_case_usd: float

    def as_dict(self) -> dict:
        return asdict(self)


def plan_budget(
    gpu_hourly_usd: float | str | None,
    max_gpu_usd: float | str | None,
    *,
    expected_calls: int,
    est_seconds_per_call: float = 6.0,
    setup_hours: float = 0.5,
    safety_fraction: float = 0.8,
    max_wall_hours: float = 4.0,
) -> BudgetPlan:
    """Derive a hard deadline from the spend cap, or raise :class:`GuardError`."""
    if gpu_hourly_usd in (None, ""):
        raise GuardError("GPU_HOURLY_USD is required (copy it from the provider's launch screen)")
    if max_gpu_usd in (None, ""):
        raise GuardError("MAX_GPU_USD is required")
    hourly, cap = float(gpu_hourly_usd), float(max_gpu_usd)  # type: ignore[arg-type]
    if hourly <= 0:
        raise GuardError("GPU_HOURLY_USD must be positive")
    if not 0 < cap <= FIRST_RUN_CAP_USD:
        raise GuardError(f"MAX_GPU_USD must be in (0, {FIRST_RUN_CAP_USD:g}] for the first run")
    if expected_calls <= 0:
        raise GuardError("expected_calls must be positive")
    permitted = min(cap * safety_fraction / hourly, max_wall_hours)
    run_hours = permitted - setup_hours
    if run_hours <= 0:
        raise GuardError(
            f"cap ${cap:g} at ${hourly:g}/h leaves no time after {setup_hours} h setup"
        )
    est_min = expected_calls * est_seconds_per_call / 60
    if est_min > run_hours * 60:
        raise GuardError(
            f"plan needs ~{est_min:.0f} min of inference but only {run_hours * 60:.0f} min "
            "fit under the cap; shrink the smoke set"
        )
    return BudgetPlan(
        gpu_hourly_usd=hourly,
        max_gpu_usd=cap,
        safety_fraction=safety_fraction,
        setup_hours=setup_hours,
        permitted_hours=round(permitted, 3),
        run_deadline_minutes=int(run_hours * 60),
        expected_calls=expected_calls,
        est_seconds_per_call=est_seconds_per_call,
        est_run_minutes=round(est_min, 1),
        worst_case_usd=round(permitted * hourly, 2),
    )


def instance_name(run_id: str, token: str | None = None) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", run_id.lower()).strip("-")[:40] or "run"
    name = f"{INSTANCE_PREFIX}{slug}-{token or secrets.token_hex(3)}"
    check_instance_name(name)
    return name


def check_instance_name(name: str) -> None:
    """Only names this controller generates may ever be deleted."""
    if not INSTANCE_RE.match(name):
        raise GuardError(f"refusing to act on instance {name!r}: not a controller-created name")


def check_pinned_model(config: dict) -> None:
    specs = list(config.get("systems", [])) + ([config["system"]] if config.get("system") else [])
    for spec in specs:
        if spec.get("kind") != "hf":
            continue
        rev = spec.get("params", {}).get("revision", "")
        if not SHA_RE.match(rev):
            raise GuardError(
                f"model {spec.get('name')} is not pinned to a commit (revision={rev!r})"
            )
        if spec.get("params", {}).get("allow_unpinned"):
            raise GuardError("allow_unpinned is not permitted for a paid run")
    if config.get("max_calls") is None:
        raise GuardError("GPU config must set max_calls")


def check_instance_type(instance_type: str) -> None:
    """Exactly one explicit instance type.

    ``brev create`` auto-selects the cheapest match when no type is given and treats a comma
    list as a fallback chain; either could start a machine whose price differs from the
    ``GPU_HOURLY_USD`` the budget was computed from.
    """
    if not INSTANCE_TYPE_RE.match(instance_type or ""):
        raise GuardError(
            f"instance type {instance_type!r} must be exactly one explicit type (no lists, no blanks)"
        )
