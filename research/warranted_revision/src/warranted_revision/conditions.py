"""The four inference conditions, sharing one interface.

* ``direct``: one greedy call, short answer.
* ``structured``: one greedy call that writes a premise ledger, then decides.
* ``best_of_n``: N sampled structured calls, the best selected by the shared non-oracle
  scorer (:func:`warranted_revision.scoring.score_candidate`).
* ``premise_search``: a two-level beam search. Depth 1 expands one node per interpretation
  of the latest message (on the base turn: sampled readings of the request), each writing a
  premise ledger under that reading; nodes are scored for grounding and support and the top
  ``beam_width`` are kept. Depth 2 asks for ``decisions_per_node`` checked decisions from
  each kept ledger. The final answer is chosen from the depth-2 leaves by the *same* scorer
  and selection rule as best-of-N. This is beam search over premises, not MCTS: there is no
  rollout, value backup or uncertainty-adaptive exploration.

Best-of-N and premise search are matched in model calls per turn and in ``max_new_tokens``
per call (:meth:`ConditionConfig.check_budget`). Nothing here reads gold labels, expected
choices or contrast classes; the inputs are a :class:`VisibleCase`, a follow-up text and
the condition's own previous answer.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import prompts as P
from .backends.base import Backend, GenRequest
from .parsing import parse_decision, parse_hypothesis
from .schema import (
    UPDATE_INTERPRETATIONS,
    Completion,
    ConditionName,
    GenParams,
    Message,
    ParsedOutput,
    SearchNode,
    VisibleCase,
)
from .scoring import ScoringContext, score_candidate, score_hypothesis

FOLLOWUP_HYPOTHESES = tuple(h for h in UPDATE_INTERPRETATIONS if h != "initial_request")


class ConditionConfig(BaseModel):
    """Decoding and budget settings shared by all conditions in a run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_new_tokens_direct: int = Field(default=160, gt=0)
    max_new_tokens_structured: int = Field(default=1024, gt=0)
    sample_temperature: float = Field(default=0.7, gt=0)
    sample_top_p: float = Field(default=0.95, gt=0, le=1)
    best_of_n: int = Field(default=9, gt=0)
    base_turn_readings: int = Field(default=len(FOLLOWUP_HYPOTHESES), gt=0)
    beam_width: int = Field(default=2, gt=0)
    decisions_per_node: int = Field(default=2, gt=0)

    def search_calls(self, turn: str) -> int:
        depth1 = self.base_turn_readings if turn == "base" else len(FOLLOWUP_HYPOTHESES)
        return depth1 + min(self.beam_width, depth1) * self.decisions_per_node

    def calls_per_turn(self, condition: ConditionName, turn: str) -> int:
        return {
            "direct": 1,
            "structured": 1,
            "best_of_n": self.best_of_n,
            "premise_search": self.search_calls(turn),
        }[condition]

    @model_validator(mode="after")
    def check_budget(self) -> ConditionConfig:
        for turn in ("base", "followup"):
            if self.search_calls(turn) != self.best_of_n:
                raise ValueError(
                    f"budget mismatch on {turn} turn: premise_search uses {self.search_calls(turn)} "
                    f"calls, best_of_n uses {self.best_of_n}"
                )
        return self


@dataclass
class CallLog:
    role: str
    messages: tuple[Message, ...]
    gen: GenParams
    completion: Completion
    parsed: ParsedOutput


@dataclass
class TurnResult:
    status: str
    choice: str | None
    final_text: str
    history_fmt: str  # format the base question was asked under (for follow-up history)
    calls: list[CallLog] = field(default_factory=list)
    nodes: list[SearchNode] = field(default_factory=list)
    selected_node_id: str | None = None
    selection_rule: str = ""


