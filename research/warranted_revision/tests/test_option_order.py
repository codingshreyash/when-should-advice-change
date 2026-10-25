"""Option order: identical within case and replicate (all turns, all conditions), counterbalanced
across replicates."""

from collections import defaultdict

from warranted_revision import prompts
from warranted_revision.schema import VisibleCase

from .conftest import DEV_INPUTS, read_jsonl


def test_order_paired_within_replicate(control_run):
    orders = defaultdict(set)
    for r in read_jsonl(control_run / "decisions.jsonl"):
        orders[(r["case_id"], r["replicate"])].add(tuple(r["option_order"]))
    assert orders and all(len(v) == 1 for v in orders.values())
    # The rendered option block in every call matches the recorded order.
    for r in read_jsonl(control_run / "predictions.jsonl")[:400]:
        last_user = [m for m in r["messages"] if m["role"] == "user"][-1]["content"]
        shown = [
            ln[2:].split(":")[0]
            for ln in last_user.split("Options:\n")[1].split("\n\n")[0].splitlines()
        ]
        assert shown == r["option_order"]


def test_order_counterbalanced_across_replicates():
    cases = [VisibleCase.model_validate_json(ln) for ln in DEV_INPUTS.read_text().splitlines()]
    for c in cases:
        n = len(c.options)
        orders = [prompts.option_order(c, r, 1684) for r in range(n)]
        for pos in range(n):
            assert sorted(o[pos] for o in orders) == sorted(c.option_codes)
        assert prompts.option_order(c, 0, 1684) == prompts.option_order(c, n, 1684)


def test_rotation_across_cases_balances_positions_and_survives_sharding(tmp_path):
    from collections import Counter

    from .conftest import make_run

    ids = [f"dev-{f}-0{i}" for f in ("refinance", "car", "freelance") for i in range(3)]
    full = make_run(
        tmp_path,
        "rot",
        [{"kind": "fake", "name": "first_option"}],
        conditions=["direct"],
        case_ids=ids,
        rotate_order_across_cases=True,
    )
    s2 = make_run(
        tmp_path,
        "rot-s2",
        [{"kind": "fake", "name": "first_option"}],
        conditions=["direct"],
        case_ids=ids,
        rotate_order_across_cases=True,
        shard="2/3",
    )
    orders = {r["case_id"]: r["option_order"] for r in read_jsonl(full / "decisions.jsonl")}
    first_pos = Counter(o[0] == "need_more_information" for o in orders.values())
    assert first_pos[True] == 3  # nmi first in exactly a third of the 9 cases
    for r in read_jsonl(s2 / "decisions.jsonl"):
        assert r["option_order"] == orders[r["case_id"]]
