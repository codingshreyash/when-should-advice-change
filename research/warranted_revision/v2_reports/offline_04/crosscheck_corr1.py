"""Compare the lead's corr-1 output (warranted_revision.corrections, commit 7d6e5a5) with the
independent expectations in corrected_metrics.py. Read-only.

    # 1. produce corr-1 JSON on scratch copies (prints only; never pass --out into results/)
    PYTHONPATH=research/warranted_revision/src python3 -B -m warranted_revision.corrections \
        --run <scratch>/smoke-004 --gold research/warranted_revision/data/v0/dev_gold.jsonl > corr1_smoke-004.json
    # 2. compare
    python3 research/warranted_revision/v2_reports/offline_04/crosscheck_corr1.py <dir with corr1_<run>.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import common as C
from corrected_metrics import COMPARISONS, U, W, joint, movement, units


def main():
    src = Path(sys.argv[1])
    g = C.gold()
    bad = checked = 0
    for run in C.RUNS:
        f = src / f"corr1_{run}.json"
        if not f.exists():
            continue
        corr = json.loads(f.read_text())
        A = C.arms(C.RESULTS / run)
        R = {cond: C.rows(decs, g) for (_, cond), decs in A.items()}
        for arm in corr["arms"]:
            cond = arm["condition"]
            if cond not in R:
                print(f"[{run}] corr-1 arm {cond} not in mine")
                continue
            rows = R[cond]
            fu = units(rows, lambda r: r["fu_ok"])
            mine = (int(sum(n for _, n, _ in fu)), len(fu))
            theirs = (arm["followup_correct"]["k"], arm["followup_correct"]["n"])
            checked += 1
            if mine != theirs:
                bad += 1
                print(f"[{run}] {cond} followup_correct mine {mine} corr-1 {theirs}")
            mv = arm.get("movement", {}).get("v0")
            if mv:
                m = movement(rows)
                pairs = [
                    ("deference", "S_defer", "nmi[pressure_for_incorrect]", "invalid[pressure_for_incorrect]"),
                    ("opposition", "S_oppose", "nmi[pressure_for_correct]", "invalid[pressure_for_correct]"),
                ]
                for name, k, kn, ki in pairs:
                    for theirs_d, mine_u in ((mv[name], m[k]), (mv[name]["need_more_information"], m[kn]),
                                             (mv[name]["invalid_or_missing"], m[ki])):
                        mk = (int(sum(n for _, n, _ in mine_u)), len(mine_u))
                        checked += 1
                        if mk != (theirs_d["k"], theirs_d["n"]):
                            bad += 1
                            print(f"[{run}] {cond} {name} mine {mk} corr-1 {(theirs_d['k'], theirs_d['n'])}")
                nm = arm["movement"]["neutral_move_to_mentioned"]
                mk = (int(sum(n for _, n, _ in m["S_neutral"])), len(m["S_neutral"]))
                checked += 1
                if mk != (nm["k"], nm["n"]):
                    bad += 1
                    print(f"[{run}] {cond} neutral mine {mk} corr-1 {(nm['k'], nm['n'])}")
        for c in corr["comparisons"]:
            a, b = c["a"], c["b"]
            if a not in R or b not in R:
                continue
            cls = {"warranted_update": W, "unwarranted_stability": U, "all_followups": None}.get(c["axis"], "?")
            if cls == "?" or c["score"] not in ("joint", "followup_only"):
                print(f"[{run}] skipped {c['score']} {c['axis']}")
                continue
            pred = joint if c["score"] == "joint" else (lambda r: r["fu_ok"])
            p, fp, fm, f0 = C.sign_flip_p(units(R[a], pred, cls), units(R[b], pred, cls))
            checked += 1
            got = (c["sign_flip_p"], c["families_a_better"], c["families_b_better"], c["families_tied"])
            if p is None or abs(p - got[0]) > 1e-9 or (fp, fm, f0) != got[1:]:
                bad += 1
                print(f"[{run}] {c['kind']} {a}-{b} {c['axis']} {c['score']}: mine p={p} fam={fp}/{fm}/{f0} corr-1 {got}")
    print(f"crosscheck: {checked} quantities compared, {bad} mismatches")


if __name__ == "__main__":
    main()
