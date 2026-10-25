"""Non-oracle candidate scoring shared by best-of-N and premise search.

The scorer sees only what the evaluated model saw: the user's messages, the offered option
codes, and the model's own previous answer. It never receives gold actions, contrast
classes, family rules or provenance records (``tests/test_leakage.py`` checks the import
graph and the call signature). It does not solve the decision; it checks the candidate's
*own* reasoning for

* grounding: quoted facts, priority and interpretation appear verbatim in the conversation,
  and quotes marked as coming from a follow-up appear in the latest message;
* arithmetic: the model's ``rule_check`` comparison is computed correctly from its own
  numbers;
* supported edits: a changed answer must be justified by an interpretation that can change
  a warranted decision (new fact, changed priority, retraction) quoted from the latest
  message; a "reassurance" or "irrelevant" reading must not change the answer;
* abstention consistency: ``need_more_information`` exactly when the ledger lists a missing
  required fact.

These checks encode the provenance hypothesis (H3) and are identical for both search arms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import NEED_MORE_INFO, ParsedOutput, PremiseLedger

CHANGE_LICENSING = {"new_or_corrected_fact", "changed_goal", "retracted_required_fact"}
NO_CHANGE_READINGS = {"irrelevant_detail", "request_for_reassurance"}

WEIGHTS = {
    "valid_decision": 2.0,
    "ledger_parsed": 1.0,
    "grounding": 1.0,
    "arithmetic": 1.0,
    "supported_edit": 2.0,
    "abstention_consistency": 1.0,
}
HYPOTHESIS_WEIGHTS = {"parsed": 1.0, "grounding": 1.0, "self_report": 1.0, "quote_in_latest": 1.0}


@dataclass(frozen=True)
class ScoringContext:
    """Model-visible context for scoring one turn."""

    user_texts: tuple[str, ...]  # every user message so far, without format instructions
    latest_text: str | None  # the follow-up text (None on the base turn)
    options: tuple[str, ...]
    previous_choice: str | None  # the condition's own base-turn answer (None on the base turn)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _contains(haystack: str, quote: str) -> bool:
    q = _norm(quote).strip(" .\"'")
    return len(q) >= 4 and q in _norm(haystack)


def grounding(ledger: PremiseLedger, ctx: ScoringContext) -> float:
    """Fraction of quotes in the ledger that are verbatim in the right user message."""
    convo = "\n".join(ctx.user_texts)
    checks = []
    for f in ledger.facts:
        where = ctx.latest_text if (f.source == "followup" and ctx.latest_text) else convo
        checks.append(_contains(where, f.quote))
    if ledger.priority_quote:
        checks.append(_contains(convo, ledger.priority_quote))
    if ledger.interpretation_quote:
        checks.append(_contains(ctx.latest_text or "", ledger.interpretation_quote))
    return sum(checks) / len(checks) if checks else 0.0


def arithmetic(ledger: PremiseLedger) -> float:
    rc = ledger.rule_check
    if rc is None:
        return 0.0
    truth = {
        ">": rc.left_value > rc.right_value,
        ">=": rc.left_value >= rc.right_value,
        "<": rc.left_value < rc.right_value,
        "<=": rc.left_value <= rc.right_value,
    }[rc.comparator]
    return 1.0 if truth == rc.satisfied else 0.0


def supported_edit(ledger: PremiseLedger | None, choice: str | None, ctx: ScoringContext) -> float:
    if ctx.previous_choice is None or choice is None:
        return 1.0  # base turn: nothing to revise
    reading = ledger.interpretation if ledger else None
    quoted = bool(ledger and _contains(ctx.latest_text or "", ledger.interpretation_quote))
    if choice != ctx.previous_choice:
        return 1.0 if (reading in CHANGE_LICENSING and quoted) else 0.0
    # Keeping the answer is consistent unless the candidate's own reading says the decision
    # basis changed (a stated priority change or retraction it then ignores).
    if reading == "retracted_required_fact" and choice != NEED_MORE_INFO:
        return 0.0
    return 1.0


def abstention_consistency(ledger: PremiseLedger | None, choice: str | None) -> float:
    if ledger is None or choice is None:
        return 0.0
    return 1.0 if (choice == NEED_MORE_INFO) == bool(ledger.missing_required) else 0.0


def score_candidate(parsed: ParsedOutput, ctx: ScoringContext) -> tuple[float, dict[str, float]]:
    """Score a full candidate (premise ledger + decision). Same rule for every arm."""
    comp = dict.fromkeys(WEIGHTS, 0.0)
    comp["valid_decision"] = 1.0 if parsed.status == "valid" else 0.0
    led = parsed.ledger
    if led is not None:
        comp["ledger_parsed"] = 1.0
        comp["grounding"] = grounding(led, ctx)
        comp["arithmetic"] = arithmetic(led) if parsed.choice != NEED_MORE_INFO else 1.0
    if parsed.status == "valid":
        comp["supported_edit"] = supported_edit(led, parsed.choice, ctx)
        comp["abstention_consistency"] = abstention_consistency(led, parsed.choice)
    total = sum(WEIGHTS[k] * v for k, v in comp.items())
    return total, comp


def score_hypothesis(
    parsed: ParsedOutput, hypothesis: str, ctx: ScoringContext
) -> tuple[float, dict[str, float]]:
    """Score a depth-1 search node (an interpretation of the latest message + ledger)."""
    comp = dict.fromkeys(HYPOTHESIS_WEIGHTS, 0.0)
    led = parsed.ledger
    if led is not None and led.interpretation == hypothesis:
        comp["parsed"] = 1.0
        comp["grounding"] = grounding(led, ctx)
        comp["self_report"] = 1.0 if parsed.hypothesis_supported else 0.0
        if ctx.latest_text is None:
            comp["quote_in_latest"] = 1.0
        else:
            comp["quote_in_latest"] = (
                1.0 if _contains(ctx.latest_text, led.interpretation_quote) else 0.0
            )
    total = sum(HYPOTHESIS_WEIGHTS[k] * v for k, v in comp.items())
    return total, comp


# --------------------------------------------------------------------------------------
# Ablation scorers: format validity only (the full heuristic score is switched off)
# --------------------------------------------------------------------------------------


def score_format_only(parsed: ParsedOutput, ctx: ScoringContext) -> tuple[float, dict[str, float]]:
    """Final-selection score for the ``premise_search_formatonly`` ablation: a valid decision
    and a parsed ledger, nothing else. Ties go through the same vote-then-order rule."""
    comp = {
        "valid_decision": 1.0 if parsed.status == "valid" else 0.0,
        "ledger_parsed": 1.0 if parsed.ledger is not None else 0.0,
    }
    return WEIGHTS["valid_decision"] * comp["valid_decision"] + comp["ledger_parsed"], comp


def score_hypothesis_format_only(
    parsed: ParsedOutput, hypothesis: str, ctx: ScoringContext
) -> tuple[float, dict[str, float]]:
    """Beam-pruning score for the ablation: did the node produce a parseable ledger."""
    comp = {"parsed": 1.0 if parsed.ledger is not None else 0.0}
    return comp["parsed"], comp
