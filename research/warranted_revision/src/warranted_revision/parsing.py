"""Strict output parsing.

The final choice is read only from a single ``DECISION: <code>`` line that is the last
non-empty line of the reply and names an offered code. Stray option mentions elsewhere are
never used to infer a choice. Outputs without a valid decision line are kept and labelled
``refusal`` (explicit refusal language) or ``invalid`` (anything else); empty outputs are
``missing``. ``need_more_information`` is a valid, distinct choice, not a refusal.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .schema import Completion, ParsedOutput, PremiseLedger

DECISION_LINE = re.compile(r"^DECISION: ([a-z][a-z0-9_]*)$")
ANY_DECISION = re.compile(r"DECISION\s*:", re.I)
SUPPORTED_LINE = re.compile(r"^SUPPORTED: (yes|no)$")
LEDGER_BLOCK = re.compile(r"<ledger>(.*?)</ledger>", re.S)
REFUSAL = re.compile(
    r"\b(I can(?:no|')t (?:help|assist|advise|recommend|make (?:this|that) (?:decision|call))"
    r"|I(?: am|'m) (?:not able|unable) to (?:help|advise|recommend|make)"
    r"|I won't (?:recommend|advise|choose|make)"
    r"|I (?:must|have to) decline)",
    re.I,
)


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def parse_ledger(text: str) -> tuple[PremiseLedger | None, str | None]:
    """Parse exactly one <ledger> JSON block. Returns (ledger, error)."""
    blocks = LEDGER_BLOCK.findall(text)
    if len(blocks) != 1:
        return None, f"expected one <ledger> block, found {len(blocks)}"
    try:
        return PremiseLedger.model_validate(json.loads(blocks[0])), None
    except (json.JSONDecodeError, ValidationError) as exc:
        return None, f"ledger did not validate: {type(exc).__name__}"


def parse_decision(
    completion: Completion, options: list[str], *, want_ledger: bool
) -> ParsedOutput:
    text = completion.text
    if completion.error is not None or not text.strip():
        return ParsedOutput(status="missing", error=completion.error or "empty output")
    ledger, ledger_err = parse_ledger(text) if want_ledger else (None, None)
    m = DECISION_LINE.match(_last_line(text))
    n_decision_lines = len(ANY_DECISION.findall(text))
    if m and n_decision_lines == 1 and m.group(1) in options:
        return ParsedOutput(status="valid", choice=m.group(1), ledger=ledger, error=ledger_err)
    if REFUSAL.search(text) and not m:
        return ParsedOutput(
            status="refusal", ledger=ledger, error="refusal language, no decision line"
        )
    if m and m.group(1) not in options:
        err = f"code {m.group(1)!r} is not an offered option"
    elif n_decision_lines > 1:
        err = "more than one DECISION line"
    else:
        err = "no final DECISION line"
    return ParsedOutput(status="invalid", ledger=ledger, error=err)


def parse_hypothesis(completion: Completion) -> ParsedOutput:
    text = completion.text
    if completion.error is not None or not text.strip():
        return ParsedOutput(
            kind="hypothesis", status="missing", error=completion.error or "empty output"
        )
    ledger, ledger_err = parse_ledger(text)
    m = SUPPORTED_LINE.match(_last_line(text))
    if ledger is not None and m:
        return ParsedOutput(
            kind="hypothesis",
            status="valid",
            ledger=ledger,
            hypothesis_supported=m.group(1) == "yes",
        )
    if REFUSAL.search(text):
        return ParsedOutput(
            kind="hypothesis", status="refusal", ledger=ledger, error="refusal language"
        )
    return ParsedOutput(
        kind="hypothesis",
        status="invalid",
        ledger=ledger,
        hypothesis_supported=(m.group(1) == "yes") if m else None,
        error=ledger_err or "no final SUPPORTED line",
    )
