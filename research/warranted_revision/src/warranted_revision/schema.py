"""Validated data contracts for the warranted-revision study.

The schema is split along the leakage boundary that the protocol requires:

* **Model-visible** records (:class:`VisibleCase`, :class:`VisibleFollowUp`) carry only text
  the evaluated model may read. They forbid extra fields, so a gold label cannot ride along
  by accident.
* **Hidden** records (:class:`GoldCase`, :class:`GoldFollowUp`, :class:`Provenance`) hold
  the deterministic reference labels, the contrast class of each follow-up and the evidence
  provenance audit. Only the generator and the offline evaluator read them.

Everything the inference side produces (raw calls, parsed outputs, premise ledgers, search
traces, final decisions) and the run manifest is also defined here so that every JSONL row
is validated on write and on read.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NEED_MORE_INFO = "need_more_information"


class Strict(BaseModel):
    """Base class: unknown fields are an error, instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ContrastClass(str, Enum):
    """Hidden label for what a follow-up does to the warranted decision."""

    relevant_fact = "relevant_fact"
    changed_priority = "changed_priority"
    subthreshold_fact = "subthreshold_fact"
    irrelevant_fact = "irrelevant_fact"
    pressure_for_correct = "pressure_for_correct"
    pressure_for_incorrect = "pressure_for_incorrect"
    missing_information = "missing_information"
    # Secondary control (not on a co-primary axis): mentions the non-warranted option
    # without asking for it. Used to separate pressure from mere option mention.
    neutral_mention = "neutral_mention"
    # Development challenge v1 (data/challenge_v1): stronger symmetric pressure, analysed
    # separately by style. None changes facts or goals; the warranted answer is unchanged.
    pressure_insist_for_correct = "pressure_insist_for_correct"
    pressure_insist_for_incorrect = "pressure_insist_for_incorrect"
    pressure_emotional_for_correct = "pressure_emotional_for_correct"
    pressure_emotional_for_incorrect = "pressure_emotional_for_incorrect"
    pressure_authority_for_correct = "pressure_authority_for_correct"
    pressure_authority_for_incorrect = "pressure_authority_for_incorrect"
    pushback_unspecified = "pushback_unspecified"


#: The eight classes of the v0 dataset (each v0 case has exactly one follow-up per class).
V0_CLASSES = (
    ContrastClass.relevant_fact,
    ContrastClass.changed_priority,
    ContrastClass.subthreshold_fact,
    ContrastClass.irrelevant_fact,
    ContrastClass.pressure_for_correct,
    ContrastClass.pressure_for_incorrect,
    ContrastClass.missing_information,
    ContrastClass.neutral_mention,
)
#: Challenge-v1 pressure classes (no facts or goals change), by style.
CHALLENGE_PRESSURE_CLASSES = {
    "insist": (
        ContrastClass.pressure_insist_for_correct,
        ContrastClass.pressure_insist_for_incorrect,
    ),
    "emotional": (
        ContrastClass.pressure_emotional_for_correct,
        ContrastClass.pressure_emotional_for_incorrect,
    ),
    "authority": (
        ContrastClass.pressure_authority_for_correct,
        ContrastClass.pressure_authority_for_incorrect,
    ),
}


#: Classes whose warranted follow-up action differs from the base action (co-primary axis i).
WARRANTED_UPDATE_CLASSES = (ContrastClass.relevant_fact, ContrastClass.changed_priority)
#: Classes whose warranted follow-up action equals the base action (co-primary axis ii).
UNWARRANTED_UPDATE_CLASSES = (
    ContrastClass.pressure_for_incorrect,
    ContrastClass.pressure_for_correct,
    ContrastClass.subthreshold_fact,
    ContrastClass.irrelevant_fact,
)

Split = Literal["dev", "holdout"]

# --------------------------------------------------------------------------------------
# Model-visible records
# --------------------------------------------------------------------------------------


class OptionSpec(Strict):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    text: str = Field(min_length=3)


class VisibleFollowUp(Strict):
    """A follow-up message as the model sees it. The id is opaque (a hash), so it does not
    reveal the contrast class."""

    followup_id: str = Field(pattern=r"^fu_[0-9a-f]{12}$")
    text: str = Field(min_length=10)


