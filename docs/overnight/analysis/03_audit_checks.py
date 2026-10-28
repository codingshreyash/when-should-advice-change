"""Overnight pass 03: offline checks for the implementation audit.

Run from the repository root:
    PYTHONPATH=research/warranted_revision/src python3 docs/overnight/analysis/03_audit_checks.py

CPU only, no model calls. Writes nothing inside the repository: every file it makes goes
into a fresh temporary directory. Uses no model outputs; the label checks use the scenario
author's draft labels (`expected`) only to show what the code accepts, not as an estimate.
"""

from __future__ import annotations

import csv
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from warranted_revision import decision_procedure as dp
from warranted_revision import decision_procedure_analysis as an

ROOT = Path(__file__).resolve().parents[3]
TMP = Path(tempfile.mkdtemp(prefix="overnight03_"))


def head(t: str) -> None:
    print(f"\n== {t}")


# 1. option order across variants and arms -------------------------------------------------
head("1 option order")
cfg = dp.load_config(ROOT / "research/warranted_revision/configs/decision_procedure_full.json")
items = dp.build_items(cfg)
orders = defaultdict(set)
for it in items:
    orders[(it.id, it.sample)].add(it.option_order)
print("items", len(items), "(scenario,sample) cells", len(orders),
      "cells with >1 order", sum(len(v) > 1 for v in orders.values()))
per_scen = defaultdict(set)
for (sid, k), v in orders.items():
    per_scen[sid] |= v
print("scenarios whose order varies across samples", sum(len(v) > 1 for v in per_scen.values()),
      "of", len(per_scen))

