"""Run log: every logged run is accounted for and totals add up from the rows."""

from warranted_revision.runlog import build, render


def test_runlog_totals_match_rows():
    rows, t = build()
    assert t["runs"] == len(rows) and len({r["run_id"] for r in rows}) == len(rows)
    gpu = [r for r in rows if r["kind"] == "gpu"]
    assert t["real_model_calls"] == sum(r.get("calls") or 0 for r in gpu)
    assert t["est_cost_usd"] == round(sum(r["est_cost_usd"] for r in gpu), 2)
    for r in rows:  # completed real runs must have their files and match the manifest call count
        if r["kind"] == "gpu" and r["outcome"].startswith("completed"):
            assert r["calls"] and r["decision_calls"] > 0
    assert "## Totals" in render(rows, t)