class VisibleCase(Strict):
    case_id: str
    family_id: str
    split: Split
    narrative: str = Field(min_length=40)
    question: str
    options: list[OptionSpec]
    followups: list[VisibleFollowUp]

    @field_validator("options")
    @classmethod
    def _options_ok(cls, v: list[OptionSpec]) -> list[OptionSpec]:
        codes = [o.code for o in v]
        if len(set(codes)) != len(codes):
            raise ValueError("duplicate option codes")
        if NEED_MORE_INFO not in codes:
            raise ValueError("every case must offer need_more_information")
        if len(codes) < 3:
            raise ValueError("need at least two actionable options plus need_more_information")
        return v

    @property
    def option_codes(self) -> list[str]:
        return [o.code for o in self.options]

    @property
    def actionable_codes(self) -> list[str]:
        return [o.code for o in self.options if o.code != NEED_MORE_INFO]


# --------------------------------------------------------------------------------------
# Hidden records: reference labels and provenance audit
# --------------------------------------------------------------------------------------


class FactValue(Strict):
    name: str
    value: float
    unit: str
    span: str = Field(description="Exact narrative text stating this fact")


class Provenance(Strict):
    """Where a follow-up's content comes from and whether it carries authority.

    Accuracy and authority are separate: a user is the authority on their own goals, but a
    factual correction is only treated as evidence when it is substantiated (here: the user
    reports it from a named document). A request to hear an answer has no evidential
    authority at all.
    """

    source_kind: Literal[
        "base_narrative",
        "user_reported_document",
        "user_goal_statement",
        "user_preference_expression",
        "user_extraneous_detail",
        "user_retraction",
    ]
    asserted_by: Literal["user"] = "user"
    substantiated: bool
    authority: Literal["evidence", "goal_owner", "none"]
    note: str = ""


class GoldFollowUp(Strict):
    followup_id: str
    contrast_class: ContrastClass
    gold_action: str
    changed_fact: str | None = None
    old_value: float | None = None
    new_value: float | None = None
    priority_before: str
    priority_after: str
    pressure_target: str | None = None
    mentioned_option: str | None = None
    margin_after: float | None = None
    provenance: Provenance


class GoldCase(Strict):
    case_id: str
    family_id: str
    split: Split
    generator_seed: int
    instance_index: int
    facts: list[FactValue]
    priority_id: str
    rule_description: str
    base_margin: float
    gold_base_action: str
    followups: list[GoldFollowUp]


# --------------------------------------------------------------------------------------
# Inference-side records
# --------------------------------------------------------------------------------------

#: Interpretation vocabulary shown to the structured / search arms. It is a fixed,
#: task-general list (identical for every case), not a per-case label.
UPDATE_INTERPRETATIONS = (
    "initial_request",
    "new_or_corrected_fact",
    "changed_goal",
    "retracted_required_fact",
    "irrelevant_detail",
    "request_for_reassurance",
)


class Message(Strict):
    role: Literal["system", "user", "assistant"]
    content: str


class GenParams(Strict):
    temperature: float = Field(ge=0.0, le=2.0)
    top_p: float = Field(gt=0.0, le=1.0, default=1.0)
    max_new_tokens: int = Field(gt=0, le=4096)
    seed: int


class Completion(Strict):
    text: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    latency_s: float = Field(ge=0.0)
    finish_reason: Literal["stop", "length", "error"] = "stop"
    error: str | None = None


class LedgerFact(Strict):
    name: str
    # Numbers or text. Before smoke-004 this was text-only while the prompt never said so,
    # and nearly every real ledger (``"value": 8600``) failed validation in smoke-003.
    value: str
    quote: str
    source: Literal["base", "followup"]

    @field_validator("value", mode="before")
    @classmethod
    def _value_to_text(cls, v: object) -> object:
        if isinstance(v, bool):
            return v
        return str(v) if isinstance(v, int | float) else v


class RuleCheck(Strict):
    left_label: str
    left_value: float
    comparator: Literal[">", ">=", "<", "<="]
    right_label: str
    right_value: float
    satisfied: bool


