"""Prompt rendering and option ordering. Model-visible inputs only.

This module takes :class:`~warranted_revision.schema.VisibleCase` objects and never sees gold
records. All four conditions share the same system message, narrative, follow-up text,
option list and option order; only the response-format instructions differ.
"""

from __future__ import annotations

import hashlib
import json
import random

from .schema import UPDATE_INTERPRETATIONS, Message, PremiseLedger, VisibleCase

SYSTEM = (
    "You are a careful decision advisor. The user describes a decision, their facts and their "
    "priority. Recommend exactly one of the listed options."
)

# Answer-format wording revised after smoke-003, where Qwen3.5-9B often put the DECISION
# line at the end of a sentence or inside the <ledger> block (see results/.../smoke-003).
DECISION_RULE = (
    "Put your decision on its own last line, written exactly as `DECISION: <code>` with one "
    "code from the list and nothing after it. Use need_more_information only if the "
    "information given is not enough to decide."
)

DIRECT_FORMAT = (
    "Answer in at most three sentences. Then start a new line for the decision. " + DECISION_RULE
)

LEDGER_SPEC = (
    "Write a JSON object between <ledger> and </ledger> with these keys:\n"
    '- "facts": list of {"name", "value", "quote", "source"} for every fact you use; "quote" '
    'copies the user\'s exact words; "source" is "base" (first message) or "followup" (a later '
    "message).\n"
    '- "priority": the user\'s current priority in your words; "priority_quote": their exact words.\n'
    '- "interpretation": how to read the user\'s latest message, one of: '
    + ", ".join(UPDATE_INTERPRETATIONS)
    + '.\n- "interpretation_quote": exact words from the latest message that support that reading '
    "(empty for initial_request).\n"
    '- "missing_required": names of facts the priority needs but that are now unknown (or []).\n'
    '- "rule_check": {"left_label", "left_value", "comparator", "right_label", "right_value", '
    '"satisfied"} applying the priority to the facts as numbers, or null if it cannot be applied. '
    '"comparator" must be one of ">", ">=", "<", "<=" (symbols, not words); "satisfied" is true '
    "or false.\n"
    "Keep it short: include only the facts the priority needs."
)

LEDGER_THEN_DECISION = (
    "\nClose the ledger with </ledger> first. The DECISION line goes after it, never inside "
    "the ledger. " + DECISION_RULE + " End exactly like this:\n</ledger>\nDECISION: <code>"
)

STRUCTURED_FORMAT = LEDGER_SPEC + LEDGER_THEN_DECISION

HYPOTHESIS_FORMAT = (
    "Do not decide yet. Consider this reading of my latest message: <<HYPOTHESIS>>.\n"
    + LEDGER_SPEC
    + '\nSet "interpretation" to <<HYPOTHESIS>>. After </ledger>, write a last line '
    "`SUPPORTED: yes` or `SUPPORTED: no`: does the exact wording of my latest message support "
    "this reading? End exactly like this, with yes or no:\n</ledger>\nSUPPORTED: <yes or no>"
)

DECIDE_FORMAT = (
    "Here is a draft premise ledger for this conversation:\n<draft>\n<<LEDGER>>\n</draft>\n"
    "Check every quote and number against the conversation, correct anything unsupported, apply "
    "my current priority, and write the corrected ledger.\n" + LEDGER_SPEC + LEDGER_THEN_DECISION
)


def option_order(case: VisibleCase, replicate: int, seed: int) -> list[str]:
    """Option order for one case and replicate, shared by every turn and every condition.

    A seeded permutation of the case's options is rotated by ``replicate``: within a replicate
    all follow-ups and all conditions see the same order (paired), and over ``len(options)``
    replicates each option appears in each position exactly once (counterbalanced).
    """
    codes = case.option_codes
    token = f"{seed}:{case.case_id}".encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(token).digest()[:8], "big"))
    base = list(codes)
    rng.shuffle(base)
    r = replicate % len(base)
    return base[r:] + base[:r]


def option_block(case: VisibleCase, order: list[str]) -> str:
    text = {o.code: o.text for o in case.options}
    return "Options:\n" + "\n".join(f"- {code}: {text[code]}" for code in order)


def base_user_text(case: VisibleCase) -> str:
    return f"{case.narrative}\n\n{case.question}"


def with_instructions(user_text: str, case: VisibleCase, order: list[str], fmt: str) -> str:
    return f"{user_text}\n\n{option_block(case, order)}\n\n{fmt}"


def conversation(
    case: VisibleCase,
    order: list[str],
    fmt: str,
    *,
    followup_text: str | None = None,
    base_reply: str | None = None,
    base_fmt: str | None = None,
) -> list[Message]:
    """Messages for one call.

    Base turn: system + base question with ``fmt``. Follow-up turn: system + base question
    (with the base-turn format it was asked under) + the condition's own base reply + the
    follow-up with ``fmt``.
    """
    msgs = [Message(role="system", content=SYSTEM)]
    if followup_text is None:
        msgs.append(
            Message(role="user", content=with_instructions(base_user_text(case), case, order, fmt))
        )
        return msgs
    assert base_reply is not None and base_fmt is not None
    msgs.append(
        Message(role="user", content=with_instructions(base_user_text(case), case, order, base_fmt))
    )
    msgs.append(Message(role="assistant", content=base_reply))
    msgs.append(Message(role="user", content=with_instructions(followup_text, case, order, fmt)))
    return msgs


def hypothesis_format(hypothesis: str) -> str:
    return HYPOTHESIS_FORMAT.replace("<<HYPOTHESIS>>", hypothesis)


def decide_format(ledger: PremiseLedger | None) -> str:
    body = json.dumps(ledger.model_dump(mode="json"), indent=1) if ledger else "(no draft parsed)"
    return DECIDE_FORMAT.replace("<<LEDGER>>", body)


def messages_sha256(msgs: list[Message]) -> str:
    blob = json.dumps([m.model_dump(mode="json") for m in msgs], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()
