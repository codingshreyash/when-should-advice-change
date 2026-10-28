"""Leakage: inference and candidate selection cannot see gold labels or contrast classes."""

import ast
import inspect
import json
from pathlib import Path

from warranted_revision import scoring
from warranted_revision.runner import PKG_ROOT
from warranted_revision.schema import ContrastClass, GoldCase

from .conftest import ALL_CONDITIONS, DEV_GOLD, make_run, read_jsonl

SRC = PKG_ROOT / "src" / "warranted_revision"
INFERENCE_MODULES = [
    "prompts.py",
    "parsing.py",
    "scoring.py",
    "conditions.py",
    "backends/base.py",
    "backends/fake.py",
    "backends/hf.py",
]
FORBIDDEN_IMPORTS = {"evaluate", "generate", "families", "controls", "stats"}
FORBIDDEN_NAMES = {
    "GoldCase",
    "GoldFollowUp",
    "Provenance",
    "ContrastClass",
    "gold_action",
    "gold_base_action",
    "contrast_class",
    "FAMILIES",
}


def _tamper(gold_path: Path, out: Path) -> Path:
    """Flip every actionable gold label and rotate contrast classes; inputs stay identical."""
    rows = []
    for ln in gold_path.read_text().splitlines():
        g = GoldCase.model_validate_json(ln)
        d = json.loads(ln)
        codes = sorted(
            {g.gold_base_action} | {f.gold_action for f in g.followups} - {"need_more_information"}
        )
        flip = {a: b for a, b in zip(codes, codes[::-1], strict=True)}
        d["gold_base_action"] = flip.get(d["gold_base_action"], d["gold_base_action"])
        classes = [c.value for c in ContrastClass]
        for f in d["followups"]:
            f["gold_action"] = flip.get(f["gold_action"], "need_more_information")
            f["contrast_class"] = classes[(classes.index(f["contrast_class"]) + 1) % len(classes)]
        rows.append(json.dumps(d))
    out.write_text("\n".join(rows) + "\n")
    return out


def _strip(rows):
    return [{k: v for k, v in r.items() if k != "run_id"} for r in rows]


def test_altering_hidden_answer_key_does_not_change_inference(tmp_path):
    tampered = _tamper(DEV_GOLD, tmp_path / "tampered_gold.jsonl")
    systems = [{"kind": "fake", "name": "visible_random"}]
    a = make_run(tmp_path, "orig", systems, gold=DEV_GOLD)
    b = make_run(tmp_path, "tampered", systems, gold=tampered)
    for name in ("predictions.jsonl", "decisions.jsonl", "search_traces.jsonl"):
        assert _strip(read_jsonl(a / name)) == _strip(read_jsonl(b / name)), name
    # Sanity: the tampering is real, so a privileged oracle *does* change.
    oa = make_run(
        tmp_path,
        "oracle_orig",
        [{"kind": "control", "name": "oracle"}],
        conditions=["direct"],
        gold=DEV_GOLD,
    )
    ob = make_run(
        tmp_path,
        "oracle_tampered",
        [{"kind": "control", "name": "oracle"}],
        conditions=["direct"],
        gold=tampered,
    )
    assert [r["choice"] for r in read_jsonl(oa / "decisions.jsonl")] != [
        r["choice"] for r in read_jsonl(ob / "decisions.jsonl")
    ]


def test_inference_modules_do_not_import_or_name_gold():
    for rel in INFERENCE_MODULES:
        tree = ast.parse((SRC / rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mods = (node.module or "").split(".")
                assert not FORBIDDEN_IMPORTS & set(mods), f"{rel} imports {node.module}"
                names = {a.name for a in node.names}
                assert not FORBIDDEN_NAMES & names, f"{rel} imports {names & FORBIDDEN_NAMES}"
            if isinstance(node, ast.Import):
                assert not any(set(a.name.split(".")) & FORBIDDEN_IMPORTS for a in node.names)
            if isinstance(node, ast.Name | ast.Attribute):
                name = node.id if isinstance(node, ast.Name) else node.attr
                assert name not in FORBIDDEN_NAMES, f"{rel} references {name}"


def test_scorer_signature_is_label_free():
    for fn in (scoring.score_candidate, scoring.score_hypothesis):
        params = set(inspect.signature(fn).parameters)
        assert params <= {"parsed", "ctx", "hypothesis"}
    fields = set(scoring.ScoringContext.__dataclass_fields__)
    assert fields == {"user_texts", "latest_text", "options", "previous_choice"}


def test_prompts_carry_no_ids_or_class_names(tmp_path):
    run = make_run(
        tmp_path,
        "msgs",
        [{"kind": "fake", "name": "visible_random"}],
        conditions=ALL_CONDITIONS,
        gold=None,
    )
    classes = [c.value for c in ContrastClass]
    for row in read_jsonl(run / "predictions.jsonl"):
        text = "\n".join(m["content"] for m in row["messages"])
        assert "fu_" not in text and "gold" not in text.lower()
        assert row["case_id"] not in text
        assert not any(c in text for c in classes)


def test_runner_refuses_gold_as_inputs_and_holdout(tmp_path):
    import pytest

    from warranted_revision.runner import RunConfig, load_cases

    with pytest.raises(SystemExit):
        load_cases(
            RunConfig(
                run_id="x",
                label="x",
                split="dev",
                inputs="data/v0/dev_gold.jsonl",
                conditions=["direct"],
                systems=[{"kind": "fake", "name": "visible_random"}],
            )
        )
    with pytest.raises(SystemExit):
        load_cases(
            RunConfig(
                run_id="x",
                label="x",
                split="holdout",
                inputs="data/v0/holdout_inputs.jsonl",
                conditions=["direct"],
                systems=[{"kind": "fake", "name": "visible_random"}],
            )
        )