@dataclass(frozen=True)
class TurnInput:
    case: VisibleCase
    order: list[str]
    followup_text: str | None
    base_reply: str | None
    base_fmt: str | None
    previous_choice: str | None
    seed_root: str  # system/condition/case/follow-up/replicate, no labels

    @property
    def turn(self) -> str:
        return "base" if self.followup_text is None else "followup"

    def messages(self, fmt: str) -> tuple[Message, ...]:
        return tuple(
            P.conversation(
                self.case,
                self.order,
                fmt,
                followup_text=self.followup_text,
                base_reply=self.base_reply,
                base_fmt=self.base_fmt,
            )
        )

    def context(self) -> ScoringContext:
        users = [P.base_user_text(self.case)] + ([self.followup_text] if self.followup_text else [])
        return ScoringContext(
            user_texts=tuple(users),
            latest_text=self.followup_text,
            options=tuple(self.order),
            previous_choice=self.previous_choice,
        )

    def seed(self, k: int) -> int:
        return int.from_bytes(hashlib.sha256(f"{self.seed_root}:{k}".encode()).digest()[:4], "big")


def _call(
    backend: Backend, reqs: list[tuple[str, tuple[Message, ...], GenParams]], parse
) -> list[CallLog]:
    comps = backend.generate([GenRequest(messages=m, gen=g) for _, m, g in reqs])
    if len(comps) != len(reqs):
        raise RuntimeError("backend returned the wrong number of completions")
    return [
        CallLog(role, m, g, c, parse(role, c)) for (role, m, g), c in zip(reqs, comps, strict=True)
    ]


def select(candidates: list[tuple[str, ParsedOutput, float]]) -> tuple[str | None, str]:
    """Pick the highest-scoring candidate; ties go to the most common choice among the tied
    candidates, then to the earliest candidate. Uses scores and choices only."""
    if not candidates:
        return None, "no candidates"
    best = max(s for _, _, s in candidates)
    tied = [(nid, p) for nid, p, s in candidates if s == best]
    if len(tied) == 1:
        return tied[0][0], "max score"
    votes = Counter(p.choice for _, p in tied if p.choice is not None)
    if votes:
        top = max(votes.values())
        winners = {c for c, n in votes.items() if n == top}
        for nid, p in tied:
            if p.choice in winners:
                return nid, "max score; tie broken by vote, then by order"
    return tied[0][0], "max score; tie broken by order"


def run_direct(backend: Backend, ti: TurnInput, cfg: ConditionConfig) -> TurnResult:
    gen = GenParams(temperature=0.0, max_new_tokens=cfg.max_new_tokens_direct, seed=ti.seed(0))
    log = _call(
        backend,
        [("direct", ti.messages(P.DIRECT_FORMAT), gen)],
        lambda _r, c: parse_decision(c, ti.order, want_ledger=False),
    )[0]
    return TurnResult(
        log.parsed.status, log.parsed.choice, log.completion.text, P.DIRECT_FORMAT, [log]
    )


def run_structured(backend: Backend, ti: TurnInput, cfg: ConditionConfig) -> TurnResult:
    gen = GenParams(temperature=0.0, max_new_tokens=cfg.max_new_tokens_structured, seed=ti.seed(0))
    log = _call(
        backend,
        [("structured", ti.messages(P.STRUCTURED_FORMAT), gen)],
        lambda _r, c: parse_decision(c, ti.order, want_ledger=True),
    )[0]
    return TurnResult(
        log.parsed.status, log.parsed.choice, log.completion.text, P.STRUCTURED_FORMAT, [log]
    )


def _sample(cfg: ConditionConfig, seed: int) -> GenParams:
    return GenParams(
        temperature=cfg.sample_temperature,
        top_p=cfg.sample_top_p,
        max_new_tokens=cfg.max_new_tokens_structured,
        seed=seed,
    )


def _leaf_node(
    nid: str, parent: str | None, depth: int, idx: int, p: ParsedOutput, ctx: ScoringContext
) -> SearchNode:
    score, comp = score_candidate(p, ctx)
    return SearchNode(
        node_id=nid,
        parent_id=parent,
        depth=depth,
        hypothesis=None,
        call_index=idx,
        status=p.status,
        choice=p.choice,
        ledger=p.ledger,
        score=score,
        score_components=comp,
        kept=False,
    )


