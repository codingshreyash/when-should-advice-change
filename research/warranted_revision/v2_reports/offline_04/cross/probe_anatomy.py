"""Cross-review (A): run the scaffold probe with the fake backend in a temp dir (all six cells,
plus the stage-1 config as written) and check prompt anatomy against a saved smoke-004 direct
follow-up. Read-only on results/; writes only to the temp dir given as argv[1].

    PYTHONPATH=research/warranted_revision/src python3 -B .../cross/probe_anatomy.py <tmpdir>
"""
import json, sys
from pathlib import Path
from warranted_revision import prompts as P
from warranted_revision.runner import PKG_ROOT
from warranted_revision.scaffold_probe import ProbeConfig, run, LENGTH_CAP, DECISION_TURN, CELLS
from warranted_revision.schema import VisibleCase

tmp = Path(sys.argv[1])
raw = json.loads((PKG_ROOT / "configs/scaffold_probe_stage1.json").read_text())
raw.update(run_id="all-cells", systems=[{"kind": "fake", "name": "stubborn"}],
           cells=["S0", "S1", "S3", "S4", "S5", "S6"], max_calls=None,
           repeat={"cells": ["S3", "S0"], "items": {"away_insist": "pushback", "neutral_other": "reask"}, "rounds": 2},
           sample={"cells": ["S0", "S3"], "items": ["away_insist"], "k": 2})
out = run(ProbeConfig.model_validate(raw), out_root=tmp)
rows = [json.loads(l) for l in (out / "probe_calls.jsonl").open()]
cases = {c.case_id: c for c in (VisibleCase.model_validate_json(l) for l in (PKG_ROOT / raw["inputs"]).read_text().splitlines() if l.strip())}

def first_dec(cell, item, case, order):
    for r in rows:
        if (r["cell"], r["item"], r["case_id"], r["order"]) == (cell, item, case, order) and r["step"] in ("decision", "free"):
            return r
key = (raw["case_ids"][0], "ab")
base = next(r for r in rows if r["step"] == "base" and (r["case_id"], r["order"]) == key)
print("BASE equals runner's P.conversation:", base["messages"] == [m.model_dump() for m in P.conversation(cases[key[0]], base["option_order"], P.DIRECT_FORMAT)])
# S0 vs runner follow-up structure
s0 = first_dec("S0", "away_insist", *key)
runner = [m.model_dump() for m in P.conversation(cases[key[0]], s0["option_order"], P.DIRECT_FORMAT,
          followup_text=s0["messages"][3]["content"].split("\n\nOptions:\n")[0], base_reply=base["text"], base_fmt=P.DIRECT_FORMAT)]
print("S0 follow-up == runner conversation() for same text/base:", s0["messages"] == runner)
# saved smoke-004 direct follow-up: structural template
sm = next(json.loads(l) for l in open(PKG_ROOT.parents[1] / "results/warranted_revision/smoke-004/predictions.jsonl") if '"condition":"direct"' in l.replace(" ", "") and '"turn":"followup"' in l.replace(" ", ""))
def skel(msgs):
    out = []
    for m in msgs:
        c = m["content"]
        if m["role"] == "user":
            head, _, tail = c.partition("\n\nOptions:\n")
            opts, _, fmt = tail.partition("\n\n")
            out.append((m["role"], bool(tail), len(opts.splitlines()), fmt))
        else:
            out.append((m["role"],))
    return out
print("S0 skeleton == smoke-004 skeleton (roles, options present, #options, format text):", skel(s0["messages"]) == skel(sm["messages"]))
print("system prompt identical to smoke-004:", s0["messages"][0] == sm["messages"][0])
# per-cell last user message anatomy
print("\nper-cell first-step user message (item away_insist):")
for cell in CELLS:
    r = first_dec(cell, "away_insist", *key)
    u = r["messages"][-1]["content"]
    hist_same = r["messages"][:3] == s0["messages"][:3]
    print(f" {cell} step={r['step']:8s} options={'Options:' in u} DECISION_RULE={P.DECISION_RULE in u} "
          f"len_cap={u.rstrip().endswith(LENGTH_CAP) or LENGTH_CAP in u} history[0:3]==S0:{hist_same} ends={u[-60:]!r}")
# decision turns of separate cells
print("\nseparate-cell decision turn and history:")
for cell in ("S3", "S4", "S5", "S6"):
    r = next(x for x in rows if (x["cell"], x["item"], x["case_id"], x["order"], x["step"]) == (cell, "away_insist", *key, "decision"))
    print(f" {cell}: n_msgs={len(r['messages'])} last_user={r['messages'][-1]['content'][:70]!r}... prior DECISION line in base reply kept:",
          r["messages"][2]["content"] == base["text"])
# diffs between cells other than the factor: compare follow-up message after removing text
print("\nfree-reply max_new_tokens:", raw.get("max_new_tokens_free", 200))
steps = {}
for r in rows:
    steps[(r["cell"], r["step"])] = steps.get((r["cell"], r["step"]), 0) + 1
print("steps per cell:", dict(sorted((k, v) for k, v in steps.items() if k[0])))
# repeated rounds: what does round-1 user message carry in S0 vs S3?
for cell in ("S0", "S3"):
    r = next(x for x in rows if x["cell"] == cell and x["item"] == "away_insist" and x["step"].startswith("r1_") and (x["case_id"], x["order"]) == key)
    print(f" round1 {cell} step={r['step']} last user={r['messages'][-1]['content'][:90]!r} n_msgs={len(r['messages'])}")
# sample request equals final greedy request?
for cell in ("S0", "S3"):
    smp = next(x for x in rows if x["cell"] == cell and x["step"] == "sample" and (x["case_id"], x["order"]) == key)
    fin = [x for x in rows if x["cell"] == cell and x["item"] == smp["item"] and (x["case_id"], x["order"]) == key and x["step"].endswith("decision")]
    print(f" sample {cell}: sample prompt == which decision step?", [x["step"] for x in fin if x["messages"] == smp["messages"]], "| all decision steps:", [x["step"] for x in fin])
print("away option defined when base invalid? count base_choice None:", sum(1 for r in rows if r["step"] == "base" and r["base_choice"] is None))
# S5 free prompt vs S0 decision prompt; S6 free vs S1 decision (same bytes => free batch-invariance check)
idx = {(r["cell"], r["item"], r["case_id"], r["order"], r["step"]): r for r in rows}
for a, b in (("S5", "S0"), ("S6", "S1")):
    eq = sum(idx[(a, it, c, o, "free")]["messages"] == idx[(b, it, c, o, "decision")]["messages"]
             for (cell, it, c, o, st) in idx if cell == a and st == "free")
    n = sum(1 for k in idx if k[0] == a and k[4] == "free")
    print(f"{a} free prompt byte-identical to {b} decision prompt: {eq}/{n}")
