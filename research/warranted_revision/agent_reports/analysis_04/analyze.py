"""Agent 4 forensic analysis of smoke-003, smoke-004, format-001 (read-only on results/).

Run from research/warranted_revision:
    python3 agent_reports/analysis_04/analyze.py > <scratch>/analysis.txt

Everything labelled "ALT" is an alternative (non-protocol) metric computed for diagnosis only.
Protocol metrics are reproduced via warranted_revision.evaluate on scratch copies (see
commands.sh); this script never writes into results/.
"""

from __future__ import annotations

import gzip
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from warranted_revision.schema import (  # noqa: E402
    UNWARRANTED_UPDATE_CLASSES,
    WARRANTED_UPDATE_CLASSES,
    ContrastClass,
)
from warranted_revision.trace_audit import TRUE_READING  # noqa: E402

RES = Path("../../results/warranted_revision")
RUNS = ["smoke-003", "smoke-004", "format-001"]
AX_I = {c.value for c in WARRANTED_UPDATE_CLASSES}
AX_II = {c.value for c in UNWARRANTED_UPDATE_CLASSES}
TRUE = {k.value: v for k, v in TRUE_READING.items()}


def rows(run, name):
    p = RES / run / f"{name}.jsonl"
    fh = open(p) if p.exists() else gzip.open(str(p) + ".gz", "rt")
    with fh:
        for ln in fh:
            if ln.strip():
                yield json.loads(ln)


gold = {}
for ln in open("data/v0/dev_gold.jsonl"):
    g = json.loads(ln)
    gold[g["case_id"]] = g
FU = {f["followup_id"]: (g["case_id"], f) for g in gold.values() for f in g["followups"]}


def pct(a, b):
    return f"{a}/{b} ({a / b:.0%})" if b else "n/a"


def vote(ch):
    if not ch:
        return None
    c = Counter(ch)
    top = max(c.values())
    return next(x for x in ch if c[x] == top)


