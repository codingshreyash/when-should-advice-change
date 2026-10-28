"""Pre-declared measurement checks for one pilot shard (see PILOT_PROPOSAL.md).

Usage::

    python -m warranted_revision.pilot_check --run ../../results/warranted_revision/<run_id>

Prints one ``PILOT_CHECK PASS`` or ``PILOT_CHECK FAIL`` line plus a JSON summary, so the
controller's job log is enough to decide whether the next shard may launch. Reads only the
run's manifest and raw per-call outputs (no gold labels). Thresholds were fixed before the
pilot and are not tuned to results:

* every planned call made;
* each arm: at least 95% strictly valid decision calls;
* each ledger-producing arm: at least 90% parsed ledgers (decision and hypothesis calls);
* each arm: at most 1% missing outputs, 2% token-limit stops and 2% refusals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .diagnostics import call_diagnostics

THRESHOLDS = {
    "min_valid_decisions": 0.95,
    "min_ledgers_parsed": 0.90,
    "max_missing": 0.01,
    "max_token_limit": 0.02,
    "max_refusals": 0.02,
}


def check(run: Path) -> dict[str, Any]:
    man = json.loads((run / "manifest.json").read_text())
    pred = next(
        run / n for n in ("predictions.jsonl", "predictions.jsonl.gz") if (run / n).exists()
    )
    rows = call_diagnostics(pred)["rows"]
    problems: list[str] = []
    if man.get("actual_calls") != man.get("expected_calls"):
        problems.append(f"calls: made {man.get('actual_calls')} of {man.get('expected_calls')}")
    arms: dict[str, dict[str, float]] = {}
    for r in rows:
        a = arms.setdefault(
            r["condition"],
            dict.fromkeys(
                (
                    "calls",
                    "decision_calls",
                    "valid",
                    "missing",
                    "limit",
                    "refusal",
                    "led_exp",
                    "led_ok",
                ),
                0.0,
            ),
        )
        a["calls"] += r["calls"]
        a["missing"] += r["missing"]
        a["limit"] += r["hit_token_limit"]
        a["refusal"] += r["refusal"]
        if r["call_group"] == "decision":
            a["decision_calls"] += r["calls"]
            a["valid"] += r["strict_valid"]
        if "ledger_expected" in r:
            a["led_exp"] += r["ledger_expected"]
            a["led_ok"] += r["ledger_parsed"]
    summary = {}
    for cond, a in sorted(arms.items()):
        s = {
            "calls": int(a["calls"]),
            "valid_decisions": a["valid"] / a["decision_calls"] if a["decision_calls"] else None,
            "ledgers_parsed": a["led_ok"] / a["led_exp"] if a["led_exp"] else None,
            "missing": a["missing"] / a["calls"],
            "token_limit": a["limit"] / a["calls"],
            "refusals": a["refusal"] / a["calls"],
        }
        summary[cond] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}
        t = THRESHOLDS
        vd, lp = s["valid_decisions"], s["ledgers_parsed"]
        if vd is not None and vd < t["min_valid_decisions"]:
            problems.append(f"{cond}: valid decisions {vd:.1%}")
        if lp is not None and lp < t["min_ledgers_parsed"]:
            problems.append(f"{cond}: ledgers parsed {lp:.1%}")
        for key, limit in (
            ("missing", "max_missing"),
            ("token_limit", "max_token_limit"),
            ("refusals", "max_refusals"),
        ):
            val = s[key]
            if val is not None and val > t[limit]:
                problems.append(f"{cond}: {key} {val:.1%}")
    return {
        "run_id": man["run_id"],
        "shard": man.get("shard"),
        "pass": not problems,
        "problems": problems,
        "arms": summary,
        "thresholds": THRESHOLDS,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--run", type=Path, required=True)
    args = ap.parse_args(argv)
    res = check(args.run)
    print(f"PILOT_CHECK {'PASS' if res['pass'] else 'FAIL'} {res['run_id']} shard={res['shard']}")
    print(json.dumps(res, indent=1))
    (args.run / "pilot_check.json").write_text(json.dumps(res, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
