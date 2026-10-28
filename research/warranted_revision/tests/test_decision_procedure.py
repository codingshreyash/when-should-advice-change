"""CS 1684 decision-procedure experiment: CPU tests with fake backends (no model, no GPU)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tarfile
from itertools import product
from pathlib import Path

import pytest

from warranted_revision import decision_procedure as dp
from warranted_revision import decision_procedure_analysis as dpa

PKG = Path(__file__).resolve().parents[1]
FULL = PKG / "configs" / "decision_procedure_full.json"
PILOT = PKG / "configs" / "decision_procedure_pilot.json"
CORE = (
    "base",
    "pressure",
    "reframe",
    "relevant_update",
    "subthreshold_update",
    "irrelevant_update",
    "omission",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("RANDOMIZE_OPTIONS", "OPTION_ORDER_SEED", "ORDER_PER_VARIANT"):
        monkeypatch.delenv(k, raising=False)


def _load(path: Path, name: str):
    if not path.exists():  # e.g. on the GPU box, whose bundle carries only what the run reads
        pytest.skip(f"{path} not in this checkout")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scenarios():
    return {
        s["id"]: s
        for s in map(
            json.loads, dp.resolve("data/derived/pressure_controls.jsonl").read_text().splitlines()
        )
    }


def small_cfg(**kw):
    raw = json.loads(FULL.read_text()) | kw
    return dp.DPConfig.model_validate(raw)


# --------------------------------------------------------------------------- frozen inputs


def test_configs_lock_and_call_counts():
    dp.check_lock()
    full, pilot = dp.load_config(FULL), dp.load_config(PILOT)
    dp.check_config_locked(full)
    dp.check_config_locked(pilot)
    assert dp.plan(full)["calls"] == 4800 == full.max_calls
    assert dp.plan(full, preflight=True)["calls"] == 64
    assert dp.plan(pilot)["calls"] == 128 == pilot.max_calls
    assert pilot.technical_pilot and not full.technical_pilot
    assert full.nimble.revision.startswith("594dfdcf") and full.base.revision.startswith("c2022362")
    assert {a.name: (a.weights, a.procedure) for a in full.arms} == {
        "A": ("base", "scorer"),
        "B": ("base", "constrained"),
        "C": ("base", "conversational"),
        "D": ("nimble", "scorer"),
    }


def test_launch_config_must_match_a_locked_config():
    cfg = dp.load_config(FULL)
    dp.check_config_locked(cfg.model_copy(update={"run_id": "other", "out_root": "/x"}))
    with pytest.raises(dp.GateError):
        dp.check_config_locked(cfg.model_copy(update={"samples": 4}))


def test_lock_detects_drift(tmp_path, monkeypatch):
    lock = json.loads(dp.LOCK.read_text())
    lock["sha256"]["scripts/lib/prompts.py"] = "0" * 64
    bad = tmp_path / "lock.json"
    bad.write_text(json.dumps(lock))
    monkeypatch.setattr(dp, "LOCK", bad)
    with pytest.raises(dp.GateError, match="prompts.py"):
        dp.check_lock()


def test_pressure_controls_match_the_career_files():
    car = {}
    for f in ("career_pilot", "career_v2"):
        for line in dp.resolve(f"data/scenarios/{f}.jsonl").read_text().splitlines():
            s = json.loads(line)
            car[s["id"]] = s
    pc = scenarios()
    assert sorted(pc) == sorted(car) and len(pc) == 30
    for sid, s in pc.items():
        for v in CORE:
            assert s["prompts"][v] == car[sid]["prompts"][v]
        for k in ("options", "option_text", "question", "pressure_target"):
            assert s[k] == car[sid][k]
        assert "mention_target" in s["prompts"]


def test_prompts_are_the_original_project_functions():
    cfg = dp.load_config(FULL)
    pm = dp.load_prompts_module(cfg.option_order_seed)
    pc = scenarios()
    items = dp.build_items(cfg)
    for it in items[::37]:
        s = pc[it.id]
        ordered = pm.ordered_scenario(s, it.variant, it.sample)
        assert list(it.option_order) == ordered["options"]
        if it.procedure == "scorer":
            assert it.text == s["prompts"][it.variant]
            assert it.schema == pm.nimble_schema(ordered)
        elif it.procedure == "constrained":
            assert it.text == pm.chat_prompt_constrained(ordered, it.variant)
        else:
            assert it.text == pm.chat_prompt_conversational(ordered, it.variant)


def test_option_order_is_shared_across_variants_and_arms_but_varies_by_sample():
    items = dp.build_items(dp.load_config(FULL))
    orders: dict[tuple, set] = {}
    for it in items:
        orders.setdefault((it.id, it.sample), set()).add(it.option_order)
    assert all(len(v) == 1 for v in orders.values())
    varied = sum(len({orders[(sid, k)].copy().pop() for k in range(5)}) > 1 for sid in scenarios())
    assert varied >= 25  # permutations differ across replicates for nearly every scenario


def test_per_variant_ordering_switch_is_refused(monkeypatch):
    monkeypatch.setenv("ORDER_PER_VARIANT", "1")
    with pytest.raises(dp.GateError):
        dp.build_items(dp.load_config(FULL))


def test_strict_parser_agrees_with_run_chat():
    run_chat = _load(dp.resolve("scripts/run/run_chat.py"), "run_chat_for_test")
    opts = ["stay", "take_offer", "need_more_information"]
    texts = [
        "take_offer",
        "Advice here.\n\n**stay**",
        "stay\nThanks!",
        "I'd say take_offer.",
        "",
        "need_more_information.",
        "Pick:\n- stay\n",
        "stay_or_go",
        "TAKE_OFFER",
    ]
    for t in texts:
        assert dp.parse_strict(t, opts) == run_chat.parse_code(t, opts)[0], t


def test_contract_check():
    cfg = dp.load_config(FULL)
    dp.check_contract({"model": "Qwen/Qwen3.5-9B", "revision": cfg.base.revision}, cfg)
    with pytest.raises(dp.GateError):
        dp.check_contract({"model": "Qwen/Qwen3.5-9B", "revision": "0" * 40}, cfg)


# --------------------------------------------------------------------------- fake backends


def label_lookup(cfg):
    """text -> label for every prompt the run shows (draft labels; tests only)."""
    pc, out = scenarios(), {}
    for it in dp.build_items(cfg) + (dp.build_items(cfg, preflight=True) if cfg.preflight else []):
        s = pc[it.id]
        out[it.text] = (s["expected"][it.variant], s["expected"]["base"], it.variant, s)
    return out


class FakeScorer:
    """'nimble' answers the draft label; 'base' never moves on relevant updates and always
    moves on irrelevant ones (the opposite of warranted updating)."""

    def __init__(self, weights, lookup, fail=False):
        self.weights, self.lookup, self.fail = weights, lookup, fail

    def score(self, context, schema):
        if self.fail:
            raise RuntimeError("cuda")
        label, base, variant, s = self.lookup[context]
        choices = schema["decision"]["choices"]
        if self.weights == "nimble":
            pick = label
        elif variant == "irrelevant_update":
            pick = next(c for c in choices if c != base)
        else:
            pick = base
        return {
            "output": {"decision": pick},
            "revision": "x" * 40,
            "temperature": 1.0,
            "fields": {
                "decision": {
                    "scores": {c: float(c == pick) for c in choices},
                    "logits": {c: 0.0 for c in choices},
                    "prompt_token_count": 10,
                }
            },
        }


class FakeGenerator:
    def __init__(self, lookup, bad_variant=None):
        self.lookup, self.bad_variant = lookup, bad_variant

    def generate(self, prompts, max_new_tokens):
        out = []
        for p in prompts:
            label, _, variant, _ = self.lookup[p]
            text = "Some advice." if variant == self.bad_variant else f"Some advice.\n{label}"
            out.append(
                dp.GenOut(text if "short paragraph" in p else text.split("\n")[-1], 5, "stop")
            )
        return out


def fake_backends(cfg, **kw):
    lookup = label_lookup(cfg)
    return dp.Backends(
        scorer=lambda w: FakeScorer(w, lookup, kw.get("fail_scorer", False)),
        generator=lambda: FakeGenerator(lookup, kw.get("bad_variant")),
        info=lambda: {"fake": True},
    )


class Clock:
    def __init__(self, step=0.5):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


def test_fake_run_writes_rows_and_passes_the_gate(tmp_path):
    cfg = dp.load_config(PILOT)
    man = dp.run(cfg, fake_backends(cfg), tmp_path / "r", clock=Clock())
    rows = dp.read_rows(tmp_path / "r")
    assert len(rows) == man["planned_calls"] == 128
    assert {r["arm"] for r in rows} == set("ABCD")
    assert all(r["choice_strict"] in r["option_order"] for r in rows)
    assert {r["model"] for r in rows if r["arm"] == "D"} == {
        "bespokelabs/Bespoke-Nimble-9B@594dfdcf"
    }
    assert all("text" not in r for r in rows if r["procedure"] == "scorer")
    s = dp.gate(tmp_path / "r", remaining_min=60, full_cfg=dp.load_config(FULL))
    assert s["passed"] and s["by_arm"]["C"]["parse_rate"] == 1.0
    assert json.loads((tmp_path / "r" / "gate.json").read_text())["passed"]
    with pytest.raises(dp.GateError, match="exists"):
        dp.run(cfg, fake_backends(cfg), tmp_path / "r", clock=Clock())


def test_gate_fails_on_unparseable_variant_and_scorer_errors(tmp_path):
    cfg = dp.load_config(PILOT)
    dp.run(cfg, fake_backends(cfg, bad_variant="omission"), tmp_path / "a", clock=Clock())
    with pytest.raises(dp.GateError, match="arm C: .*omission"):
        dp.gate(tmp_path / "a", remaining_min=60)
    dp.run(cfg, fake_backends(cfg, fail_scorer=True), tmp_path / "b", clock=Clock())
    with pytest.raises(dp.GateError, match="scorer errors"):
        dp.gate(tmp_path / "b", remaining_min=60)
    rows = dp.read_rows(tmp_path / "b")
    assert all(r["error"].startswith("RuntimeError") for r in rows if r["procedure"] == "scorer")


def test_gate_fails_when_the_projection_does_not_fit(tmp_path):
    cfg = dp.load_config(PILOT)
    dp.run(cfg, fake_backends(cfg), tmp_path / "r", clock=Clock(step=60))
    with pytest.raises(dp.GateError, match="projected"):
        dp.gate(tmp_path / "r", remaining_min=10, full_cfg=dp.load_config(FULL))
    with pytest.raises(dp.GateError, match="min left"):
        dp.gate(tmp_path / "r", remaining_min=1)


def test_summary_has_counts_only(tmp_path):
    cfg = dp.load_config(PILOT)
    dp.run(cfg, fake_backends(cfg), tmp_path / "r", clock=Clock())
    text = json.dumps(dp.summarize(tmp_path / "r"))
    for s in scenarios().values():
        for code in s["options"]:
            assert f'"{code}"' not in text


def test_log_transport_round_trip(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(dp, "CHUNK", 2000)  # several chunks, as a real run prints
    cfg = dp.load_config(PILOT)
    run = tmp_path / "r"
    dp.run(cfg, fake_backends(cfg), run, clock=Clock())
    (run / "summary.json").write_text(json.dumps(dp.summarize(run)))
    dp.emit_files(run, ("summary.json",))
    dp.emit_calls(run)
    log = "\n".join(
        f"2026-10-28T12:00:00.0000000Z {ln}" for ln in capsys.readouterr().out.splitlines()
    )
    got = dp.recover(log, tmp_path / "back")
    assert set(got) == {"summary.json", "calls.jsonl"}
    assert (tmp_path / "back" / "calls.jsonl").read_bytes() == (run / "calls.jsonl").read_bytes()
    with pytest.raises(dp.GateError):
        dp.recover(
            "\n".join(ln for ln in log.splitlines() if "DP_CALLS 2/" not in ln), tmp_path / "x"
        )


# --------------------------------------------------------------------------- analysis


#: test-only provenance in the shape `labeling.py score` writes; not a real labelling round
FAKE_PROVENANCE = {
    "labelers": {"A": "test-a", "B": "test-b"},
    "sheet_sha256": {"A": "0" * 64, "B": "1" * 64},
}


def labels_file(tmp_path, mutate=None, provenance=True):
    """Synthetic label file for the analysis code. Its labels are the scenario author's drafts
    with fake provenance; they exercise the code only and are not blind labels."""
    p = tmp_path / "blind.jsonl"
    rows = []
    for s in scenarios().values():
        exp = {v: s["expected"][v] for v in CORE}
        if mutate:
            mutate(s["id"], exp)
        row = {"id": s["id"], "expected": exp, "pressure_target": s["pressure_target"]}
        if provenance:
            row |= {"label_source": "blind", "label_provenance": FAKE_PROVENANCE}
        rows.append(json.dumps(row))
    p.write_text("\n".join(rows) + "\n")
    return p


def full_fake_run(tmp_path, **kw):
    cfg = dp.load_config(FULL)
    dp.run(cfg, fake_backends(cfg, **kw), tmp_path / "full", clock=Clock())
    return tmp_path / "full"


def test_analysis_detects_a_planted_adapter_effect(tmp_path):
    run = full_fake_run(tmp_path)
    res = dpa.analyze(run, [labels_file(tmp_path)])
    n = res["eligible"]["primary"]
    assert n >= dpa.MIN_PRIMARY
    prim = res["main"]["primary"]
    # fake D answers every label (Delta = 1); fake A never takes relevant updates and always
    # moves on irrelevant ones (Delta = -1)
    assert prim["estimate"] == pytest.approx(2.0) and prim["n"] == n
    assert prim["ci95"][0] > 0 and prim["p"] == pytest.approx(2 / 2**n)
    assert res["decision"]["decision"] == "REPLICATE"
    assert (
        res["main"]["per_arm"]["D"]["d_prime"]["d_prime"]
        > res["main"]["per_arm"]["A"]["d_prime"]["d_prime"]
    )
    assert (
        res["validity"]["C"]["passed"]
        and res["main"]["secondary_procedure"]["C-B:Delta"]["evaluable"]
    )


def test_analysis_null_and_invalid_generative_arm(tmp_path):
    run = full_fake_run(tmp_path, bad_variant="pressure")
    res = dpa.analyze(run, [labels_file(tmp_path)])
    assert not res["validity"]["B"]["passed"] and not res["validity"]["C"]["passed"]
    assert res["main"]["secondary_procedure"]["B-A:Press"] == {
        "evaluable": False,
        "why": "an arm failed the validity gate",
        "p_holm": None,
    }
    out = {
        "D": {"s1": {"Delta": 0.2}, "s2": {"Delta": 0.0}},
        "A": {"s1": {"Delta": 0.2}, "s2": {"Delta": 0.0}},
    }
    prim = dpa.paired(out, "D", "A", "Delta", ["s1", "s2"])
    assert prim["estimate"] == 0 and prim["p"] == 1.0
    d = dpa.decide({"estimate": 0.01, "ci95": [-0.05, 0.07]}, {"estimate": 0.01}, True, True)
    assert d == {"decision": "NULL", "kind": "equivalent within ±0.10", "checks": d["checks"]}
    d = dpa.decide({"estimate": 0.2, "ci95": [-0.05, 0.45]}, {"estimate": 0.1}, True, True)
    assert d["kind"] == "inconclusive at this precision"
    d = dpa.decide({"estimate": 0.2, "ci95": [0.05, 0.35]}, {"estimate": -0.1}, True, True)
    assert d["decision"] == "NULL" and not d["checks"]["career_v2_same_sign"]
    assert dpa.decide({}, {}, False, True)["decision"] == "NOT EVALUABLE"
    assert dpa.decide({}, {}, True, False)["decision"] == "UNINTERPRETABLE"


def test_eligibility_rules(tmp_path):
    def mutate(sid, exp):
        if sid == "career_11":
            exp["relevant_update"] = [exp["relevant_update"], exp["base"]]  # labelers disagree
        if sid == "career_12":
            exp["irrelevant_update"] = exp["relevant_update"]  # irrelevant would change the answer

    lab = dpa.load_labels([labels_file(tmp_path, mutate)])
    sets = dpa.eligibility(lab)
    assert "career_11" not in sets["primary"] and "career_12" not in sets["primary"]
    nmi_rel = [sid for sid, x in lab.items() if x["labels"]["relevant_update"] == dpa.NMI]
    assert nmi_rel and not set(nmi_rel) & set(sets["primary"])
    assert all(lab[s]["labels"]["mention_target"] == lab[s]["labels"]["base"] for s in lab)
    assert all(lab[s]["target"] != lab[s]["labels"]["base"] for s in sets["pressure"])


def test_too_few_eligible_scenarios_is_not_evaluable_and_reports_no_estimate(tmp_path):
    run = full_fake_run(tmp_path)

    def mutate(sid, exp):
        if int(sid.split("_")[1]) > 10:
            exp["base"] = [exp["base"], "x"]

    labels = labels_file(tmp_path, mutate)
    res = dpa.analyze(run, [labels])
    assert res["eligible"]["primary"] < dpa.MIN_PRIMARY
    assert res["decision"]["decision"] == "NOT EVALUABLE" and "kind" not in res["decision"]
    for block in ("main", "sensitivity_unparsed_as_change"):
        prim = res[block]["primary"]
        assert prim["evaluated"] is False
        assert not {"estimate", "ci95", "p", "career_v2_only"} & set(prim)
    pre = dpa.eligibility_report([labels])  # the same outcome from the labels alone
    assert pre["eligible"] == res["eligible"] and pre["decision"] == res["decision"]
    assert "decision" not in dpa.eligibility_report([labels_file(tmp_path)])


def test_analysis_refuses_labels_without_blind_provenance(tmp_path):
    with pytest.raises(dpa.LabelError):
        dpa.load_labels([labels_file(tmp_path, provenance=False)])
    for rel in ("data/scenarios/career_pilot.jsonl", "data/scenarios/career_v2.jsonl"):
        with pytest.raises(dpa.LabelError):
            dpa.load_labels([dp.resolve(rel)])
    p = labels_file(tmp_path)
    p.write_text(p.read_text().replace('"test-b"', '"test-a"'))  # one labeler twice
    with pytest.raises(dpa.LabelError):
        dpa.load_labels([p])


def test_analysis_records_label_hashes_and_completeness(tmp_path):
    run = full_fake_run(tmp_path)
    labels = labels_file(tmp_path)
    res = dpa.analyze(run, [labels])
    assert res["label_sha256"] == {str(labels): dp.sha256(labels)}
    man = json.loads((run / "manifest.json").read_text())
    assert res["completeness"]["planned_calls"] == man["planned_calls"]
    assert res["completeness"]["matches_plan"]


def test_duplicate_rows_are_an_error():
    row = {"arm": "A", "id": "s1", "sample": 0, "variant": "base", "choice_strict": "a"}
    with pytest.raises(ValueError, match="duplicate"):
        dpa.index([row, row | {"choice_strict": "b"}])


def test_unparsed_pairs_drop_or_count_as_change():
    samples = {
        0: {"base": "a", "relevant_update": None, "irrelevant_update": "a"},
        1: {"base": "a", "relevant_update": "b", "irrelevant_update": "a"},
    }
    labels = {"relevant_update": "b", "base": "a"}
    main = dpa.scenario_outcomes(samples, labels, "a")
    sens = dpa.scenario_outcomes(samples, labels, "a", unparsed_as_change=True)
    assert main["H"] == 1.0 and sens["H"] == 1.0 and main["F"] == 0.0
    samples[1]["relevant_update"] = "a"
    assert dpa.scenario_outcomes(samples, labels, "a")["H"] == 0.0
    assert dpa.scenario_outcomes(samples, labels, "a", unparsed_as_change=True)["H"] == 0.5


def test_exact_sign_flip_matches_brute_force():
    diffs = [0.4, -0.2, 0.6, 0.0, 0.2, 0.8, -0.4]
    obs = abs(sum(diffs))
    hits = sum(
        abs(sum(s * d for s, d in zip(signs, diffs, strict=True))) >= obs - 1e-9
        for signs in product((1, -1), repeat=len(diffs))
    )
    assert dpa.sign_flip_p(diffs) == pytest.approx(hits / 2 ** len(diffs))


def test_holm_and_z():
    assert dpa.holm({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx(
        {"a": 0.03, "b": 0.06, "c": 0.06}
    )
    stats = _load(dp.resolve("scripts/lib/stats.py"), "stats_for_test")
    for p, n in ((0.0, 20), (0.35, 23), (1.0, 30)):
        assert dpa.z(p, n) == pytest.approx(stats.z(p, n))


def test_analysis_refuses_the_pilot_and_preflight(tmp_path):
    cfg = dp.load_config(PILOT)
    dp.run(cfg, fake_backends(cfg), tmp_path / "p", clock=Clock())
    with pytest.raises(SystemExit, match="counts only"):
        dpa.analyze(tmp_path / "p", [labels_file(tmp_path)])
    full = dp.load_config(FULL)
    dp.run(full, fake_backends(full), tmp_path / "pre", preflight=True, clock=Clock())
    with pytest.raises(SystemExit, match="counts only"):
        dpa.analyze(tmp_path / "pre", [labels_file(tmp_path)])


# --------------------------------------------------------------------------- controller and bundle


def test_controller_plans_fit_the_caps():
    ctl = _load(PKG / "gpu/brev_controller.py", "ctl_dp")
    for cfg, cap in ((PILOT, "2"), (FULL, "3")):
        args = ctl.argparse.Namespace(
            config=str(cfg),
            run_id="dp-test",
            shard="1/1",
            hourly="1.06",
            max_usd=cap,
            est_seconds_per_call=6.0,
            setup_hours=0.5,
            bench=False,
            instance_type="massedcompute_L40S",
        )
        plan = ctl.build_plan(args)
        assert plan["budget"]["worst_case_usd"] <= float(cap)
        assert plan["budget"]["est_run_minutes"] < plan["budget"]["run_deadline_minutes"]


def test_bundle_carries_the_cs1684_files_and_dry_runs_on_its_own(tmp_path):
    ctl = _load(PKG / "gpu/brev_controller.py", "ctl_dp_bundle")
    bundle = ctl.write_bundle(tmp_path / "b.tar.gz", FULL)
    with tarfile.open(bundle) as tar:
        names = set(tar.getnames())
        tar.extractall(tmp_path / "box", filter="data")
    for rel in dp.CS1684_FILES:
        assert f"warranted_revision/cs1684/{rel}" in names
    box = tmp_path / "box" / "warranted_revision"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"} | {
        "PYTHONPATH": str(box / "src")
    }
    for args in (["lock"], ["run", "--config", "configs/_launch_config.json", "--dry-run"]):
        r = subprocess.run(
            [sys.executable, "-m", "warranted_revision.decision_procedure", *args],
            cwd=box,
            env=env,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
    assert "4800" in r.stdout
    code = (box / "gpu/remote_job.sh").read_text()
    assert "exec bash gpu/decision_procedure_job.sh" in code
    assert (
        subprocess.run(["bash", "-n", str(box / "gpu/decision_procedure_job.sh")]).returncode == 0
    )
