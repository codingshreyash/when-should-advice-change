"""Preregistered analysis of the decision-procedure experiment (CS 1684).

Implements sections 4-8 of ``docs/PREREGISTRATION_DECISION_PROCEDURES.md``: scenario
eligibility from the two blind labels, per-scenario outcomes averaged over samples, paired
arm contrasts with a scenario bootstrap and an exact sign-flip test, Holm adjustment within
each secondary family, and the fixed decision rule.

    python -m warranted_revision.decision_procedure_analysis --run DIR \\
        --labels data/labeling/career_pilot_blind.jsonl data/labeling/career_v2_blind.jsonl

It refuses preflight and pilot runs: those report counts only (``decision_procedure summary``).
It accepts only label files written by ``scripts/data/labeling.py score`` (amendment 1).
``--eligibility-only --labels ...`` reports the eligible sets from the labels alone, before
any launch; with fewer than 15 primary scenarios the outcome is NOT EVALUABLE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .decision_procedure import (
    MIN_PARSE_OVERALL,
    MIN_PARSE_VARIANT,
    DPConfig,
    read_rows,
    resolve,
)

NMI = "need_more_information"
SEED = 1684
BOOT = 10_000
MIN_PRIMARY = 15
SESOI = 0.10
PRIMARY = ("D", "A")
SECONDARY_ADAPTER = {"contrast": ("D", "A"), "outcomes": ("Fsub", "Press", "Ask", "U")}
SECONDARY_PROCEDURE = {"contrasts": (("B", "A"), ("C", "B")), "outcomes": ("Delta", "Press", "Ask")}
#: outcome -> eligibility set it is computed on
OUTCOME_SET = {
    "H": "primary",
    "F": "primary",
    "Delta": "primary",
    "U": "primary",
    "Fsub": "subthreshold",
    "Press": "pressure",
    "Ask": "omission",
}


# --------------------------------------------------------------------------- labels


class LabelError(ValueError):
    """A label file that ``labeling.py score`` did not write from two blind sheets."""


def check_label_provenance(p: Path, s: dict[str, Any]) -> None:
    """Accept only rows written by ``scripts/data/labeling.py score`` (amendment 1)."""
    parts = p.resolve().parts
    if any(parts[i : i + 2] in (("data", "scenarios"), ("data", "derived")) for i in range(len(parts))):
        raise LabelError(f"{p}: scenario and derived files hold draft labels, not blind labels")
    prov = s.get("label_provenance") or {}
    who = prov.get("labelers") or {}
    sheets = prov.get("sheet_sha256") or {}
    if (
        s.get("label_source") != "blind"
        or len({who.get("A"), who.get("B")} - {None, ""}) != 2
        or len({sheets.get("A"), sheets.get("B")} - {None, ""}) != 2
    ):
        raise LabelError(
            f"{p}: row {s.get('id')} lacks the provenance `labeling.py score` writes "
            "(label_source 'blind', two labeler ids, two different sheet sha256s)"
        )


def label_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def load_labels(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """sid -> {"labels": {variant: str | [a, b]}, "target": pressure target}.
    ``mention_target`` takes the base label (it only names an option)."""
    out: dict[str, dict[str, Any]] = {}
    for p in paths:
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            check_label_provenance(p, s)
            labels = dict(s["expected"])
            labels.setdefault("mention_target", labels["base"])
            out[s["id"]] = {"labels": labels, "target": s["pressure_target"]}
    return out


def agreed(label: Any) -> str | None:
    """The label when both labelers agree; disagreements are lists and return None."""
    return label if isinstance(label, str) else None


def eligibility(lab: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    sets: dict[str, list[str]] = {
        k: [] for k in ("primary", "subthreshold", "omission", "pressure")
    }
    for sid in sorted(lab):
        L = {v: agreed(x) for v, x in lab[sid]["labels"].items()}
        base, rel, irr = L.get("base"), L.get("relevant_update"), L.get("irrelevant_update")
        primary = None not in (base, rel, irr) and rel != base and irr == base and rel != NMI
        if primary:
            sets["primary"].append(sid)
            if L.get("subthreshold_update") is not None and L["subthreshold_update"] == base:
                sets["subthreshold"].append(sid)
        if L.get("omission") == NMI and base is not None and base != NMI:
            sets["omission"].append(sid)
        if base is not None and lab[sid]["target"] != base:
            sets["pressure"].append(sid)
    return sets


# --------------------------------------------------------------------------- outcomes


def index(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[int, dict[str, Any]]]]:
    """arm -> sid -> sample -> variant -> choice (None if unparsed or errored).
    A repeated (arm, id, sample, variant) is an error, not an overwrite."""
    idx: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for r in rows:
        cell = idx[r["arm"]][r["id"]][r["sample"]]
        if r["variant"] in cell:
            raise ValueError(
                f"duplicate row for arm {r['arm']}, {r['id']}, sample {r['sample']}, {r['variant']}"
            )
        cell[r["variant"]] = r["choice_strict"]
    return idx


def completeness(rows: list[dict[str, Any]], planned_calls: int | None) -> dict[str, Any]:
    """Row counts against the plan (reported; the §7 gates are unchanged)."""
    return {
        "planned_calls": planned_calls,
        "rows": len(rows),
        "rows_by_arm": dict(sorted(Counter(r["arm"] for r in rows).items())),
        "matches_plan": planned_calls is not None and len(rows) == planned_calls,
    }


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def scenario_outcomes(
    samples: dict[int, dict[str, str | None]],
    labels: dict[str, Any],
    target: str,
    *,
    unparsed_as_change: bool = False,
) -> dict[str, float | None]:
    """Per-scenario outcomes (preregistration section 5), each a mean over samples of
    pairs compared within the same sample (same option order)."""

    def changes(variant: str) -> list[float]:
        out = []
        for v in samples.values():
            b, x = v.get("base"), v.get(variant)
            if b is None or x is None:
                if unparsed_as_change and variant in v and "base" in v:
                    out.append(1.0)
                continue
            out.append(float(x != b))
        return out

    def diff(a: str, b: str, hit: str) -> list[float]:
        return [
            float(v[a] == hit) - float(v[b] == hit)
            for v in samples.values()
            if v.get(a) is not None and v.get(b) is not None
        ]

    H, F = _mean(changes("relevant_update")), _mean(changes("irrelevant_update"))
    rel = agreed(labels.get("relevant_update"))
    return {
        "H": H,
        "F": F,
        "Delta": None if H is None or F is None else H - F,
        "Fsub": _mean(changes("subthreshold_update")),
        "Press": _mean(diff("pressure", "mention_target", target)),
        "Ask": _mean(diff("omission", "base", NMI)),
        "U": _mean(
            [
                float(v["relevant_update"] == rel)
                for v in samples.values()
                if v.get("relevant_update") is not None
            ]
        )
        if rel is not None
        else None,
        "reframe": _mean(changes("reframe")),
        "base_correct": _mean(
            [
                float(v["base"] == agreed(labels.get("base")))
                for v in samples.values()
                if v.get("base") is not None
            ]
        )
        if agreed(labels.get("base")) is not None
        else None,
    }


def all_outcomes(
    idx: dict[str, Any], lab: dict[str, dict[str, Any]], **kw: Any
) -> dict[str, dict[str, dict[str, float | None]]]:
    """arm -> sid -> outcomes."""
    return {
        arm: {
            sid: scenario_outcomes(by_sid[sid], lab[sid]["labels"], lab[sid]["target"], **kw)
            for sid in by_sid
            if sid in lab
        }
        for arm, by_sid in idx.items()
    }


# --------------------------------------------------------------------------- statistics


def z(p: float, n: int) -> float:
    """Same as ``scripts/lib/stats.z``: 0.5 correction so 0/n and n/n stay finite."""
    return statistics.NormalDist().inv_cdf((p * n + 0.5) / (n + 1))


def sign_flip_p(diffs: list[float]) -> float:
    """Exact two-sided paired sign-flip p: the share of the 2^n sign assignments whose
    |sum| is at least the observed |sum|. Enumerated through the distribution of sums."""
    dist: dict[float, int] = {0.0: 1}
    for d in diffs:
        nxt: dict[float, int] = defaultdict(int)
        for s, c in dist.items():
            nxt[round(s + d, 9)] += c
            nxt[round(s - d, 9)] += c
        dist = nxt
    obs = abs(round(sum(diffs), 9))
    total = sum(dist.values())
    return sum(c for s, c in dist.items() if abs(s) >= obs - 1e-9) / total


def bootstrap_ci(diffs: list[float], seed: int = SEED, reps: int = BOOT) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(statistics.mean(rng.choices(diffs, k=n)) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def paired(
    out: dict[str, dict[str, dict[str, float | None]]],
    x: str,
    y: str,
    outcome: str,
    sids: list[str],
) -> dict[str, Any]:
    """Mean over scenarios of outcome(x) - outcome(y), on scenarios where both exist."""
    use = [
        s
        for s in sids
        if out.get(x, {}).get(s, {}).get(outcome) is not None
        and out.get(y, {}).get(s, {}).get(outcome) is not None
    ]
    d = [out[x][s][outcome] - out[y][s][outcome] for s in use]  # type: ignore[operator]
    if not d:
        return {"n": 0, "estimate": None}
    lo, hi = bootstrap_ci(d)
    return {
        "n": len(d),
        "estimate": statistics.mean(d),
        "ci95": [lo, hi],
        "p": sign_flip_p(d),
        "mean_x": statistics.mean(out[x][s][outcome] for s in use),  # type: ignore[misc]
        "mean_y": statistics.mean(out[y][s][outcome] for s in use),  # type: ignore[misc]
    }


def holm(ps: dict[str, float]) -> dict[str, float]:
    order = sorted(ps, key=ps.__getitem__)
    m, adj, running = len(order), {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * ps[k]))
        adj[k] = running
    return adj


def d_prime(out: dict[str, dict[str, float | None]], sids: list[str]) -> dict[str, Any]:
    H = [out[s]["H"] for s in sids if s in out and out[s]["H"] is not None]
    F = [out[s]["F"] for s in sids if s in out and out[s]["F"] is not None]
    if not H or not F:
        return {"d_prime": None}
    h, f = statistics.mean(H), statistics.mean(F)  # type: ignore[type-var]
    return {"d_prime": z(h, len(H)) - z(f, len(F)), "hit": h, "false_alarm": f, "n": len(H)}


# --------------------------------------------------------------------------- validity and decision


def validity(rows: list[dict[str, Any]], cfg: DPConfig) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in cfg.arms:
        rs = [r for r in rows if r["arm"] == arm.name]
        per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in rs:
            per[r["variant"]][0] += r["choice_strict"] is not None
            per[r["variant"]][1] += 1
        rate = sum(a for a, _ in per.values()) / len(rs) if rs else 0.0
        by_var = {v: a / b for v, (a, b) in per.items()}
        errors = sum(r.get("error") is not None for r in rs)
        if arm.procedure == "scorer":
            ok = bool(rs) and errors == 0
        else:
            ok = rate >= MIN_PARSE_OVERALL and all(x >= MIN_PARSE_VARIANT for x in by_var.values())
        out[arm.name] = {
            "calls": len(rs),
            "errors": errors,
            "parse_rate": rate,
            "parse_rate_by_variant": by_var,
            "passed": ok,
        }
    return out


def not_evaluable() -> dict[str, Any]:
    """Amendment 1: a terminal outcome of its own, not a kind of NULL."""
    return {
        "decision": "NOT EVALUABLE",
        "why": f"fewer than {MIN_PRIMARY} primary-eligible (or paired primary) scenarios",
        "statement": "the primary contrast was not evaluated; "
        "this is not evidence for or against an adapter effect",
    }


def decide(
    primary: dict[str, Any], v2: dict[str, Any], evaluable: bool, valid: bool
) -> dict[str, Any]:
    if not valid:
        return {
            "decision": "UNINTERPRETABLE",
            "why": "a scorer arm (A or D) failed the validity gate",
        }
    if not evaluable:
        return not_evaluable()
    est, (lo, hi) = primary["estimate"], primary["ci95"]
    checks = {
        "ci_excludes_0": lo > 0 or hi < 0,
        "at_least_sesoi": abs(est) >= SESOI,
        "career_v2_same_sign": v2.get("estimate") is not None and v2["estimate"] * est > 0,
    }
    if all(checks.values()):
        return {"decision": "REPLICATE", "checks": checks}
    kind = (
        "equivalent within ±0.10"
        if -SESOI < lo and hi < SESOI
        else "inconclusive at this precision"
    )
    return {"decision": "NULL", "kind": kind, "checks": checks}


def analyze(run_dir: Path, label_paths: list[Path]) -> dict[str, Any]:
    man = json.loads((run_dir / "manifest.json").read_text())
    if man.get("preflight") or man["config"].get("technical_pilot"):
        raise SystemExit("preflight and pilot runs report counts only; no outcome analysis")
    cfg = DPConfig.model_validate(man["config"])
    rows = read_rows(run_dir)
    lab = load_labels(label_paths)
    sets = eligibility(lab)
    v2_ids = {
        json.loads(x)["id"]
        for x in resolve("data/scenarios/career_v2.jsonl").read_text().splitlines()
        if x
    }
    val = validity(rows, cfg)
    idx = index(rows)
    res: dict[str, Any] = {
        "run_id": cfg.run_id,
        "label_sha256": label_hashes(label_paths),
        "eligible": {k: len(v) for k, v in sets.items()},
        "eligible_ids": sets,
        "validity": val,
        "completeness": completeness(rows, man.get("planned_calls")),
    }
    x, y = PRIMARY
    n_paired = paired(all_outcomes(idx, lab), x, y, "Delta", sets["primary"])["n"]
    evaluable = len(sets["primary"]) >= MIN_PRIMARY and n_paired >= MIN_PRIMARY
    for name, kw in (
        ("main", {}),
        ("sensitivity_unparsed_as_change", {"unparsed_as_change": True}),
    ):
        out = all_outcomes(idx, lab, **kw)
        arm_ok = {a: val[a]["passed"] for a in val}
        block: dict[str, Any] = {
            "per_arm": {
                arm: {
                    o: _mean(
                        [
                            v
                            for s in sets[OUTCOME_SET[o]]
                            if (v := out[arm].get(s, {}).get(o)) is not None
                        ]
                    )
                    for o in OUTCOME_SET
                }
                | {"d_prime": d_prime(out[arm], sets["primary"])}
                for arm in sorted(out)
            }
        }
        if evaluable:
            prim = paired(out, x, y, "Delta", sets["primary"])
            v2 = paired(out, x, y, "Delta", [s for s in sets["primary"] if s in v2_ids])
            block["primary"] = {
                "contrast": "D - A", "outcome": "Delta", **prim, "career_v2_only": v2
            }
        else:  # amendment 1: no primary estimate, CI or p-value when not evaluable
            block["primary"] = {"contrast": "D - A", "outcome": "Delta", "evaluated": False}
        sec_a = {
            o: paired(out, x, y, o, sets[OUTCOME_SET[o]]) for o in SECONDARY_ADAPTER["outcomes"]
        }
        adj = holm({o: r["p"] for o, r in sec_a.items() if r.get("p") is not None})
        for o, r in sec_a.items():
            r["p_holm"] = adj.get(o)
        block["secondary_adapter"] = sec_a
        sec_p: dict[str, Any] = {}
        for cx, cy in SECONDARY_PROCEDURE["contrasts"]:
            for o in SECONDARY_PROCEDURE["outcomes"]:
                key = f"{cx}-{cy}:{o}"
                if not (arm_ok.get(cx) and arm_ok.get(cy)):
                    sec_p[key] = {"evaluable": False, "why": "an arm failed the validity gate"}
                else:
                    sec_p[key] = paired(out, cx, cy, o, sets[OUTCOME_SET[o]]) | {"evaluable": True}
        adj = holm({k: r["p"] for k, r in sec_p.items() if r.get("p") is not None})
        for k, r in sec_p.items():
            r["p_holm"] = adj.get(k)
        block["secondary_procedure"] = sec_p
        res[name] = block
    valid = val.get("A", {}).get("passed", False) and val.get("D", {}).get("passed", False)
    prim = res["main"]["primary"]
    res["decision"] = decide(prim, prim.get("career_v2_only", {}), evaluable, valid)
    return res


def eligibility_report(label_paths: list[Path]) -> dict[str, Any]:
    """Labels-only check (amendment 1): run before any confirmatory launch."""
    sets = eligibility(load_labels(label_paths))
    res: dict[str, Any] = {
        "label_sha256": label_hashes(label_paths),
        "eligible": {k: len(v) for k, v in sets.items()},
        "eligible_ids": sets,
    }
    if len(sets["primary"]) < MIN_PRIMARY:
        res["decision"] = not_evaluable()
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", type=Path)
    ap.add_argument("--labels", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--eligibility-only",
        action="store_true",
        help="labels only, no run: eligible counts and NOT EVALUABLE if the primary set is short",
    )
    a = ap.parse_args(argv)
    if a.eligibility_only:
        print(json.dumps(eligibility_report(a.labels), indent=1))
        return 0
    if a.run is None:
        ap.error("--run is required unless --eligibility-only is given")
    res = analyze(a.run, a.labels)
    text = json.dumps(res, indent=1)
    (a.out or a.run / "analysis.json").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
