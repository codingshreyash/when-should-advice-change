"""Read-only loaders shared by the offline_04 scripts. Standard library only.

Nothing here writes anywhere. Pass --results to point at a scratch copy if preferred; the
scripts only ever open files for reading.
"""

from __future__ import annotations

import gzip
import itertools
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
PKG = HERE.parents[2]  # research/warranted_revision
REPO = PKG.parents[1]
RESULTS = REPO / "results" / "warranted_revision"
DEV_GOLD = PKG / "data" / "v0" / "dev_gold.jsonl"
RUNS = ("smoke-003", "smoke-004", "format-001")
NMI = "need_more_information"


def jsonl(path: Path):
    path = Path(path)
    if not path.exists() and Path(str(path) + ".gz").exists():
        path = Path(str(path) + ".gz")
    op = gzip.open if path.suffix == ".gz" else open
    with op(path, "rt") as fh:
        for ln in fh:
            if ln.strip():
                yield json.loads(ln)


def gold(path: Path = DEV_GOLD) -> dict:
    return {g["case_id"]: g for g in jsonl(path)}


def followup_index(g: dict) -> dict:
    return {f["followup_id"]: (cid, f) for cid, c in g.items() for f in c["followups"]}


def vote(choices: list[str]) -> str | None:
    """Majority over choices, ties to the earliest (same rule as evaluate._vote)."""
    if not choices:
        return None
    c = Counter(choices)
    top = max(c.values())
    return next(x for x in choices if c[x] == top)


def derived(run_dir: Path, decisions: list[dict]) -> list[dict]:
    """evaluate.derived_records (vote/first/firstvalid) plus vote4 for best_of_n.

    vote4: majority over the *valid* leaves among the first 4 leaves by call_index, ties to
    the earliest; status 'invalid' (choice None) if none of the first 4 is valid.
    vote4_subsets: not a selector; per-turn expected follow-up accuracy over all C(9,4)
    subsets with random tie-break, matching prototypes_03/subsample.py (handled elsewhere).
    """
    key = lambda d: (d["system"], d["condition"], d["case_id"], d["followup_id"], d["replicate"])
    by = {key(d): d for d in decisions}
    out = []
    for tr in jsonl(run_dir / "search_traces.jsonl"):
        d = by.get(key(tr))
        if d is None:
            continue
        leaves = sorted((n for n in tr["nodes"] if n["hypothesis"] is None), key=lambda n: n["call_index"])
        valid = [n for n in leaves if n["status"] == "valid" and n["choice"] is not None]
        picks = {
            "vote": (vote([n["choice"] for n in valid]), "valid"),
            "first": (leaves[0]["choice"], leaves[0]["status"]) if leaves else (None, "missing"),
            "firstvalid": (valid[0]["choice"], "valid") if valid else (None, "invalid"),
        }
        if tr["condition"] == "best_of_n":
            v4 = [n for n in leaves[:4] if n["status"] == "valid" and n["choice"] is not None]
            picks["vote4"] = (vote([n["choice"] for n in v4]), "valid")
        for name, (choice, status) in picks.items():
            out.append({**d, "condition": f"{d['condition']}:{name}", "choice": choice,
                        "status": status if choice is not None else "invalid",
                        "_leaves": [(n["status"], n["choice"]) for n in leaves]})
    return out


def arms(run_dir: Path, with_derived: bool = True) -> dict[tuple[str, str], list[dict]]:
    dec = list(jsonl(run_dir / "decisions.jsonl"))
    out: dict[tuple[str, str], list[dict]] = {}
    for d in dec + (derived(run_dir, dec) if with_derived else []):
        out.setdefault((d["system"], d["condition"]), []).append(d)
    return out


def rows(decs: list[dict], g: dict) -> list[dict]:
    """evaluate.arm_units rows, plus 'opp' = the actionable option that is not gold base."""
    base = {(d["case_id"], d["replicate"]): d for d in decs if d["turn"] == "base"}
    out = []
    for d in decs:
        if d["turn"] != "followup":
            continue
        c = g[d["case_id"]]
        f = next(x for x in c["followups"] if x["followup_id"] == d["followup_id"])
        b = base[(d["case_id"], d["replicate"])]
        acts = [o for o in d["option_order"] if o != NMI]
        opp = [o for o in acts if o != c["gold_base_action"]]
        out.append({
            "family": c["family_id"], "case": d["case_id"], "rep": d["replicate"],
            "fid": d["followup_id"], "cls": f["contrast_class"],
            "base_ok": b["status"] == "valid" and b["choice"] == c["gold_base_action"],
            "fu_ok": d["status"] == "valid" and d["choice"] == f["gold_action"],
            "base_choice": b["choice"], "base_status": b["status"],
            "choice": d["choice"], "status": d["status"],
            "target": f["pressure_target"], "mentioned": f["mentioned_option"],
            "opp": opp[0] if len(opp) == 1 else None,
        })
    return out


def fam_sums(units):
    acc: dict[str, list[float]] = {}
    for f, n, d in units:
        a = acc.setdefault(f, [0.0, 0.0])
        a[0] += n
        a[1] += d
    return acc


def ratio(units):
    den = sum(d for _, _, d in units)
    return None if den == 0 else sum(n for _, n, _ in units) / den


def sign_flip_p(units_a, units_b) -> tuple[float | None, int, int, int]:
    """Exact two-sided family sign-flip p for pooled(a) - pooled(b) on paired units.

    Requires the same denominator per family in a and b (true for paired arms and for the
    base-gated movement classes, one turn per case per class). Statistic T = sum_f D_f with
    D_f = num_a,f - num_b,f; p = #{s in {+1,-1}^G : |sum s_f D_f| >= |T|} / 2^G (all G
    families enumerated, including D_f = 0). Returns (p, #D_f>0, #D_f<0, #D_f=0).
    """
    fa, fb = fam_sums(units_a), fam_sums(units_b)
    fams = sorted(set(fa) | set(fb))
    if not fams:
        return None, 0, 0, 0
    for f in fams:
        if fa.get(f, [0, 0])[1] != fb.get(f, [0, 0])[1]:
            return None, 0, 0, 0
    D = [fa.get(f, [0, 0])[0] - fb.get(f, [0, 0])[0] for f in fams]
    T = abs(sum(D))
    hits = sum(abs(sum(s * x for s, x in zip(signs, D))) >= T - 1e-9
               for signs in itertools.product((1, -1), repeat=len(D)))
    return hits / 2 ** len(D), sum(x > 0 for x in D), sum(x < 0 for x in D), sum(x == 0 for x in D)
