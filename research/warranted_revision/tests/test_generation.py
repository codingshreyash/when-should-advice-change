"""Data generation: determinism, frozen hashes, reference-rule labels, invariants, splits."""

import json

from warranted_revision import generate
from warranted_revision.families import DEV_FAMILIES, FAMILIES, HOLDOUT_FAMILIES
from warranted_revision.schema import NEED_MORE_INFO, ContrastClass, GoldCase, VisibleCase

from .conftest import DATA


def _load(split):
    vis = [
        VisibleCase.model_validate_json(ln)
        for ln in (DATA / f"{split}_inputs.jsonl").read_text().splitlines()
    ]
    gold = [
        GoldCase.model_validate_json(ln)
        for ln in (DATA / f"{split}_gold.jsonl").read_text().splitlines()
    ]
    return vis, gold


def test_frozen_files_match_hashes():
    assert generate.check_frozen(DATA) == []


def test_regeneration_is_byte_identical(tmp_path):
    generate.write_all(tmp_path)
    for name in json.loads((DATA / "FREEZE.json").read_text())["files"]:
        assert (tmp_path / name).read_bytes() == (DATA / name).read_bytes(), name


def test_audit_passes_and_catches_tampering():
    for split in ("dev", "holdout"):
        vis, gold = _load(split)
        assert generate.audit(vis, gold) == []
    vis, gold = _load("dev")
    g = gold[0]
    wrong = next(a for a in FAMILIES[g.family_id].options if a != g.gold_base_action)
    tampered = [g.model_copy(update={"gold_base_action": wrong})] + gold[1:]
    assert any("base label" in e for e in generate.audit(vis, tampered))


def test_split_is_by_family_and_disjoint():
    assert not set(DEV_FAMILIES) & set(HOLDOUT_FAMILIES)
    assert set(DEV_FAMILIES) | set(HOLDOUT_FAMILIES) == set(FAMILIES)
    for split, fams in (("dev", DEV_FAMILIES), ("holdout", HOLDOUT_FAMILIES)):
        vis, _ = _load(split)
        assert {v.family_id for v in vis} == set(fams)
        assert all(v.split == split for v in vis)
    smoke = json.loads((DATA / "smoke_case_ids.json").read_text())
    assert all(s.startswith("dev-") for s in smoke)


def test_families_are_distinct_templates():
    intros = {f.intro for f in FAMILIES.values()}
    rules = {p.rule_description for f in FAMILIES.values() for p in f.priorities}
    assert len(intros) == len(FAMILIES) >= 8
    assert len(rules) == 2 * len(FAMILIES)


def test_labels_follow_reference_rule_and_balance():
    vis, gold = _load("dev")
    for g in gold:
        fam = FAMILIES[g.family_id]
        facts = {f.name: f.value for f in g.facts}
        assert fam.priority(g.priority_id).action(facts) == g.gold_base_action
        by_cls = {f.contrast_class: f for f in g.followups}
        assert by_cls[ContrastClass.relevant_fact].gold_action != g.gold_base_action
        assert by_cls[ContrastClass.changed_priority].gold_action != g.gold_base_action
        assert by_cls[ContrastClass.missing_information].gold_action == NEED_MORE_INFO
        for c in (
            ContrastClass.subthreshold_fact,
            ContrastClass.irrelevant_fact,
            ContrastClass.pressure_for_correct,
            ContrastClass.pressure_for_incorrect,
            ContrastClass.neutral_mention,
        ):
            assert by_cls[c].gold_action == g.gold_base_action
    # Base actions and priorities are balanced within each family.
    for fid in DEV_FAMILIES:
        acts = [g.gold_base_action for g in gold if g.family_id == fid]
        pris = [g.priority_id for g in gold if g.family_id == fid]
        assert len(set(acts)) == 2 and acts.count(acts[0]) == len(acts) // 2
        assert pris.count(pris[0]) == len(pris) // 2


def test_pressure_is_symmetric_and_not_a_goal_change():
    vis, gold = _load("dev")
    for v, g in zip(vis, gold, strict=True):
        text = {f.followup_id: f.text for f in v.followups}
        by_cls = {f.contrast_class: text[f.followup_id] for f in g.followups}
        for c in (ContrastClass.pressure_for_correct, ContrastClass.pressure_for_incorrect):
            t = by_cls[c]
            assert "priority" not in t.lower() and not any(ch.isdigit() for ch in t)
        assert "priority is different now" in by_cls[ContrastClass.changed_priority]
        gp = {f.contrast_class: f for f in g.followups}
        assert gp[ContrastClass.pressure_for_correct].provenance.authority == "none"
        assert gp[ContrastClass.changed_priority].provenance.authority == "goal_owner"
        assert gp[ContrastClass.relevant_fact].provenance.substantiated


def test_followup_ids_and_order_do_not_reveal_class():
    vis, gold = _load("dev")
    positions = {}
    for v, g in zip(vis, gold, strict=True):
        cls = {f.followup_id: f.contrast_class for f in g.followups}
        for i, f in enumerate(v.followups):
            assert f.followup_id.startswith("fu_") and cls[f.followup_id].value not in f.followup_id
            positions.setdefault(cls[f.followup_id], set()).add(i)
    assert all(len(p) > 1 for p in positions.values())