# 2. labeling.py score from two copies of the draft labels ----------------------------------
head("2 labeling.py score with two identical sheets filled from the draft labels")
work = TMP / "labeling"
(work / "data/scenarios").mkdir(parents=True)
(work / "scripts/data").mkdir(parents=True)
shutil.copy(ROOT / "scripts/data/labeling.py", work / "scripts/data/labeling.py")
blind_paths = []
for stem in ("career_pilot", "career_v2"):
    shutil.copy(ROOT / f"data/scenarios/{stem}.jsonl", work / f"data/scenarios/{stem}.jsonl")
    subprocess.run([sys.executable, "scripts/data/labeling.py", "make", f"data/scenarios/{stem}.jsonl"],
                   cwd=work, check=True, capture_output=True)
    draft = {json.loads(x)["id"]: json.loads(x)["expected"]
             for x in (work / f"data/scenarios/{stem}.jsonl").read_text().splitlines() if x}
    key = {r["row_id"]: r["item_key"].split("::")
           for r in csv.DictReader(open(work / f"data/labeling/{stem}_key.csv"))}
    sheet = work / f"data/labeling/{stem}_sheet.csv"
    rows = list(csv.DictReader(open(sheet)))
    for r in rows:
        sid, v = key[r["row_id"]]
        r["your_label"] = draft[sid][v]
    filled = work / f"{stem}_filled.csv"
    with open(filled, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    out = subprocess.run([sys.executable, "scripts/data/labeling.py", "score",
                          f"data/scenarios/{stem}.jsonl", str(filled), str(filled)],
                         cwd=work, check=True, capture_output=True, text=True)
    print(f"[{stem}] exit 0; ALL line:", [l for l in out.stdout.splitlines() if l.startswith("ALL")])
    blind_paths.append(work / f"data/labeling/{stem}_blind.jsonl")
lab_fake = an.load_labels(blind_paths)
sets_fake = an.eligibility(lab_fake)
print("analysis accepts the fake *_blind.jsonl; eligible counts:", {k: len(v) for k, v in sets_fake.items()})

head("2b analysis --labels accepts the scenario files themselves (draft labels)")
lab_draft = an.load_labels([ROOT / "data/scenarios/career_pilot.jsonl", ROOT / "data/scenarios/career_v2.jsonl"])
sets_draft = an.eligibility(lab_draft)
print("eligible counts from draft labels (NOT blind):", {k: len(v) for k, v in sets_draft.items()})
print("identical to 2:", sets_draft == sets_fake)

# 3. validity passes when rows are missing ---------------------------------------------------
head("3 validity with missing rows")
rows = []
for it in items:
    rows.append({"arm": it.arm, "id": it.id, "variant": it.variant, "sample": it.sample,
                 "choice_strict": it.option_order[0], "error": None})
kept = [r for r in rows if not (r["arm"] == "A" and r["id"] != "career_01")]
val = an.validity(kept, cfg)
print("arm A rows kept", val["A"]["calls"], "of 1200; passed =", val["A"]["passed"])

# 4. unparsed generative rows: per-scenario n and Press/Ask under the sensitivity rule -------
head("4 unparsed handling")
samples = {k: {"base": "a", "relevant_update": None, "irrelevant_update": "a",
               "pressure": None, "mention_target": "a", "omission": None} for k in range(5)}
o_main = an.scenario_outcomes(samples, {"base": "a", "relevant_update": "b"}, "b")
o_sens = an.scenario_outcomes(samples, {"base": "a", "relevant_update": "b"}, "b",
                              unparsed_as_change=True)
print("all relevant/pressure/omission unparsed -> main H,Delta,Press,Ask:",
      o_main["H"], o_main["Delta"], o_main["Press"], o_main["Ask"])
print("sensitivity H,Delta,Press,Ask:", o_sens["H"], o_sens["Delta"], o_sens["Press"], o_sens["Ask"])
dup = an.index([{"arm": "A", "id": "s", "sample": 0, "variant": "base", "choice_strict": "a"},
                {"arm": "A", "id": "s", "sample": 0, "variant": "base", "choice_strict": "b"}])
print("duplicate row silently overwrites ->", dup["A"]["s"][0]["base"])

# 5. statistics -----------------------------------------------------------------------------
head("5 statistics")
d = [0.4, -0.2, 0.2, 0.0, 0.6, 0.2, -0.4, 0.2]
brute = sum(abs(sum(s * x for s, x in zip(signs, d))) >= abs(sum(d)) - 1e-9
            for signs in itertools.product((1, -1), repeat=len(d))) / 2 ** len(d)
print("sign_flip_p", an.sign_flip_p(d), "brute force", brute)
lo, hi = an.bootstrap_ci(d)
print("bootstrap ci", round(lo, 4), round(hi, 4), "index used: lower 250, upper 9749 of 10000")
ps6 = {"a": 0.01, "b": 0.02, "c": 0.03, "d": 0.2, "e": 0.3, "f": 0.4}
ps3 = {k: ps6[k] for k in ("a", "b", "c")}
print("holm m=6:", an.holm(ps6))
print("holm when 3 contrasts are not evaluable (m=3):", an.holm(ps3))

# 6. not-evaluable branch ---------------------------------------------------------------------
head("6 decision when not evaluable")
print(an.decide({"estimate": None, "ci95": None}, {}, evaluable=False, valid=True))

# 7. lock coverage ----------------------------------------------------------------------------
head("7 lock coverage")
for rel in ("data/labeling/career_pilot_blind.jsonl", "data/labeling/career_v2_blind.jsonl",
            "scripts/data/labeling.py", "research/warranted_revision/configs/decision_procedure_lock.json",
            "research/warranted_revision/gpu/decision_procedure_job.sh",
            "research/warranted_revision/gpu/remote_job.sh",
            "research/warranted_revision/gpu/brev_controller.py",
            "research/warranted_revision/src/warranted_revision/gpu_guard.py"):
    print(f"{rel}: locked={rel in dp.LOCKED}")

# 8. controller per-launch cap ----------------------------------------------------------------
head("8 controller plan with --max-usd 15 on the decision-procedure config")
out = subprocess.run([sys.executable, str(ROOT / "research/warranted_revision/gpu/brev_controller.py"),
                      "plan", "--hourly", "1.06", "--max-usd", "15", "--run-id", "audit15",
                      "--instance-type", "massedcompute_L40S", "--config",
                      str(ROOT / "research/warranted_revision/configs/decision_procedure_full.json"),
                      "--state", str(TMP / "plan15.json")], capture_output=True, text=True)
print("exit", out.returncode)
b = json.loads((TMP / "plan15.json").read_text())["budget"] if out.returncode == 0 else None
print("budget", b and {k: b[k] for k in ("max_gpu_usd", "permitted_hours", "worst_case_usd")})
# 9. planner estimate vs the on-box gate (x RUNTIME_MARGIN) under the $3 plan ------------------
head("9 planner estimates vs on-box gate")
est = dp.estimate_seconds(cfg)
run_only = est["seconds"] - dp.EST_PREPARE_S
cfg_pre = cfg.model_copy(update={"preflight": None})
full_only = dp.estimate_seconds(cfg_pre)["seconds"] - dp.EST_PREPARE_S
pre_only = run_only - full_only
deadline = 105  # run_deadline_minutes printed by the $3 plan
left_after = deadline - (dp.EST_PREPARE_S + pre_only) / 60
print(f"estimate total {est['seconds']/60:.1f} min = prepare {dp.EST_PREPARE_S/60:.0f} + preflight "
      f"{pre_only/60:.1f} + full run {full_only/60:.1f}")
print(f"gate needs full run x {dp.RUNTIME_MARGIN} = {full_only/60*dp.RUNTIME_MARGIN:.1f} min <= "
      f"minutes left after prepare+preflight = {left_after:.1f} (deadline {deadline}) -> "
      f"{'pass' if full_only/60*dp.RUNTIME_MARGIN <= left_after else 'FAIL'}")
print("\ntemp dir:", TMP)
