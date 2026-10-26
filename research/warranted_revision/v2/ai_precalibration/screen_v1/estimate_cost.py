"""Exact call counts and token/cost estimates for the goal screen, without any model call.

Replays the run's exact call sequence with a synthetic backend whose replies are padded to a
fixed length. Input tokens are estimated at 1 token per 3 characters + 10% (an over-estimate
for English text); reply length drives how much history later calls carry.

    python v2/ai_precalibration/screen_v1/estimate_cost.py configs/goal_screen_sonnet.json
"""

import json
import sys
import tempfile
from pathlib import Path

from warranted_revision import goal_screen as gs


class Padded(gs.FakeScreenBackend):
    def __init__(self, out_tokens: int | None):
        super().__init__("stubborn")
        self.out_tokens = out_tokens  # None: every reply uses its full max_tokens

    def complete(self, system, messages, max_tokens, sample, seed):
        rep = super().complete(system, messages, max_tokens, sample, seed)
        n = max_tokens if self.out_tokens is None else min(self.out_tokens, max_tokens)
        rep.text = "x " * (3 * n // 2 - 30) + "\n" + rep.text  # ~3 chars per token
        rep.output_tokens = n
        return rep


def estimate(cfg_path: Path) -> dict:
    cfg = gs.load_config(cfg_path)
    items, controls = gs.load_screen_items(gs.PKG_ROOT / cfg.items, gs.PKG_ROOT / cfg.manifest)
    out = {
        "config": str(cfg_path),
        "calls": gs.plan_calls(cfg, items, controls),
        "preflight_calls": gs.preflight_plan(cfg, items, controls),
    }
    budget = cfg.budget or gs.BudgetCfg(max_usd=1e9, usd_per_m_input=0, usd_per_m_output=0)
    big = cfg.model_copy(update={"budget": budget.model_copy(update={"max_usd": 1e9})})
    for name, n in (("typical_150_out", 150), ("worst_all_max_tokens", None)):
        with tempfile.TemporaryDirectory() as d:
            for pre in (False, True):
                r = gs.run(big, preflight=pre, backend=Padded(n), out_root=Path(d))
                rows = [json.loads(x) for x in (r / "calls.jsonl").read_text().splitlines()]
                key = name + ("_preflight" if pre else "")
                out[key] = {
                    "calls": len(rows),
                    "input_tokens": sum(x["input_tokens"] for x in rows),
                    "output_tokens": sum(x["output_tokens"] for x in rows),
                    "usd": round(sum(x["cost_usd"] for x in rows), 2),
                }
    return out


if __name__ == "__main__":
    print(json.dumps(estimate(Path(sys.argv[1])), indent=1))
