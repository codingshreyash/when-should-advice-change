"""Shared fixtures: small runs on a subset of frozen dev cases (CPU only, no model)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from warranted_revision.runner import PKG_ROOT, RunConfig, run

DATA = PKG_ROOT / "data" / "v0"
DEV_INPUTS = DATA / "dev_inputs.jsonl"
DEV_GOLD = DATA / "dev_gold.jsonl"
# One case per dev family (alternating priorities), enough for family-level checks.
SUBSET = [
    "dev-refinance-00",
    "dev-relocation-01",
    "dev-certification-02",
    "dev-car-03",
    "dev-freelance-04",
]
ALL_CONDITIONS = ["direct", "structured", "best_of_n", "premise_search"]


def make_run(
    tmp: Path,
    run_id: str,
    systems: list[dict],
    *,
    conditions=None,
    replicates=1,
    case_ids=None,
    gold: Path | None = DEV_GOLD,
    inputs: Path = DEV_INPUTS,
    **extra,
) -> Path:
    ids_file = tmp / f"{run_id}_ids.json"
    ids_file.write_text(json.dumps(case_ids or SUBSET))
    cfg = RunConfig(
        run_id=run_id,
        label="test",
        split="dev",
        inputs=str(inputs),
        case_ids_file=str(ids_file),
        conditions=conditions or ALL_CONDITIONS,
        replicates=replicates,
        systems=systems,
        gold_for_controls=str(gold) if gold else None,
        **extra,
    )
    out = run(cfg, out_root=tmp / "runs")
    assert out is not None
    return out


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


@pytest.fixture(scope="session")
def control_run(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("controls")
    systems = [
        {"kind": "control", "name": n}
        for n in ("oracle", "always_agree", "always_oppose", "always_stay_put")
    ]
    systems += [
        {"kind": "fake", "name": "first_option"},
        {"kind": "fake", "name": "visible_random"},
    ]
    return make_run(tmp, "controls", systems, replicates=3)
