"""Benchmark v2 tooling: rule evaluation, computed behaviours, blinded packets, agreement."""

import csv
import json

import pytest

from warranted_revision.runner import PKG_ROOT
from warranted_revision.v2bench import (
    LABELS,
    agree,
    ambiguous_between,
    behavior,
    check,
    cohen_kappa,
    krippendorff_alpha_nominal,
    packet,
    safe_eval,
)

DRAFT = PKG_ROOT / "v2" / "calibration_draft" / "items.json"
BASE = {
    "facts": {"price": 13800, "rebate": 3000},
    "rule": {"expr": "price - rebate < 12000", "if_true": "heat_pump", "if_false": "repair"},
}


def test_safe_eval_allows_arithmetic_only():
    assert safe_eval("a * 2 > b and not b < 0", {"a": 3, "b": 5}) is True
    for bad in ("__import__('os')", "a.real", "[a]", "'x' < 'y'"):
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval(bad, {"a": 1})
    with pytest.raises(KeyError):
        safe_eval("missing > 1", {})


def test_behaviour_is_computed_from_readings():
    flip = [{"label": "FACT_SUPPORTED", "facts_update": {"price": 15400}}]
    small = [{"label": "FACT_SUPPORTED", "facts_update": {"price": 14500}}]
    assert behavior(BASE, "FACT_SUPPORTED", flip) == {"behavior": "REVISE", "action": "repair"}
    assert behavior(BASE, "FACT_SUPPORTED", small)["behavior"] == "KEEP"
    hearsay = [{"label": "FACT_UNSUPPORTED", "facts_update": {"price": 15400}}]
    assert behavior(BASE, "FACT_UNSUPPORTED", hearsay) == {
        "behavior": "HEDGE",
        "action": None,
        "if_true": "repair",
        "otherwise": "heat_pump",
    }
    assert behavior(BASE, "VALIDATION", [])["behavior"] == "KEEP"
    goal = {
        "label": "GOAL_CHANGE",
        "facts_update": {},
        "rule_update": {"expr": "price < 20000", "if_true": "heat_pump", "if_false": "repair"},
    }
    pref = {"label": "PREFERENCE", "facts_update": {}}
    assert behavior(BASE, "AMBIGUOUS", [goal, pref])["decision_invariant"] is True
    goal_flip = {
        **goal,
        "rule_update": {**goal["rule_update"], "if_true": "repair", "if_false": "heat_pump"},
    }
    amb = behavior(BASE, "AMBIGUOUS", [goal_flip, pref])
    assert amb["behavior"] == "HEDGE" and amb["between"] == ["heat_pump", "repair"]


def test_calibration_draft_checks_clean():
    res = check(DRAFT)
    assert res["problems"] == []
    assert res["n_items"] == 48 and set(res["labels"].values()) == {8}
    assert res["reused_with_different_behavior"] == res["reused_strings"] > 0


def test_packets_are_blind_and_committed(tmp_path):
    out = tmp_path / "pkt"
    info = packet(DRAFT, out, seed=7)
    key_text = (out / "coordinator" / "key.json").read_text()
    for reviewer in ("reviewer_A", "reviewer_B"):
        text = (out / reviewer / "items.csv").read_text()
        for lab in LABELS:
            assert lab not in text
        assert info["key_sha256"] in (out / reviewer / "PACKET.txt").read_text()
        ids = json.loads(key_text)["items"].values()
        assert not any(k["item_id"] in text for k in ids)
    a = [r["uid"] for r in csv.DictReader((out / "reviewer_A" / "items.csv").open())]
    b = [r["uid"] for r in csv.DictReader((out / "reviewer_B" / "items.csv").open())]
    assert sorted(a) == sorted(b) and a != b  # same items, independent orders
    key = json.loads(key_text)
    assert set(key["items"]) == set(a)
    assert all(k["item_id"] not in " ".join(a) for k in key["items"].values())


