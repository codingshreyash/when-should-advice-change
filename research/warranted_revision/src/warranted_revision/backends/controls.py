"""PRIVILEGED synthetic control policies. These read gold labels.

They are evaluator checks, not experimental arms: an oracle (upper bound), always-agree
(follows any requested answer), always-oppose (picks the other option whenever an answer is
requested), and always-stay-put (repeats its base answer). The evaluator must score oracle
at 1.0 on both co-primary axes and stay-put at 0.0 on the warranted-update axis.

Every row they produce is labelled ``control:<name>`` and the run manifest records
``privileged: true``. No experimental condition, search scorer or selector imports this file.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..schema import ContrastClass, GoldCase, VisibleCase
from .fake import FakeBackend, PromptView, VisibleRandomPolicy, pressure_target

READING = {
    None: "initial_request",
    ContrastClass.relevant_fact: "new_or_corrected_fact",
    ContrastClass.subthreshold_fact: "new_or_corrected_fact",
    ContrastClass.changed_priority: "changed_goal",
    ContrastClass.missing_information: "retracted_required_fact",
    ContrastClass.irrelevant_fact: "irrelevant_detail",
    ContrastClass.neutral_mention: "irrelevant_detail",
    ContrastClass.pressure_for_correct: "request_for_reassurance",
    ContrastClass.pressure_for_incorrect: "request_for_reassurance",
}


class GoldIndex:
    """Map rendered text back to gold labels (privileged)."""

    def __init__(self, visible: list[VisibleCase], gold: list[GoldCase]) -> None:
        self.by_base: dict[str, tuple[VisibleCase, GoldCase]] = {}
        for v, g in zip(visible, gold, strict=True):
            self.by_base[f"{v.narrative}\n\n{v.question}"] = (v, g)

    @classmethod
    def from_files(cls, inputs: Path, gold: Path) -> GoldIndex:
        vis = [VisibleCase.model_validate_json(ln) for ln in inputs.read_text().splitlines() if ln]
        gd = [GoldCase.model_validate_json(ln) for ln in gold.read_text().splitlines() if ln]
        return cls(vis, gd)

    def lookup(self, v: PromptView) -> tuple[str, ContrastClass | None]:
        vis, gold = self.by_base[v.base_text]
        if v.latest_text is None:
            return gold.gold_base_action, None
        fid = next(f.followup_id for f in vis.followups if f.text == v.latest_text)
        gf = next(f for f in gold.followups if f.followup_id == fid)
        return gf.gold_action, gf.contrast_class


class OraclePolicy(VisibleRandomPolicy):
    name = "oracle"

    def __init__(self, index: GoldIndex) -> None:
        self.index = index

    def choose(self, v: PromptView) -> str:
        return self.index.lookup(v)[0]

    def interpretation(self, v: PromptView) -> str:
        return READING[self.index.lookup(v)[1]]

    def supports(self, v: PromptView, hypothesis: str) -> bool:
        return hypothesis == self.interpretation(v)


class AlwaysAgreePolicy(OraclePolicy):
    name = "always_agree"

    def choose(self, v: PromptView) -> str:
        return pressure_target(v) or super().choose(v)


class AlwaysOpposePolicy(OraclePolicy):
    name = "always_oppose"

    def choose(self, v: PromptView) -> str:
        target = pressure_target(v)
        if target is None:
            return super().choose(v)
        return next(c for c in v.options if c not in (target, "need_more_information"))


class StayPutPolicy(OraclePolicy):
    """Correct at base, then repeats its own previous answer for every follow-up."""

    name = "always_stay_put"

    def choose(self, v: PromptView) -> str:
        if v.latest_text is None or v.previous_choice is None:
            return super().choose(v)
        return v.previous_choice


CONTROL_POLICIES = {
    p.name: p for p in (OraclePolicy, AlwaysAgreePolicy, AlwaysOpposePolicy, StayPutPolicy)
}


def control_backend(name: str, inputs: Path, gold: Path) -> FakeBackend:
    return FakeBackend(CONTROL_POLICIES[name](GoldIndex.from_files(inputs, gold)), privileged=True)


def gold_digest(gold: Path) -> str:
    """Short description of which gold file a control read (recorded in the manifest)."""
    import hashlib

    return json.dumps({"path": str(gold), "sha256": hashlib.sha256(gold.read_bytes()).hexdigest()})
