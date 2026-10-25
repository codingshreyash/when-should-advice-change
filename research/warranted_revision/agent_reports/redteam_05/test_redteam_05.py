"""Red-team tripwires (Agent 5). Run: python3 -m pytest -q agent_reports/redteam_05 (from
research/warranted_revision). Characterisation tests pass; the xfail(strict) test documents a
property the code claims but does not have."""
from __future__ import annotations

import json
import sys
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import pytest

PKG = Path(__file__).resolve().parents[2]
REPO = PKG.parents[1]
sys.path.insert(0, str(PKG / "src"))

from warranted_revision.backends.base import GenRequest  # noqa: E402
from warranted_revision.backends.hf import HFBackend  # noqa: E402
from warranted_revision.runner import RunConfig, load_cases, shard_cases  # noqa: E402
from warranted_revision.schema import GenParams, Message  # noqa: E402


def test_four_shards_are_label_cells():
    """With 4 round-robin shards, each shard holds exactly one (priority, gold-side) cell,
    because generate.build_case balances priority and gold by index. A pilot stopped after
    shard 1-2 contains only cases whose gold is the family's first option."""
    raw = json.loads((PKG / "configs/pilot_challenge.json").read_text())
    raw["run_id"] = "x"
    gold = {
        json.loads(l)["case_id"]: json.loads(l)
        for l in (PKG / "data/challenge_v1/challenge_gold.jsonl").read_text().splitlines()
    }
    for i in range(1, 5):
        raw["shard"] = f"{i}/4"
        cfg = RunConfig.model_validate(raw)
        cases = shard_cases(cfg, load_cases(cfg))
        sides = {c.option_codes.index(gold[c.case_id]["gold_base_action"]) for c in cases}
        assert len(sides) == 1  # confound: shard == gold side
        assert len({c.case_id[-2:] for c in cases}) == 1  # same index => same priority slot


class _Enc(dict):
    def to(self, _device):
        return self


def _stub_backend(log):
    b = object.__new__(HFBackend)

    class T:
        @staticmethod
        def manual_seed(s):
            log.append(s)

        @staticmethod
        def no_grad():
            return nullcontext()

    class Tok:
        pad_token_id = 0

        def apply_chat_template(self, msgs, **kw):
            return msgs[-1]["content"]

        def __call__(self, prompts, **kw):
            n = len(prompts)
            return _Enc(input_ids=np.ones((n, 3), int), attention_mask=np.ones((n, 3), int))

        def decode(self, ids, **kw):
            return "x"

    class M:
        device = "cpu"

        def generate(self, input_ids, attention_mask, **kw):
            return np.ones((input_ids.shape[0], 5), int)

    b.torch, b.tok, b.model, b.max_batch = T, Tok(), M(), 9
    return b


@pytest.mark.xfail(strict=True, reason="HF backend seeds once per batch with reqs[0].gen.seed")
def test_hf_backend_honours_each_request_seed():
    log: list[int] = []
    b = _stub_backend(log)
    reqs = [
        GenRequest((Message(role="user", content="p"),), GenParams(temperature=0.7, max_new_tokens=4, seed=s))
        for s in (11, 22, 33)
    ]
    b.generate(reqs)
    assert sorted(log) == [11, 22, 33]  # recorded per-call seeds are what was used


def test_ablation_crn_is_deterministic_in_format001():
    """Negative finding: SEED_ALIAS common random numbers work on the GPU. Every decide call
    with identical messages and seed in premise_search and its ablation produced identical
    text, so arm differences arise only where beams/selections diverge."""
    p = REPO / "results/warranted_revision/format-001/predictions.jsonl"
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    by: dict = {}
    for r in rows:
        if r["call_role"].startswith("decide"):
            by.setdefault((r["case_id"], r["followup_id"], r["call_role"]), {})[r["condition"]] = r
    same = diff = 0
    for v in by.values():
        a, b = v.get("premise_search"), v.get("premise_search_noprov")
        if a and b and a["messages_sha256"] == b["messages_sha256"] and a["gen"]["seed"] == b["gen"]["seed"]:
            same += 1
            diff += a["completion"]["text"] != b["completion"]["text"]
    assert same >= 50 and diff == 0
