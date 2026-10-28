"""Deterministic half of proposal 2 (explicit premise-diff verification). Agent 3 prototype.

The model would write (a) the user's rule once as an arithmetic comparison over named facts,
e.g. ``rate * hours * 48 - benefits > salary``, and (b) for the latest message, a list of
proposed edits ``{"name", "old", "new", "quote"}``. Everything below is model-free and
label-free: it verifies edits against the visible text, takes a consensus over sampled
diffs, applies it to the old state and evaluates the rule exactly, so arithmetic is never
left to the model and a message with no verified edit cannot move the rule's outcome.

Imports the package read-only (``scoring._contains``); does not modify it.
"""

from __future__ import annotations

import ast
import operator
import re
from collections import Counter
from dataclasses import dataclass

from warranted_revision.scoring import _contains

UNKNOWN = "unknown"
_NUM = re.compile(r"(?<![\w.])\$?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s*%)?")
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


class UnsafeExpression(ValueError):
    pass


def numbers_in(text: str) -> list[float]:
    return [float(m.group(1).replace(",", "")) for m in _NUM.finditer(text)]


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def _eval(node, env):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise KeyError(node.id)
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, env)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_eval(node.left, env), _eval(node.right, env))
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
        return _CMP[type(node.ops[0])](_eval(node.left, env), _eval(node.comparators[0], env))
    raise UnsafeExpression(ast.dump(node))


def evaluate_rule(expr: str, facts: dict[str, object]) -> bool | None:
    """Truth of the rule on the facts; None if a needed fact is unknown or missing."""
    tree = ast.parse(expr, mode="eval")
    if not isinstance(tree.body, ast.Compare):
        raise UnsafeExpression("rule must be a single comparison")
    env = {}
    for k, v in facts.items():
        n = _num(v)
        if n is not None:
            env[k] = n
    try:
        return bool(_eval(tree, env))
    except KeyError:
        return None


@dataclass(frozen=True)
class Edit:
    name: str
    old: str
    new: str
    quote: str


def verify_edit(e: Edit, latest_text: str, base_text: str, state: dict[str, object]) -> tuple[bool, str]:
    """An edit is accepted only if its quote is verbatim in the latest message, it targets a
    fact in the old state whose old value matches, and the new value is a number that appears
    inside the quote (or ``unknown`` for a retraction). Self-reported support plays no role."""
    if e.name not in state:
        return False, "unknown fact name"
    if not _contains(latest_text, e.quote):
        return False, "quote not verbatim in latest message"
    old = _num(e.old)
    if old is None or _num(state[e.name]) != old:
        return False, "old value does not match the old state"
    if e.new == UNKNOWN:
        return True, "retraction"
    new = _num(e.new)
    if new is None:
        return False, "new value not numeric"
    if new not in numbers_in(e.quote):
        return False, "new value not in the quoted words"
    if new == old:
        return False, "no change"
    return True, "ok"


def consensus(diffs: list[list[Edit]], latest: str, base: str, state: dict[str, object], min_votes: int = 2) -> list[Edit]:
    """Verified edits proposed (same fact, same new value) by at least ``min_votes`` samples."""
    votes: Counter = Counter()
    first: dict[tuple[str, str], Edit] = {}
    for diff in diffs:
        seen = set()
        for e in diff:
            ok, _ = verify_edit(e, latest, base, state)
            key = (e.name, UNKNOWN if e.new == UNKNOWN else str(_num(e.new)))
            if ok and key not in seen:
                seen.add(key)
                votes[key] += 1
                first.setdefault(key, e)
    return [first[k] for k, n in votes.items() if n >= min_votes]


def apply_diff(state: dict[str, object], edits: list[Edit]) -> dict[str, object]:
    new = dict(state)
    for e in edits:
        new[e.name] = e.new
    return new


def revision_verdict(expr: str, old_state: dict[str, object], edits: list[Edit]) -> dict[str, object]:
    """Old and new rule outcomes. ``warranted_change`` is True only if verified edits flip the
    rule; ``abstain`` if a verified retraction leaves the rule unevaluable."""
    before = evaluate_rule(expr, old_state)
    after = evaluate_rule(expr, apply_diff(old_state, edits))
    return {
        "before": before,
        "after": after,
        "abstain": after is None,
        "warranted_change": after is not None and before is not None and after != before,
        "n_edits": len(edits),
    }