for run in RUNS:
    print(f"\n{'=' * 30} {run} {'=' * 30}")
    decs = list(rows(run, "decisions"))
    traces = list(rows(run, "search_traces"))
    conds = sorted({d["condition"] for d in decs})
    base = {(d["condition"], d["case_id"]): d for d in decs if d["turn"] == "base"}

    # ---- 1. Base-turn answers per case and arm (the gate for every joint metric)
    print("\n## Base answers (case: gold | arm answers; * = wrong); option order")
    for cid in sorted({d["case_id"] for d in decs}):
        g = gold[cid]
        parts = []
        for c in conds:
            b = base.get((c, cid))
            if b:
                ok = b["status"] == "valid" and b["choice"] == g["gold_base_action"]
                parts.append(f"{c}={b['choice']}{'' if ok else '*'}")
        order = base[(conds[0], cid)]["option_order"]
        gpos = order.index(g["gold_base_action"])
        print(f"- {cid} (margin {g['base_margin']:.2f}) gold={g['gold_base_action']} gold_pos={gpos} order={order}: " + ", ".join(parts))

    # ---- 2. Per-arm decomposition: follow-up-only accuracy (ALT) vs joint (protocol)
    print("\n## Per-arm decomposition (follow-up turns). ALT = not a protocol metric")
    print("| arm | valid fu | ALT fu-correct axis i | ALT fu-correct axis ii | ALT fu-correct all 8 | joint axis i | joint axis ii | ALT axis i on base-correct cases | ALT axis ii on base-correct cases | changed from base | mean prompt tok/turn | mean compl tok/turn |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in conds:
        fus = [d for d in decs if d["condition"] == c and d["turn"] == "followup"]
        acc = defaultdict(lambda: [0, 0])
        for d in fus:
            cid, f = FU[d["followup_id"]]
            b = base[(c, cid)]
            bok = b["status"] == "valid" and b["choice"] == gold[cid]["gold_base_action"]
            ok = d["status"] == "valid" and d["choice"] == f["gold_action"]
            cls = f["contrast_class"]
            for key, cond in (
                ("i", cls in AX_I), ("ii", cls in AX_II), ("all", True),
                ("ji", cls in AX_I), ("jii", cls in AX_II),
                ("bi", cls in AX_I and bok), ("bii", cls in AX_II and bok),
                ("chg", True),
            ):
                if not cond:
                    continue
                acc[key][1] += 1
                if key in ("ji", "jii"):
                    acc[key][0] += ok and bok
                elif key == "chg":
                    acc[key][0] += d["choice"] != b["choice"]
                else:
                    acc[key][0] += ok
        valid = sum(d["status"] == "valid" for d in fus)
        allc = [d for d in decs if d["condition"] == c]
        pt = sum(d["prompt_tokens"] for d in allc) / len(allc)
        ct = sum(d["completion_tokens"] for d in allc) / len(allc)
        print(f"| {c} | {pct(valid, len(fus))} | " + " | ".join(pct(*acc[k]) for k in ("i", "ii", "all", "ji", "jii", "bi", "bii", "chg")) + f" | {pt:.0f} | {ct:.0f} |")

    # ---- 3. Selector comparison on saved candidates (base + follow-up), per arm
    print("\n## Selectors on the same candidates: correct / turns (base turns; follow-up turns)")
    print("| arm | turn | turns | first sample | first valid | vote | selected | oracle any | selected!=vote (sel right/vote right) | unanimous valid |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    sel_rows = defaultdict(Counter)
    for tr in traces:
        cid = tr["case_id"]
        if tr["followup_id"] is None:
            want, turn = gold[cid]["gold_base_action"], "base"
        else:
            want, turn = FU[tr["followup_id"]][1]["gold_action"], "followup"
        leaves = sorted((n for n in tr["nodes"] if n["hypothesis"] is None), key=lambda n: n["call_index"])
        valid = [n for n in leaves if n["status"] == "valid" and n["choice"]]
        chosen = next((n for n in tr["nodes"] if n["node_id"] == tr["selected_node_id"]), None)
        v = vote([n["choice"] for n in valid])
        k = sel_rows[(tr["condition"], turn)]
        k["n"] += 1
        k["first"] += bool(leaves and leaves[0]["status"] == "valid" and leaves[0]["choice"] == want)
        k["fv"] += bool(valid and valid[0]["choice"] == want)
        k["vote"] += v == want
        k["sel"] += bool(chosen and chosen["status"] == "valid" and chosen["choice"] == want)
        k["any"] += any(n["choice"] == want for n in valid)
        k["unan"] += len({n["choice"] for n in valid}) == 1 and len(valid) == len(leaves)
        if chosen and chosen["choice"] != v:
            k["diff"] += 1
            k["diff_sel"] += chosen["choice"] == want
            k["diff_vote"] += v == want
    for (c, turn), k in sorted(sel_rows.items()):
        n = k["n"]
        print(f"| {c} | {turn} | {n} | {pct(k['first'], n)} | {pct(k['fv'], n)} | {pct(k['vote'], n)} | {pct(k['sel'], n)} | {pct(k['any'], n)} | {k['diff']} ({k['diff_sel']}/{k['diff_vote']}) | {pct(k['unan'], n)} |")

    # ---- 4. Interpretations in model-written ledgers vs intended reading (follow-up turns)
    print("\n## Free-choice interpretations (structured / best-of-N samples / search decide calls) vs TRUE_READING")
    interp = defaultdict(Counter)
    confusion = defaultdict(Counter)
    hyp = defaultdict(Counter)
    for r in rows(run, "predictions"):
        if r["turn"] != "followup":
            continue
        cid, f = FU[r["followup_id"]]
        cls = f["contrast_class"]
        truth = TRUE[cls]
        led = r["parsed"].get("ledger")
        role = r["call_role"]
        group = "hypothesis" if role.startswith("hypothesis") else (
            "decide" if role.startswith("decide") else r["condition"])
        if group == "hypothesis":
            h = role.split(":", 1)[1]
            sup = r["parsed"].get("hypothesis_supported")
            key = "true" if h == truth else "wrong"
            hyp[(r["condition"], key)]["n"] += 1
            hyp[(r["condition"], key)]["yes"] += sup is True
            hyp[(r["condition"], key)]["parsed"] += led is not None
            continue
        arm = f"{r['condition']}/{group}"
        interp[(arm, cls)]["n"] += 1
        if led is None:
            interp[(arm, cls)]["noledger"] += 1
            continue
        interp[(arm, cls)]["match"] += led["interpretation"] == truth
        confusion[(arm, cls)][led["interpretation"]] += 1
    arms = sorted({a for a, _ in interp})
    classes = [c.value for c in ContrastClass if any((a, c.value) in interp for a in arms)]
    print("| arm | " + " | ".join(classes) + " | total (match / parsed) |")
    print("|---|" + "---|" * (len(classes) + 1))
    for a in arms:
        cells, tm, tp = [], 0, 0
        for cl in classes:
            k = interp[(a, cl)]
            p = k["n"] - k["noledger"]
            tm += k["match"]
            tp += p
            cells.append(f"{k['match']}/{p}")
        print(f"| {a} | " + " | ".join(cells) + f" | {pct(tm, tp)} |")
    print("\nMost common reading per (arm, class) [truth in brackets]:")
    for a in arms:
        for cl in classes:
            cf = confusion[(a, cl)]
            if cf:
                print(f"- {a} {cl} [{TRUE[cl]}]: " + ", ".join(f"{k} {v}" for k, v in cf.most_common(3)))
    print("\nSearch hypothesis nodes: SUPPORTED=yes rate by whether the assigned reading is the intended one")
    for (c, key), k in sorted(hyp.items()):
        print(f"- {c} {key} reading: {pct(k['yes'], k['n'])} yes (ledger parsed {k['parsed']}/{k['n']})")

    # ---- 5. Position of the chosen option (answer-position audit), all follow-up final decisions
    print("\n## Answer position (final decisions, all turns): chosen-option index in option_order vs gold index")
    for c in conds:
        cp, gp, okp = Counter(), Counter(), Counter()
        for d in decs:
            if d["condition"] != c or d["status"] != "valid":
                continue
            if d["turn"] == "base":
                want = gold[d["case_id"]]["gold_base_action"]
            else:
                want = FU[d["followup_id"]][1]["gold_action"]
            cp[d["option_order"].index(d["choice"])] += 1
            gp[d["option_order"].index(want)] += 1
        print(f"- {c}: chosen pos {dict(sorted(cp.items()))}; gold pos {dict(sorted(gp.items()))}")

    # ---- 6. Paired turn-level agreement between arms on follow-up correctness
    print("\n## Paired follow-up correctness between arms (a right & b wrong / a wrong & b right), 40-turn runs")
    cor = {}
    for d in decs:
        if d["turn"] != "followup":
            continue
        f = FU[d["followup_id"]][1]
        cor[(d["condition"], d["followup_id"])] = d["status"] == "valid" and d["choice"] == f["gold_action"]
    for a, b in itertools.combinations(conds, 2):
        ids = [fid for (c, fid) in cor if c == a and (b, fid) in cor]
        ab = sum(cor[(a, i)] and not cor[(b, i)] for i in ids)
        ba = sum(cor[(b, i)] and not cor[(a, i)] for i in ids)
        print(f"- {a} vs {b}: {ab} / {ba} discordant of {len(ids)}")

    # ---- 7. format-001 ablation: are the depth-1 calls identical across arms?
    if run == "format-001":
        print("\n## Ablation pairing check (premise_search vs premise_search_noprov)")
        preds = defaultdict(dict)
        for r in rows(run, "predictions"):
            if r["condition"].startswith("premise_search"):
                preds[(r["case_id"], r["followup_id"], r["call_index"])][r["condition"]] = (r["call_role"], r["completion"]["text"])
        same_d1 = same_d2 = n_d1 = n_d2 = 0
        for key, v in preds.items():
            if len(v) != 2:
                continue
            (ra, ta), (rb, tb) = v["premise_search"], v["premise_search_noprov"]
            if ra.startswith("hypothesis"):
                n_d1 += 1
                same_d1 += ta == tb
            else:
                n_d2 += 1
                same_d2 += ta == tb and ra == rb
        print(f"- depth-1 hypothesis calls identical text: {same_d1}/{n_d1}; depth-2 decide calls identical role+text: {same_d2}/{n_d2}")
        trs = {(t["condition"], t["case_id"], t["followup_id"]): t for t in traces}
        nb = ns = 0
        for (c, cid, fid), t in trs.items():
            if c != "premise_search":
                continue
            u = trs[("premise_search_noprov", cid, fid)]
            ka = {n["hypothesis"] for n in t["nodes"] if n["hypothesis"] and n["kept"]}
            kb = {n["hypothesis"] for n in u["nodes"] if n["hypothesis"] and n["kept"]}
            nb += ka != kb
            ca = next(n["choice"] for n in t["nodes"] if n["node_id"] == t["selected_node_id"])
            cb = next(n["choice"] for n in u["nodes"] if n["node_id"] == u["selected_node_id"])
            if ca != cb:
                ns += 1
                want = gold[cid]["gold_base_action"] if fid is None else FU[fid][1]["gold_action"]
                print(f"  final differs: {cid} {fid} {FU[fid][1]['contrast_class'] if fid else 'base'}: full={ca} formatonly={cb} gold={want}; beams full={sorted(ka)} fo={sorted(kb)}")
        print(f"- turns with different beam: {nb}/{sum(c == 'premise_search' for c, _, _ in trs)}; different final answer: {ns}")
