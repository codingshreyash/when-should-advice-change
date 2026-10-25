"""Challenge set v1: frozen, audited, dev-only, distinct from v0, never touches holdout."""

import json

from warranted_revision import challenge
from warranted_revision.families import DEV_FAMILIES
from warranted_revision.runner import PKG_ROOT
from warranted_revision.schema import GoldCase, VisibleCase

DIR = PKG_ROOT / "data" / "challenge_v1"


def _load():
    vis = [
        VisibleCase.model_validate_json(ln)
        for ln in (DIR / "challenge_inputs.jsonl").read_text().splitlines()
    ]
    gold = [
        GoldCase.model_validate_json(ln)
        for ln in (DIR / "challenge_gold.jsonl").read_text().splitlines()
    ]
    return vis, gold


def test_frozen_and_reproducible(tmp_path):
    freeze = challenge.write(tmp_path)
    for name, digest in json.loads((DIR / "FREEZE.json").read_text())["files"].items():
        assert (tmp_path / name).read_bytes() == (DIR / name).read_bytes()
        assert freeze["files"][name] == digest


def test_audit_passes_and_is_dev_only():
    vis, gold = _load()
    assert challenge.audit(vis, gold) == []
    assert {g.family_id for g in gold} == set(DEV_FAMILIES)
    assert all(v.case_id.startswith("chal1-") and v.split == "dev" for v in vis)


def test_cases_are_new_instances_not_v0_copies():
    _, gold = _load()
    v0 = [
        GoldCase.model_validate_json(ln)
        for ln in (PKG_ROOT / "data/v0/dev_gold.jsonl").read_text().splitlines()
    ]
    v0_facts = {(g.family_id, tuple((f.name, f.value) for f in g.facts)) for g in v0}
    assert not v0_facts & {(g.family_id, tuple((f.name, f.value) for f in g.facts)) for g in gold}


def test_generator_never_references_holdout():
    src = (PKG_ROOT / "src/warranted_revision/challenge.py").read_text()
    assert "holdout" not in src.replace("never reads holdout", "").lower()
    assert "HOLDOUT_FAMILIES" not in src


def test_controls_on_challenge_set(tmp_path):
    from warranted_revision.evaluate import evaluate_run

    from .conftest import make_run

    ids = ["chal1-refinance-00", "chal1-car-01", "chal1-freelance-02"]
    run = make_run(tmp_path, "chal", [{"kind": "control", "name": "oracle"},
                                     {"kind": "control", "name": "always_stay_put"},
                                     {"kind": "fake", "name": "first_option"}],
                   conditions=["direct", "premise_search"], case_ids=ids,
                   inputs=DIR / "challenge_inputs.jsonl", gold=DIR / "challenge_gold.jsonl")
    m = evaluate_run(run, DIR / "challenge_gold.jsonl", n_draws=100)
    arms = {(a["system"], a["condition"]): a for a in m["arms"]}
    o = arms[("control:oracle", "direct")]["challenge"]
    assert o["stability_all_styles"]["value"] == 1.0 and o["insist"]["movement_beyond_neutral_mention"] == 0.0
    sp = arms[("control:always_stay_put", "premise_search")]
    assert sp["challenge"]["stability_all_styles"]["value"] == 1.0
    assert sp["axis_warranted_update"]["value"] == 0.0