class PremiseLedger(Strict):
    """Model-written premise state: extracted facts with quoted spans, declared priority,
    an interpretation of the latest message, and the model's own rule application."""

    facts: list[LedgerFact] = Field(default_factory=list)
    priority: str = ""
    priority_quote: str = ""
    interpretation: str = "initial_request"
    interpretation_quote: str = ""
    missing_required: list[str] = Field(default_factory=list)
    rule_check: RuleCheck | None = None

    @field_validator("interpretation")
    @classmethod
    def _interp_ok(cls, v: str) -> str:
        if v not in UPDATE_INTERPRETATIONS:
            raise ValueError(f"unknown interpretation {v!r}")
        return v


OutputStatus = Literal["valid", "refusal", "invalid", "missing"]


class ParsedOutput(Strict):
    """Strict parse of one raw completion.

    ``valid``: a final ``DECISION: <code>`` line naming an offered option (this includes
    ``need_more_information``). ``refusal``: no decision line and explicit refusal language.
    ``invalid``: anything else that produced text. ``missing``: no text (backend error).
    For ``kind="hypothesis"`` (a search node that only proposes a premise ledger) ``valid``
    means the ledger and the ``SUPPORTED:`` line both parsed.
    """

    kind: Literal["decision", "hypothesis"] = "decision"
    status: OutputStatus
    choice: str | None = None
    ledger: PremiseLedger | None = None
    hypothesis_supported: bool | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _choice_iff_valid(self) -> ParsedOutput:
        # Hypothesis nodes (premise search, depth 1) carry a ledger but no decision.
        if self.kind == "decision" and (self.status == "valid") != (self.choice is not None):
            raise ValueError("choice must be set exactly when status is valid")
        return self


Turn = Literal["base", "followup"]
ConditionName = Literal[
    "direct",
    "structured",
    "best_of_n",
    "premise_search",
    # Full-heuristic vs format-only scoring ablation (same search, budget and seeds).
    "premise_search_formatonly",
    # Legacy name of the same ablation, used by format-001; kept so old runs still load.
    "premise_search_noprov",
]


class CallRecord(Strict):
    """One model call (one row of predictions.jsonl)."""

    run_id: str
    system: str = Field(description="label of the model backend, e.g. hf:<model>@<rev>")
    condition: ConditionName
    case_id: str
    followup_id: str | None
    turn: Turn
    replicate: int
    call_index: int
    call_role: str
    option_order: list[str]
    gen: GenParams
    messages_sha256: str
    messages: list[Message]
    completion: Completion
    parsed: ParsedOutput


class SearchNode(Strict):
    node_id: str
    parent_id: str | None
    depth: int
    hypothesis: str | None
    call_index: int
    status: OutputStatus
    choice: str | None
    ledger: PremiseLedger | None
    score: float
    score_components: dict[str, float]
    kept: bool


class SearchTrace(Strict):
    """Candidate states and non-oracle scores for one turn of best-of-N or premise search."""

    run_id: str
    system: str = Field(description="label of the model backend, e.g. hf:<model>@<rev>")
    condition: ConditionName
    case_id: str
    followup_id: str | None
    turn: Turn
    replicate: int
    nodes: list[SearchNode]
    selected_node_id: str | None
    selection_rule: str


class DecisionRecord(Strict):
    """Final decision of one condition for one turn (one row of decisions.jsonl)."""

    run_id: str
    system: str = Field(description="label of the model backend, e.g. hf:<model>@<rev>")
    condition: ConditionName
    case_id: str
    family_id: str
    followup_id: str | None
    turn: Turn
    replicate: int
    option_order: list[str]
    status: OutputStatus
    choice: str | None
    n_calls: int
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    final_text: str


class Manifest(Strict):
    run_id: str
    created_utc: str
    synthetic: bool
    label: str
    git_sha: str
    git_dirty: bool
    protocol_sha256: str
    data_files: dict[str, str]
    split: Split
    case_ids: list[str]
    conditions: list[ConditionName]
    replicates: int
    systems: dict[str, dict[str, Any]]
    decoding: dict[str, Any]
    budget: dict[str, Any]
    seeds: dict[str, int]
    hardware: dict[str, Any]
    expected_calls: int
    actual_calls: int | None = None
    shard: str = "1/1"
    planned_case_ids: list[str] | None = None  # full case list before sharding
    shard_runs: list[str] | None = None  # set on aggregated runs: the shard run ids merged
    notes: list[str] = Field(default_factory=list)
