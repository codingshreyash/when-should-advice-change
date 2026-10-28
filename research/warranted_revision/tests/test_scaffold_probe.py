"""Scaffold probe: item file, prompt anatomy per cell, call plan and gate logic (CPU only)."""

import json

import pytest

from warranted_revision import prompts as P
from warranted_revision.generate import sha256_file
from warranted_revision.probe_analysis import analyse
from warranted_revision.runner import PKG_ROOT
from warranted_revision.scaffold_probe import (
    DECISION_TURN,
    LENGTH_CAP,
    ProbeConfig,
    ProbeFakeBackend,
    expected_calls,
    run,
)
from warranted_revision.schema import VisibleCase

CFG = PKG_ROOT / "configs" / "scaffold_probe_stage1.json"
ITEMS = PKG_ROOT / "data" / "scaffold_probe_v1"
INPUTS = PKG_ROOT / "data" / "challenge_v1" / "challenge_inputs.jsonl"


def _cfg(policy, run_id):
    raw = json.loads(CFG.read_text())
    raw.update(run_id=run_id, systems=[{"kind": "fake", "name": policy}])
    return ProbeConfig.model_validate(raw)


def test_item_file_is_frozen_and_reuses_challenge_texts():
    freeze = json.loads((ITEMS / "FREEZE.json").read_text())
    assert sha256_file(ITEMS / "items.jsonl") == freeze["items_sha256"]
    assert sha256_file(INPUTS) == freeze["source_inputs_sha256"]
    items = {
        r["case_id"]: r for r in map(json.loads, (ITEMS / "items.jsonl").read_text().splitlines())
    }
    for line in INPUTS.read_text().splitlines():
        case = VisibleCase.model_validate_json(line)
        mine = items[case.case_id]
        probe_texts = {t for k in ("insist", "emotional", "neutral") for t in mine[k].values()}
        probe_texts.add(mine["pushback"])
        challenge_texts = {f.text for f in case.followups}
        # every challenge pressure, pushback and neutral text is reproduced verbatim; the only
        # new text per case is the neutral mention of the other option
        reused = {t for t in challenge_texts if t in probe_texts}
        assert len(probe_texts - challenge_texts) == 1
        assert len(reused) == 6


def test_stage1_plan_matches_the_written_budget():
    assert expected_calls(ProbeConfig.model_validate(json.loads(CFG.read_text()))) == 970


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("probe")
    return {p: run(_cfg(p, f"t-{p}"), out_root=root) for p in ("stubborn", "deferential")}


def _calls(run_dir):
    return [json.loads(ln) for ln in (run_dir / "probe_calls.jsonl").read_text().splitlines()]


def test_prompt_anatomy_per_cell(runs):
    rows = _calls(runs["stubborn"])
    base = {(r["case_id"], r["order"]): r for r in rows if r["step"] == "base"}
    for r in rows:
        if r["step"] in ("base", "repro"):
            continue
        b = base[(r["case_id"], r["order"])]
        # the base turn is byte-identical in every cell, item and step
        assert r["messages"][:2] == b["messages"]
        assert r["messages"][2]["content"] == b["text"]
        last = r["messages"][-1]["content"]
        if r["cell"] == "S0" and r["step"] == "decision":
            assert last.endswith("Options:\n" + last.split("Options:\n")[1])
            assert last.endswith(P.DIRECT_FORMAT) and "Options:" in last
        if r["cell"] == "S3" and r["step"] == "free":
            assert (
                "Options:" not in last and P.DECISION_RULE not in last and last.endswith(LENGTH_CAP)
            )
        if r["cell"] == "S3" and r["step"] == "decision":
            assert (
                last.startswith(DECISION_TURN)
                and "Options:" in last
                and last.endswith(P.DIRECT_FORMAT)
            )
    # S0 follow-ups are exactly what the main runner sends for a direct follow-up
    r = next(r for r in rows if r["cell"] == "S0" and r["step"] == "decision")
    case = next(
        VisibleCase.model_validate_json(ln)
        for ln in INPUTS.read_text().splitlines()
        if json.loads(ln)["case_id"] == r["case_id"]
    )
    text = r["messages"][-1]["content"].split("\n\nOptions:")[0]
    assert r["messages"][-1]["content"] == P.with_instructions(
        text, case, r["option_order"], P.DIRECT_FORMAT
    )


def test_away_items_are_keyed_to_the_models_own_base(runs):
    for r in _calls(runs["stubborn"]):
        if r["step"] == "base":
            continue
        assert r["away_option"] != r["base_choice"] and r["away_option"] in r["option_order"][:2]
        if r["item"] == "away_insist" and r["step"] == "free":
            phrase = r["messages"][-1]["content"]
            assert "I should" in phrase


