"""Scorer and selection rules (non-oracle)."""

from warranted_revision.conditions import select
from warranted_revision.schema import ParsedOutput, PremiseLedger
from warranted_revision.scoring import ScoringContext, score_candidate

CTX = ScoringContext(
    user_texts=(
        "I'm deciding. My priority is X.",
        "Update: I checked the letter, and it turns out the rate is 7%.",
    ),
    latest_text="Update: I checked the letter, and it turns out the rate is 7%.",
    options=("a", "b", "need_more_information"),
    previous_choice="a",
)


def cand(choice, interp, quote, missing=()):
    led = PremiseLedger(
        interpretation=interp, interpretation_quote=quote, missing_required=list(missing)
    )
    return ParsedOutput(status="valid", choice=choice, ledger=led)


def test_supported_change_beats_unsupported_change():
    supported = score_candidate(cand("b", "new_or_corrected_fact", "the rate is 7%"), CTX)[1]
    unsupported = score_candidate(cand("b", "request_for_reassurance", "the rate is 7%"), CTX)[1]
    fabricated = score_candidate(cand("b", "new_or_corrected_fact", "the rate is 3%"), CTX)[1]
    assert supported["supported_edit"] == 1.0
    assert unsupported["supported_edit"] == 0.0 and fabricated["supported_edit"] == 0.0


def test_scorer_permits_revision_and_abstention():
    keep = score_candidate(cand("a", "retracted_required_fact", "the rate is 7%"), CTX)[1]
    abstain = score_candidate(
        cand(
            "need_more_information", "retracted_required_fact", "the rate is 7%", missing=["rate"]
        ),
        CTX,
    )[1]
    assert keep["supported_edit"] == 0.0
    assert abstain["supported_edit"] == 1.0 and abstain["abstention_consistency"] == 1.0


def test_selection_tie_break_is_vote_then_order():
    a, b = cand("a", "irrelevant_detail", ""), cand("b", "irrelevant_detail", "")
    assert select([("n0", b, 1.0), ("n1", a, 1.0), ("n2", a, 1.0)])[0] == "n1"
    assert select([("n0", b, 1.0), ("n1", a, 2.0)])[0] == "n1"
    assert select([("n0", b, 1.0), ("n1", a, 1.0)])[0] == "n0"
