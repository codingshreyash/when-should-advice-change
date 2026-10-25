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


def test_satisfied_means_the_written_comparison_holds():
    from warranted_revision.schema import RuleCheck
    from warranted_revision.scoring import arithmetic

    def rc(left, comp, right, sat):
        return PremiseLedger(
            rule_check=RuleCheck(
                left_label="drive_hours",
                left_value=left,
                comparator=comp,
                right_label="max_hours",
                right_value=right,
                satisfied=sat,
            )
        )

    # True comparisons: consistent only with satisfied=True, even when the user's broader
    # requirement fails (a 6 h drive exceeds a 4 h limit, so the user would not move).
    assert arithmetic(rc(6, ">", 4, True)) == 1.0
    assert arithmetic(rc(6, ">", 4, False)) == 0.0
    assert arithmetic(rc(4, ">=", 4, True)) == 1.0
    # False comparisons: consistent only with satisfied=False, even when the requirement holds
    # (2 h is within the 4 h limit, but "2 > 4" is false as written).
    assert arithmetic(rc(2, ">", 4, False)) == 1.0
    assert arithmetic(rc(2, ">", 4, True)) == 0.0
    assert arithmetic(rc(5, "<", 3, False)) == 1.0
    assert arithmetic(rc(3, "<=", 2.5, True)) == 0.0


def test_prompt_defines_satisfied_strictly():
    from warranted_revision import prompts as P

    assert "true as written" in P.STRUCTURED_FORMAT
    assert "requirement is not met" in P.STRUCTURED_FORMAT
    assert '"satisfied": "<true or false>"' in P.LEDGER_TEMPLATE


def test_tiebreak_keys_ignore_list_order_and_are_seeded():
    from warranted_revision.conditions import tiebreak_keys

    hyps = ["new_or_corrected_fact", "changed_goal", "irrelevant_detail"]
    a = dict(zip(hyps, tiebreak_keys("root-1", hyps), strict=True))
    b = dict(zip(hyps[::-1], tiebreak_keys("root-1", hyps[::-1]), strict=True))
    assert a == b  # same key per reading whatever the list order
    assert tiebreak_keys("root-2", hyps) != tiebreak_keys("root-1", hyps)
    base = tiebreak_keys("root-1", ["initial_request"] * 5)
    assert len(set(base)) == 5  # repeated readings get distinct keys
