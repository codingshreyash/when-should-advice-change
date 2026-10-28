"""Merge independently executed shard runs into one run directory.

Usage (from ``research/warranted_revision``)::

    python -m warranted_revision.aggregate --out-run-id pilot-01 \
        ../../results/warranted_revision/pilot-01-s1of4 ... ../../results/warranted_revision/pilot-01-s4of4

Refuses to merge unless every shard used the same configuration (apart from run id and
shard), the same git commit, the same model systems and the same planned case list; the
shards are exactly 1..n of one n; their case sets are disjoint and together cover the
planned list; and each shard made exactly the calls it planned. The merged directory is
new and immutable like any run; evaluate and report it as usual.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .schema import Manifest

RAW_FILES = ("predictions.jsonl", "decisions.jsonl", "search_traces.jsonl")


def _config(m: Manifest) -> dict:
    note = next(n for n in m.notes if n.startswith("config: "))
    cfg = json.loads(note[len("config: ") :])
    cfg.pop("run_id", None)
    cfg.pop("shard", None)
    return cfg


def check_shards(manifests: list[Manifest]) -> list[str]:
    """Return problems that make the shards unsafe to merge (empty list = OK)."""
    errs: list[str] = []
    if not manifests:
        return ["no shards given"]
    first = manifests[0]
    n_values = {int(m.shard.split("/")[1]) for m in manifests}
    if len(n_values) != 1:
        return [f"shards disagree on n: {sorted(n_values)}"]
    n = n_values.pop()
    idx = sorted(int(m.shard.split("/")[0]) for m in manifests)
    if idx != list(range(1, n + 1)):
        errs.append(f"need shards 1..{n} exactly once, got {idx}")
    for m in manifests[1:]:
        for field, a, b in (
            ("config", _config(first), _config(m)),
            ("git_sha", first.git_sha, m.git_sha),
            ("systems", _systems(first), _systems(m)),
            ("planned_case_ids", first.planned_case_ids, m.planned_case_ids),
            ("data_files", first.data_files, m.data_files),
        ):
            if a != b:
                errs.append(f"{m.run_id}: {field} differs from {first.run_id}")
    seen: dict[str, str] = {}
    for m in manifests:
        if m.actual_calls != m.expected_calls:
            errs.append(f"{m.run_id}: made {m.actual_calls} of {m.expected_calls} planned calls")
        for c in m.case_ids:
            if c in seen:
                errs.append(f"case {c} in both {seen[c]} and {m.run_id}")
            seen[c] = m.run_id
    planned = first.planned_case_ids or []
    if sorted(seen) != sorted(planned):
        errs.append("shards do not cover the planned case list exactly")
    return errs


def _systems(m: Manifest) -> dict:
    # Load time and similar per-machine facts may differ; compare the model identity only.
    keep = ("kind", "model_id", "revision", "model_class", "dtype", "load_in_4bit", "policy")
    return {k: {f: v.get(f) for f in keep} for k, v in m.systems.items()}


def aggregate(shard_dirs: list[Path], out_dir: Path) -> Manifest:
    manifests = [
        Manifest.model_validate_json((d / "manifest.json").read_text()) for d in shard_dirs
    ]
    errs = check_shards(manifests)
    if errs:
        raise SystemExit("refusing to aggregate:\n  " + "\n  ".join(errs))
    if out_dir.exists():
        raise SystemExit(f"{out_dir} exists; runs are immutable")
    out_dir.mkdir(parents=True)
    run_id = out_dir.name
    order = sorted(range(len(manifests)), key=lambda k: int(manifests[k].shard.split("/")[0]))
    for name in RAW_FILES:
        with (out_dir / name).open("w") as out:
            for k in order:
                for line in (shard_dirs[k] / name).read_text().splitlines():
                    if line.strip():
                        row = json.loads(line)
                        row["run_id"] = run_id
                        out.write(json.dumps(row) + "\n")
    first = manifests[order[0]]
    merged = first.model_copy(
        update={
            "run_id": run_id,
            "case_ids": [c for k in order for c in manifests[k].case_ids],
            "expected_calls": sum(m.expected_calls for m in manifests),
            "actual_calls": sum(m.actual_calls or 0 for m in manifests),
            "shard": f"merged {len(manifests)}/{len(manifests)}",
            "shard_runs": [manifests[k].run_id for k in order],
            "hardware": {manifests[k].run_id: manifests[k].hardware for k in order},
            "systems": {
                s: {**v, "per_shard": {manifests[k].run_id: manifests[k].systems[s] for k in order}}
                for s, v in first.systems.items()
            },
            "notes": first.notes + [f"aggregated from {len(manifests)} shards"],
        }
    )
    (out_dir / "manifest.json").write_text(merged.model_dump_json(indent=2) + "\n")
    return merged


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("shards", nargs="+", type=Path)
    ap.add_argument("--out-run-id", required=True)
    args = ap.parse_args(argv)
    out = args.shards[0].parent / args.out_run_id
    m = aggregate(args.shards, out)
    print(f"merged {len(m.shard_runs or [])} shards into {out} ({m.actual_calls} calls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