def test_gates_and_branches(runs):
    stub, defer = analyse(runs["stubborn"]), analyse(runs["deferential"])
    assert stub["pass"] and defer["pass"]
    assert stub["branch"].startswith("d") and defer["branch"].startswith("a")
    assert stub["repro"] == {"n": 10, "same_choice": 10, "same_text": 10}
    assert defer["cells"]["S3"]["away_insist"]["switched"] == 20
    assert defer["cells"]["S3"]["neutral_other"]["switched"] == 0


def test_invalid_outputs_fail_the_validity_gate(runs, tmp_path):
    src = runs["stubborn"]
    dst = tmp_path / "broken"
    dst.mkdir()
    (dst / "manifest.json").write_text((src / "manifest.json").read_text())
    rows = _calls(src)
    n = 0
    for r in rows:
        if r["cell"] == "S3" and r["step"] == "decision" and n < 12:
            r.update(status="invalid", choice=None)
            n += 1
    (dst / "probe_calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    res = analyse(dst)
    assert not res["pass"] and any(p.startswith("V2 S3") for p in res["problems"])
    assert res["branch"] is None


class _NmiBaseFake(ProbeFakeBackend):
    """Answers need_more_information on the base turn of one case (regression for R1)."""

    nmi_prefix = ""

    def generate(self, requests):
        out = super().generate(requests)
        return [
            c.model_copy(update={"text": "Not enough to go on.\nDECISION: need_more_information"})
            if len(r.messages) == 2 and r.messages[1].content.startswith(self.nmi_prefix)
            else c
            for r, c in zip(requests, out, strict=True)
        ]


def test_non_actionable_base_does_not_crash_and_is_excluded(tmp_path):
    case = next(
        VisibleCase.model_validate_json(ln)
        for ln in INPUTS.read_text().splitlines()
        if json.loads(ln)["case_id"] == "chal1-car-00"
    )
    fake = _NmiBaseFake("stubborn")
    fake.nmi_prefix = case.narrative[:60]
    cfg = _cfg("stubborn", "t-nmi")
    out = run(cfg, out_root=tmp_path, backends={"x": fake})
    res = analyse(out)
    hit = sum(
        r["step"] == "base" and r["messages"][1]["content"].startswith(fake.nmi_prefix)
        for r in _calls(out)
    )
    assert hit >= 2 and res["base"]["actionable"] == res["base"]["conversations"] - hit
    toward = [
        r
        for r in _calls(out)
        if r["case_id"] == "chal1-car-00" and r["item"] == "toward_insist" and r["step"] != "sample"
    ]
    assert toward and all(r["base_choice"] == "need_more_information" for r in toward)


def test_sampled_readout_redraws_the_first_decision_in_every_cell(runs):
    rows = _calls(runs["stubborn"])
    first = {
        (r["case_id"], r["order"], r["cell"], r["item"]): r["messages_sha256"]
        for r in rows
        if r["step"] == "decision"
    }
    samples = [r for r in rows if r["step"] == "sample"]
    assert samples
    for r in samples:
        assert r["messages_sha256"] == first[(r["case_id"], r["order"], r["cell"], r["item"])]
        assert len(r["messages"]) == (4 if r["cell"] == "S0" else 6)


def test_reproducibility_mismatch_is_reported_not_a_stop(runs, tmp_path):
    src, dst = runs["stubborn"], tmp_path / "repro"
    dst.mkdir()
    (dst / "manifest.json").write_text((src / "manifest.json").read_text())
    rows = _calls(src)
    r = next(r for r in rows if r["step"] == "repro")
    r["choice"] = next(o for o in r["option_order"][:2] if o != r["choice"])
    (dst / "probe_calls.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    res = analyse(dst)
    assert res["pass"] and any(w.startswith("V5") for w in res["warnings"])


def test_confirm_stage_uses_the_stage1_rules(tmp_path):
    raw = json.loads((PKG_ROOT / "configs" / "scaffold_probe_stage2_confirm.json").read_text())
    raw.update(run_id="t-2c", systems=[{"kind": "fake", "name": "deferential"}])
    out = run(ProbeConfig.model_validate(raw), out_root=tmp_path)
    res = analyse(out)
    assert res["pass"] and res["branch"].startswith("a")
    assert res["batch_invariance"]["pairs"] == 0  # 2c has no S5/S6 cells
