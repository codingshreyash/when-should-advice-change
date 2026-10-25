"""Schema contracts: visible records cannot carry labels; parsed outputs are consistent."""

import pytest
from pydantic import ValidationError

from warranted_revision.schema import (
    NEED_MORE_INFO,
    OptionSpec,
    ParsedOutput,
    PremiseLedger,
    VisibleCase,
    VisibleFollowUp,
)

from .conftest import DEV_INPUTS


def _case(**extra):
    return dict(
        case_id="c",
        family_id="f",
        split="dev",
        narrative="x" * 50,
        question="q?",
        options=[
            {"code": "a", "text": "Do A"},
            {"code": "b", "text": "Do B"},
            {"code": NEED_MORE_INFO, "text": "More info"},
        ],
        followups=[{"followup_id": "fu_0123456789ab", "text": "some follow-up"}],
        **extra,
    )


def test_visible_case_rejects_gold_fields():
    VisibleCase.model_validate(_case())
    for leak in ({"gold_base_action": "a"}, {"expected": "a"}, {"contrast_class": "x"}):
        with pytest.raises(ValidationError):
            VisibleCase.model_validate(_case(**leak))


def test_visible_followup_rejects_class_and_label():
    with pytest.raises(ValidationError):
        VisibleFollowUp(followup_id="fu_0123456789ab", text="hello there", gold_action="a")
    with pytest.raises(ValidationError):  # ids must be opaque hashes
        VisibleFollowUp(followup_id="pressure_for_incorrect", text="hello there")


def test_options_require_need_more_information():
    bad = _case()
    bad["options"] = bad["options"][:2] + [{"code": "c", "text": "Do C"}]
    with pytest.raises(ValidationError):
        VisibleCase.model_validate(bad)
    with pytest.raises(ValidationError):
        OptionSpec(code="Bad Code", text="xyz")


def test_parsed_output_choice_iff_valid():
    ParsedOutput(status="valid", choice="a")
    with pytest.raises(ValidationError):
        ParsedOutput(status="valid")
    with pytest.raises(ValidationError):
        ParsedOutput(status="refusal", choice="a")
    ParsedOutput(kind="hypothesis", status="valid", hypothesis_supported=True)


def test_ledger_interpretation_vocabulary():
    PremiseLedger(interpretation="changed_goal")
    with pytest.raises(ValidationError):
        PremiseLedger(interpretation="pressure_for_incorrect")


def test_frozen_inputs_validate():
    rows = [VisibleCase.model_validate_json(ln) for ln in DEV_INPUTS.read_text().splitlines()]
    assert len(rows) == 40