def _finish(calls: list[CallLog], nodes: list[SearchNode], leaf_ids: list[str]) -> TurnResult:
    by_id = {n.node_id: n for n in nodes}
    cands = []
    for nid in leaf_ids:
        n = by_id[nid]
        parsed = calls[n.call_index].parsed
        cands.append((nid, parsed, n.score))
    chosen, rule = select(cands)
    nodes = [n.model_copy(update={"kept": True}) if n.node_id == chosen else n for n in nodes]
    if chosen is None:
        return TurnResult("missing", None, "", P.STRUCTURED_FORMAT, calls, nodes, None, rule)
    log = calls[by_id[chosen].call_index]
    return TurnResult(
        log.parsed.status,
        log.parsed.choice,
        log.completion.text,
        P.STRUCTURED_FORMAT,
        calls,
        nodes,
        chosen,
        rule,
    )


def run_best_of_n(backend: Backend, ti: TurnInput, cfg: ConditionConfig) -> TurnResult:
    msgs = ti.messages(P.STRUCTURED_FORMAT)
    reqs = [(f"sample_{k}", msgs, _sample(cfg, ti.seed(k))) for k in range(cfg.best_of_n)]
    calls = _call(backend, reqs, lambda _r, c: parse_decision(c, ti.order, want_ledger=True))
    ctx = ti.context()
    nodes = [_leaf_node(f"n{k}", None, 1, k, c.parsed, ctx) for k, c in enumerate(calls)]
    return _finish(calls, nodes, [n.node_id for n in nodes])


def run_premise_search(backend: Backend, ti: TurnInput, cfg: ConditionConfig) -> TurnResult:
    ctx = ti.context()
    if ti.turn == "base":
        hyps = ["initial_request"] * cfg.base_turn_readings
    else:
        hyps = list(FOLLOWUP_HYPOTHESES)
    reqs = [
        (f"hypothesis:{h}", ti.messages(P.hypothesis_format(h)), _sample(cfg, ti.seed(k)))
        for k, h in enumerate(hyps)
    ]
    calls = _call(backend, reqs, lambda _r, c: parse_hypothesis(c))
    nodes: list[SearchNode] = []
    for k, (h, log) in enumerate(zip(hyps, calls, strict=True)):
        score, comp = score_hypothesis(log.parsed, h, ctx)
        nodes.append(
            SearchNode(
                node_id=f"h{k}",
                parent_id=None,
                depth=1,
                hypothesis=h,
                call_index=k,
                status=log.parsed.status,
                choice=None,
                ledger=log.parsed.ledger,
                score=score,
                score_components=comp,
                kept=False,
            )
        )
    # Stable sort: ties keep expansion order, which is fixed and label-free.
    ranked = sorted(nodes, key=lambda n: -n.score)[: min(cfg.beam_width, len(nodes))]
    kept_ids = {n.node_id for n in ranked}
    nodes = [n.model_copy(update={"kept": n.node_id in kept_ids}) for n in nodes]
    reqs2: list[tuple[str, tuple[Message, ...], GenParams]] = []
    parents: list[str] = []
    for parent in ranked:
        for j in range(cfg.decisions_per_node):
            k = len(calls) + len(reqs2)
            reqs2.append(
                (
                    f"decide:{parent.node_id}:{j}",
                    ti.messages(P.decide_format(parent.ledger)),
                    _sample(cfg, ti.seed(k)),
                )
            )
            parents.append(parent.node_id)
    calls2 = _call(backend, reqs2, lambda _r, c: parse_decision(c, ti.order, want_ledger=True))
    leaf_ids = []
    for j, (pid, log) in enumerate(zip(parents, calls2, strict=True)):
        idx = len(calls) + j
        nid = f"d{j}"
        nodes.append(_leaf_node(nid, pid, 2, idx, log.parsed, ctx))
        leaf_ids.append(nid)
    # Depth-1 kept flags mark the beam; the final selected leaf is marked kept in _finish.
    return _finish(calls + calls2, nodes, leaf_ids)


RUNNERS = {
    "direct": run_direct,
    "structured": run_structured,
    "best_of_n": run_best_of_n,
    "premise_search": run_premise_search,
}