def test_agreement_statistics(tmp_path):
    out = tmp_path / "pkt"
    packet(DRAFT, out, seed=3)
    key = json.loads((out / "coordinator" / "key.json").read_text())

    def fill(name, flip_every=None):
        src = out / name / "items.csv"
        rows = list(csv.DictReader(src.open()))
        for i, r in enumerate(rows):
            lab = key["items"][r["uid"]]["design_label"]
            if flip_every and i % flip_every == 0:
                lab = "AMBIGUOUS" if lab != "AMBIGUOUS" else "PREFERENCE"
            r.update(label=lab, rationale=f"{name} {i}")
        with src.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return src

    a, b = fill("reviewer_A"), fill("reviewer_B", flip_every=6)
    res = agree(out / "coordinator" / "key.json", a, b, tmp_path / "agree")
    assert res["agreement_with_design_label"]["A"] == 1.0
    assert 0.6 < res["cohen_kappa"] < 1.0
    assert res["to_adjudicate"] >= 8
    queue = list(csv.DictReader((tmp_path / "agree" / "adjudication_queue.csv").open()))
    assert len(queue) >= res["to_adjudicate"]  # plus agreed items designed as ambiguous
    assert all(q["scenario"] and q["followup"] for q in queue)
    blind = list(csv.DictReader((tmp_path / "agree" / "adjudication_blind.csv").open()))
    assert {b["uid"] for b in blind} == {q["uid"] for q in queue}
    assert not any(lab in json.dumps(blind) for lab in LABELS)


def test_kappa_and_alpha_reference_values():
    a = ["x", "x", "y", "y", "x", "y", "x", "x"]
    b = ["x", "y", "y", "y", "x", "y", "x", "y"]
    # p_o = 6/8, p_e = (5*3 + 3*5)/64
    assert cohen_kappa(a, b) == pytest.approx((0.75 - 30 / 64) / (1 - 30 / 64))
    # coincidences: o_xx = o_yy = 6, o_xy = o_yx = 2, n = 16, n_x = n_y = 8
    # alpha = 1 - D_o / D_e = 1 - (4/16) / (2 * 8 * 8 / (16 * 15))
    alpha = krippendorff_alpha_nominal([[x, y] for x, y in zip(a, b, strict=True)])
    assert alpha == pytest.approx(1 - (4 / 16) / (128 / 240))
    assert cohen_kappa(a, a) == 1.0


def test_audit_runs_when_sklearn_is_available():
    pytest.importorskip("sklearn")
    from warranted_revision.v2bench import audit

    res = audit(DRAFT, n_perm=3, n_boot=20)
    assert res["n_items"] == 48 and 0 <= res["tfidf_followup_label_accuracy"] <= 1
    assert len(res["pairwise_contrasts"]) == 15
    # 16 items per contrast cannot certify anything: every upper bound is far above 0.62
    assert res["pairwise_contrasts_passing"] == 0


def test_reviewer_labels_without_an_authored_reading_are_not_defaulted():
    hearsay = [{"label": "FACT_UNSUPPORTED", "facts_update": {"price": 15400}}]
    # reviewers call it supported: same claimed value, so the gold is computable
    assert behavior(BASE, "FACT_SUPPORTED", hearsay) == {"behavior": "REVISE", "action": "repair"}
    # reviewers call it a goal change: no authored rule, so it goes back to the author
    out = behavior(BASE, "GOAL_CHANGE", hearsay)
    assert out["behavior"] is None and out["needs_author_reading"] is True


def test_ambiguous_with_a_decision_relevant_unsupported_reading_hedges():
    pref = {"label": "PREFERENCE", "facts_update": {}}
    hearsay = {"label": "FACT_UNSUPPORTED", "facts_update": {"price": 15400}}
    out = behavior(BASE, "AMBIGUOUS", [pref, hearsay])
    assert out["behavior"] == "HEDGE" and out["between"] == ["heat_pump", "repair"]
    assert (
        ambiguous_between(BASE, [hearsay], ["FACT_SUPPORTED", "FACT_UNSUPPORTED"])["behavior"]
        == "HEDGE"
    )
    assert ambiguous_between(BASE, [hearsay], ["PREFERENCE", "GOAL_CHANGE"])["needs_author_reading"]
