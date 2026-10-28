"""Provenance checks in ``scripts/data/labeling.py score``, on synthetic sheets in a temp dir.

The sheets here are filled by rule (drafts, or the first option that is not the draft); they
exercise the refusals only and are not labels of any kind.
"""

import csv
import importlib.util
import json

import pytest

from warranted_revision.decision_procedure_analysis import load_labels
from warranted_revision.runner import PKG_ROOT

REPO = PKG_ROOT.parents[1]
SCEN = REPO / "data" / "scenarios" / "career_pilot.jsonl"


def _labeling():
    path = REPO / "scripts/data/labeling.py"
    if not path.exists() or not SCEN.exists():  # the GPU bundle carries neither
        pytest.skip(f"{path} not in this checkout")
    spec = importlib.util.spec_from_file_location("labeling", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # make/score write under ./data/labeling
    mod = _labeling()
    mod.make(str(SCEN))
    return mod


def fill(tmp_path, name, rule, extra_col=None, blank=()):
    """Copy the handed-out sheet and fill `your_label` with rule(draft, options)."""
    S = {json.loads(x)["id"]: json.loads(x) for x in SCEN.read_text().splitlines() if x}
    key = {
        r["row_id"]: r["item_key"].split("::")
        for r in csv.DictReader(open(tmp_path / "data/labeling/career_pilot_key.csv"))
    }
    rows = list(csv.DictReader(open(tmp_path / "data/labeling/career_pilot_sheet.csv")))
    for r in rows:
        sid, v = key[r["row_id"]]
        r["your_label"] = "" if r["row_id"] in blank else rule(S[sid]["expected"][v], S[sid]["options"])
        r["why"] = "test"
        if extra_col:
            r[extra_col] = v
    p = tmp_path / name
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return p


def draft(d, opts):
    return d


def not_draft(d, opts):
    return next(o for o in opts if o != d)


def test_score_refuses_same_or_identical_sheets_and_missing_ids(lab, tmp_path):
    a = fill(tmp_path, "a.csv", not_draft)
    b = fill(tmp_path, "b.csv", not_draft)
    with pytest.raises(SystemExit, match="same file"):
        lab.score(str(SCEN), str(a), str(a), "p1", "p2")
    with pytest.raises(SystemExit, match="identical contents"):
        lab.score(str(SCEN), str(a), str(b), "p1", "p2")
    for ids in ((None, "p2"), ("p1", " "), ("p1", "p1")):
        with pytest.raises(SystemExit, match="labeler ids"):
            lab.score(str(SCEN), str(a), str(b), *ids)
    with pytest.raises(SystemExit):  # the CLI requires both ids
        lab.main(["score", str(SCEN), str(a), str(b)])
    assert not (tmp_path / "data/labeling/career_pilot_blind.jsonl").exists()


def test_score_refuses_sheets_equal_to_the_drafts(lab, tmp_path):
    a = fill(tmp_path, "a.csv", draft)
    b = fill(tmp_path, "b.csv", not_draft)
    with pytest.raises(SystemExit, match="draft labels on every row"):
        lab.score(str(SCEN), str(a), str(b), "p1", "p2")
    assert not (tmp_path / "data/labeling/career_pilot_blind.jsonl").exists()


def test_score_refuses_reference_columns_and_incomplete_sheets(lab, tmp_path):
    b = fill(tmp_path, "b.csv", not_draft)
    a = fill(tmp_path, "a.csv", not_draft, extra_col="reference_variant")
    with pytest.raises(SystemExit, match="reference_variant"):
        lab.score(str(SCEN), str(a), str(b), "p1", "p2")
    a = fill(tmp_path, "a.csv", not_draft, blank=("r005",))
    with pytest.raises(SystemExit, match="row problem"):
        lab.score(str(SCEN), str(a), str(b), "p1", "p2")
    assert not (tmp_path / "data/labeling/career_pilot_blind.jsonl").exists()


def test_score_writes_provenance_the_analysis_accepts(lab, tmp_path):
    a = fill(tmp_path, "a.csv", not_draft)
    b = fill(tmp_path, "b.csv", lambda d, opts: [o for o in opts if o != d][-1])
    lab.score(str(SCEN), str(a), str(b), "p1", "p2")
    out = tmp_path / "data/labeling/career_pilot_blind.jsonl"
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    prov = rows[0]["label_provenance"]
    assert all(r["label_source"] == "blind" for r in rows)
    assert prov["labelers"] == {"A": "p1", "B": "p2"}
    assert prov["sheet_sha256"] == {"A": lab.sha256(a), "B": lab.sha256(b)}
    assert prov["scenarios_sha256"] == lab.sha256(SCEN)
    assert len(load_labels([out])) == len(rows)
