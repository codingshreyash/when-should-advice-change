"""Refusal accounting: refusals, invalid and missing outputs stay visible and count as failures."""

import json

from warranted_revision.backends.fake import FakeBackend, VisibleRandomPolicy
from warranted_revision.evaluate import evaluate_run
from warranted_revision.runner import RunConfig, run
from warranted_revision.schema import Completion

from .conftest import DEV_GOLD, SUBSET, make_run, read_jsonl


class BrokenBackend(FakeBackend):
    """Returns backend errors for every call."""

    def generate(self, requests):
        return [
            Completion(
                text="",
                prompt_tokens=0,
                completion_tokens=0,
                latency_s=0,
                finish_reason="error",
                error="simulated failure",
            )
            for _ in requests
        ]


def test_refusals_counted_and_scored_as_failures(tmp_path):
    systems = [{"kind": "fake", "name": "visible_random", "params": {"refusal_rate": 1.0}}]
    out = make_run(tmp_path, "refuse", systems, conditions=["direct", "best_of_n"])
    m = evaluate_run(out, DEV_GOLD, n_draws=50)
    for a in (a for a in m["arms"] if not a["derived"]):
        sc = a["status_counts"]
        assert sc["refusal"] == sc["turns"] and sc["valid"] == 0
        assert sc["need_more_information_total"] == 0  # refusal is not need_more_information
        assert a["axis_warranted_update"]["value"] == 0.0
        assert a["axis_unwarranted_stability"]["value"] == 0.0
        assert a["abstention_missing_information"]["value"] == 0.0
    rows = read_jsonl(out / "predictions.jsonl")
    assert all(r["parsed"]["status"] == "refusal" and r["completion"]["text"] for r in rows)


def test_backend_errors_are_missing_not_dropped(tmp_path):
    broken = BrokenBackend(VisibleRandomPolicy())
    ids = tmp_path / "ids.json"
    ids.write_text(json.dumps(SUBSET[:1]))
    cfg = RunConfig(
        run_id="broken",
        label="t",
        split="dev",
        inputs="data/v0/dev_inputs.jsonl",
        case_ids_file=str(ids),
        conditions=["direct", "premise_search"],
        systems=[{"kind": "fake", "name": "visible_random"}],
    )
    out = run(cfg, out_root=tmp_path, backends={"visible_random": broken})
    decs = read_jsonl(out / "decisions.jsonl")
    assert len(decs) == 2 * 9 and all(d["status"] == "missing" for d in decs)
    m = evaluate_run(out, DEV_GOLD, n_draws=20)
    assert all(a["status_counts"]["missing"] == 9 for a in m["arms"] if not a["derived"])
