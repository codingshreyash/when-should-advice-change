"""Synthetic backends that emit well-formed replies without any model inference.

They exist to test the pipeline, parser, scorer, budget accounting and evaluator. Their
"decisions" come from a policy object. The policies in this module read only the rendered
messages (model-visible text). Privileged policies that read gold labels live in
:mod:`warranted_revision.backends.controls` and are clearly marked.

Nothing produced by these backends is evidence about any language model.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from ..schema import NEED_MORE_INFO, UPDATE_INTERPRETATIONS, Completion, Message
from .base import GenRequest

OPTION_LINE = re.compile(r"^- ([a-z][a-z0-9_]*): (.+)$", re.M)
PRESSURE_PATTERN = re.compile(r"I'd really like to hear that I should (.+?)\. Can you tell me")
PREV_DECISION = re.compile(r"^DECISION: ([a-z][a-z0-9_]*)\s*$", re.M)


@dataclass(frozen=True)
class PromptView:
    """What a fake model can read off the rendered messages."""

    kind: str  # direct | structured | hypothesis | decide
    hypothesis: str | None
    options: dict[str, str]  # code -> option text, in displayed order
    base_text: str  # narrative + question
    latest_text: str | None  # follow-up text, None on the base turn
    previous_choice: str | None
    seed: int
    messages_digest: str


def _strip_instructions(content: str) -> str:
    return content.split("\n\nOptions:\n", 1)[0]


def view(req: GenRequest) -> PromptView:
    msgs = req.messages
    users = [m for m in msgs if m.role == "user"]
    last = users[-1].content
    if "Do not decide yet. Consider this reading" in last:
        kind = "hypothesis"
        m = re.search(r"Consider this reading of my latest message: ([a-z_]+)\.", last)
        hypothesis = m.group(1) if m else None
    elif "Here is a draft premise ledger" in last:
        kind, hypothesis = "decide", None
    elif "<ledger>" in last:
        kind, hypothesis = "structured", None
    else:
        kind, hypothesis = "direct", None
    options = dict(OPTION_LINE.findall(last.split("\n\nOptions:\n", 1)[1]))
    prev = None
    for m in msgs:
        if m.role == "assistant":
            found = PREV_DECISION.findall(m.content)
            prev = found[-1] if found else None
    digest = hashlib.sha256(json.dumps([m.model_dump() for m in msgs]).encode()).hexdigest()
    return PromptView(
        kind=kind,
        hypothesis=hypothesis,
        options=options,
        base_text=_strip_instructions(users[0].content),
        latest_text=_strip_instructions(last) if len(users) > 1 else None,
        previous_choice=prev,
        seed=req.gen.seed,
        messages_digest=digest,
    )


def pressure_target(v: PromptView) -> str | None:
    """Option the latest message asks to hear, read from visible text only."""
    if not v.latest_text:
        return None
    m = PRESSURE_PATTERN.search(v.latest_text)
    if not m:
        return None
    for code, text in v.options.items():
        if text[0].lower() + text[1:] == m.group(1):
            return code
    return None


class Policy(Protocol):
    name: str

    def choose(self, v: PromptView) -> str: ...

    def interpretation(self, v: PromptView) -> str: ...

    def supports(self, v: PromptView, hypothesis: str) -> bool: ...


def _u(v: PromptView, salt: str) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{v.messages_digest}:{v.seed}:{salt}".encode()).digest()[:8], "big"
    )


class VisibleRandomPolicy:
    """Pseudo-random answers that depend only on the rendered messages and the seed."""

    name = "visible_random"

    def choose(self, v: PromptView) -> str:
        codes = list(v.options)
        return codes[_u(v, "choice") % len(codes)]

    def interpretation(self, v: PromptView) -> str:
        if v.latest_text is None:
            return "initial_request"
        opts = UPDATE_INTERPRETATIONS[1:]
        return opts[_u(v, "interp") % len(opts)]

    def supports(self, v: PromptView, hypothesis: str) -> bool:
        return _u(v, "support:" + hypothesis) % 2 == 0


class FirstOptionPolicy(VisibleRandomPolicy):
    """Always picks the first displayed option (an option-position artefact)."""

    name = "first_option"

    def choose(self, v: PromptView) -> str:
        return next(iter(v.options))


def _quote(text: str | None) -> str:
    if not text:
        return ""
    first = re.split(r"(?<=[.?!])\s", text.strip(), maxsplit=1)[0]
    return first[:120]


def render(v: PromptView, choice: str | None, interpretation: str, supported: bool | None) -> str:
    """Render a well-formed reply for the request kind."""
    if v.kind == "direct":
        return f"Based on the stated priority, this is my recommendation.\nDECISION: {choice}"
    ledger: dict[str, Any] = {
        "facts": [],
        "priority": "as stated by the user",
        "priority_quote": "",
        "interpretation": interpretation,
        "interpretation_quote": ""
        if interpretation == "initial_request"
        else _quote(v.latest_text),
        "missing_required": ["deciding_fact"] if choice == NEED_MORE_INFO else [],
        "rule_check": None
        if choice == NEED_MORE_INFO
        else {
            "left_label": "a",
            "left_value": 1.0,
            "comparator": ">",
            "right_label": "b",
            "right_value": 0.0,
            "satisfied": True,
        },
    }
    body = f"<ledger>{json.dumps(ledger)}</ledger>\n"
    if v.kind == "hypothesis":
        return body + f"SUPPORTED: {'yes' if supported else 'no'}"
    return body + f"DECISION: {choice}"


class FakeBackend:
    """Backend driven by a :class:`Policy`. Token counts are word counts (synthetic)."""

    synthetic = True

    def __init__(
        self,
        policy: Policy,
        *,
        privileged: bool = False,
        refusal_rate: float = 0.0,
        garbage_rate: float = 0.0,
    ) -> None:
        self.policy = policy
        self.privileged = privileged
        self.refusal_rate = refusal_rate
        self.garbage_rate = garbage_rate
        suffix = f"+refuse{refusal_rate:g}" if refusal_rate else ""
        suffix += f"+garbage{garbage_rate:g}" if garbage_rate else ""
        self.label = ("control:" if privileged else "fake:") + policy.name + suffix

    def info(self) -> dict[str, Any]:
        return {
            "kind": "control" if self.privileged else "fake",
            "policy": self.policy.name,
            "refusal_rate": self.refusal_rate,
            "garbage_rate": self.garbage_rate,
            "synthetic": True,
            "privileged": self.privileged,
        }

    def _one(self, req: GenRequest) -> Completion:
        v = view(req)
        roll = (_u(v, "fault") % 10_000) / 10_000
        if roll < self.refusal_rate:
            text = "I can't make this decision for you; please consult a qualified advisor."
        elif roll < self.refusal_rate + self.garbage_rate:
            text = f"I would probably go with {next(iter(v.options))}, but it depends."
        else:
            interp = (
                v.hypothesis
                if v.kind == "hypothesis" and v.hypothesis
                else self.policy.interpretation(v)
            )
            supported = (
                self.policy.supports(v, v.hypothesis)
                if v.kind == "hypothesis" and v.hypothesis
                else None
            )
            choice = None if v.kind == "hypothesis" else self.policy.choose(v)
            text = render(v, choice, interp, supported)
        prompt_words = sum(len(m.content.split()) for m in req.messages)
        return Completion(
            text=text,
            prompt_tokens=prompt_words,
            completion_tokens=min(len(text.split()), req.gen.max_new_tokens),
            latency_s=0.0,
        )

    def generate(self, requests: list[GenRequest]) -> list[Completion]:
        return [self._one(r) for r in requests]


def messages_text(msgs: tuple[Message, ...]) -> str:
    return "\n".join(m.content for m in msgs)
