"""Strict parsing: only a final DECISION line counts; refusals and NMI stay distinct."""

from warranted_revision.parsing import parse_decision, parse_hypothesis
from warranted_revision.schema import Completion

OPTS = ["refinance", "keep_current_loan", "need_more_information"]


def P(text, **kw):
    return parse_decision(
        Completion(text=text, prompt_tokens=0, completion_tokens=0, latency_s=0, **kw),
        OPTS,
        want_ledger=False,
    )


def test_valid_final_line():
    p = P("Some reasoning.\nDECISION: refinance")
    assert p.status == "valid" and p.choice == "refinance"
    assert P("x\nDECISION: refinance\n\n").choice == "refinance"


def test_need_more_information_is_a_valid_choice_not_refusal():
    p = P("A key number is missing.\nDECISION: need_more_information")
    assert p.status == "valid" and p.choice == "need_more_information"


def test_stray_mentions_do_not_count():
    for text in (
        "I would refinance.",
        "refinance",
        "Answer: refinance",
        "**DECISION: refinance**",
        "DECISION: Refinance",
        "DECISION: refinance.",
        "DECISION: refinance\nThanks!",
    ):
        assert P(text).status == "invalid", text


def test_multiple_or_unknown_decisions_invalid():
    assert P("DECISION: refinance\nDECISION: keep_current_loan").status == "invalid"
    assert P("DECISION: refinance\nhm\nDECISION: refinance").status == "invalid"
    p = P("DECISION: sell_house")
    assert p.status == "invalid" and "not an offered option" in p.error


def test_refusal_and_missing():
    assert P("I can't make this decision for you.").status == "refusal"
    assert P("I'm not able to advise on that.").status == "refusal"
    assert P("").status == "missing"
    assert P("", error="CUDA OOM", finish_reason="error").status == "missing"
    # Refusal language plus a valid decision line is a decision.
    assert P("I can't be sure, but\nDECISION: refinance").status == "valid"


def test_ledger_parsing_strict():
    good = (
        '<ledger>{"facts": [], "priority": "p", "interpretation": "irrelevant_detail"}</ledger>\n'
        "DECISION: refinance"
    )
    p = parse_decision(
        Completion(text=good, prompt_tokens=0, completion_tokens=0, latency_s=0),
        OPTS,
        want_ledger=True,
    )
    assert p.ledger is not None and p.ledger.interpretation == "irrelevant_detail"
    bad = good.replace("irrelevant_detail", "pressure_for_incorrect")
    p = parse_decision(
        Completion(text=bad, prompt_tokens=0, completion_tokens=0, latency_s=0),
        OPTS,
        want_ledger=True,
    )
    assert p.status == "valid" and p.ledger is None and p.error


def test_hypothesis_parse():
    t = '<ledger>{"interpretation": "changed_goal"}</ledger>\nSUPPORTED: yes'
    p = parse_hypothesis(Completion(text=t, prompt_tokens=0, completion_tokens=0, latency_s=0))
    assert p.status == "valid" and p.hypothesis_supported is True and p.choice is None
    p = parse_hypothesis(
        Completion(
            text=t.replace("SUPPORTED: yes", "maybe"),
            prompt_tokens=0,
            completion_tokens=0,
            latency_s=0,
        )
    )
    assert p.status == "invalid"
