"""Measurement diagnostics computed from raw per-call outputs (predictions.jsonl).

These describe whether the instrument works, separately from the scored metrics:

* strict decision validity per call, and rejected outputs that still contain one clear
  ``DECISION: <code>`` (recoverable by a looser parser, but scored as failures);
* premise-ledger validity, kept apart from decision validity: a call can end with a
  well-formed DECISION line while its ledger fails to parse or quotes text that is not in
  the conversation;
* grounding of ledger quotes and arithmetic consistency of ``rule_check``, using the same
  label-free checks as the search scorer;
* token-limit terminations, token usage, model calls, refusals and missing outputs.

Nothing here reads gold labels or changes any score.
"""

from __future__ import annotations

import gzip
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .schema import CallRecord
from .scoring import ScoringContext, arithmetic, grounding

DECISION_TOKEN = re.compile(r"DECISION:\s*([a-z][a-z0-9_]*)")


def _strip(content: str) -> str:
    return content.split("\n\nOptions:\n", 1)[0]


def _context(rec: CallRecord) -> ScoringContext:
    users = [_strip(m.content) for m in rec.messages if m.role == "user"]
    return ScoringContext(
        user_texts=tuple(users),
        latest_text=users[-1] if len(users) > 1 else None,
        options=tuple(rec.option_order),
        previous_choice=None,
    )


def _role_group(role: str) -> str:
    if role.startswith("hypothesis"):
        return "hypothesis"
    return "decision"


def _new() -> dict[str, float]:
    return defaultdict(float)


def call_diagnostics(predictions: Path) -> dict[str, Any]:
    """Aggregate per (system, condition, call group); group is "decision" or "hypothesis"."""
    acc: dict[tuple[str, str, str], dict[str, float]] = defaultdict(_new)
    opener = gzip.open if predictions.suffix == ".gz" else open
    with opener(predictions, "rt") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = CallRecord.model_validate_json(line)
            group = _role_group(rec.call_role)
            a = acc[(rec.system, rec.condition, group)]
            p, c = rec.parsed, rec.completion
            a["calls"] += 1
            a["prompt_tokens"] += c.prompt_tokens
            a["completion_tokens"] += c.completion_tokens
            a["max_new_tokens"] = rec.gen.max_new_tokens
            a["hit_token_limit"] += c.finish_reason == "length"
            a[f"status_{p.status}"] += 1
            if group == "decision" and p.status == "invalid":
                found = DECISION_TOKEN.findall(c.text)
                a["invalid_with_one_clear_decision"] += (
                    len(found) == 1 and found[0] in rec.option_order
                )
            wants_ledger = rec.condition != "direct"
            if not wants_ledger:
                continue
            a["ledger_expected"] += 1
            led = p.ledger
            if led is None:
                if group == "decision" and p.status == "valid":
                    a["valid_decision_without_ledger"] += 1
                continue
            a["ledger_parsed"] += 1
            g = grounding(led, _context(rec))
            a["grounding_sum"] += g
            a["fully_grounded"] += g == 1.0
            a["ledger_has_quotes"] += bool(
                led.facts or led.priority_quote or led.interpretation_quote
            )
            if led.rule_check is not None:
                a["rule_check_present"] += 1
                a["rule_check_consistent"] += arithmetic(led)
    out = []
    for (system, cond, group), a in sorted(acc.items()):
        n = a["calls"]
        row: dict[str, Any] = {
            "system": system,
            "condition": cond,
            "call_group": group,
            "calls": int(n),
            "max_new_tokens": int(a["max_new_tokens"]),
            "strict_valid": int(a["status_valid"]),
            "invalid": int(a["status_invalid"]),
            "refusal": int(a["status_refusal"]),
            "missing": int(a["status_missing"]),
            "invalid_with_one_clear_decision": int(a["invalid_with_one_clear_decision"]),
            "hit_token_limit": int(a["hit_token_limit"]),
            "token_limit_rate": a["hit_token_limit"] / n if n else None,
            "mean_prompt_tokens": a["prompt_tokens"] / n if n else None,
            "mean_completion_tokens": a["completion_tokens"] / n if n else None,
            "total_tokens": int(a["prompt_tokens"] + a["completion_tokens"]),
        }
        if a["ledger_expected"]:
            parsed = a["ledger_parsed"]
            row.update(
                {
                    "ledger_expected": int(a["ledger_expected"]),
                    "ledger_parsed": int(parsed),
                    "ledger_parse_rate": parsed / a["ledger_expected"],
                    "valid_decision_without_ledger": int(a["valid_decision_without_ledger"]),
                    "mean_grounding": a["grounding_sum"] / parsed if parsed else None,
                    "fully_grounded": int(a["fully_grounded"]),
                    "ledger_with_quotes": int(a["ledger_has_quotes"]),
                    "rule_check_present": int(a["rule_check_present"]),
                    "rule_check_consistent": int(a["rule_check_consistent"]),
                }
            )
        out.append(row)
    return {"source": predictions.name, "rows": out}
