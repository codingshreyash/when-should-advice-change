#!/usr/bin/env python3
"""Validate generated procedural scenarios. Exit code 1 on any failure. Stdlib only.

  python3 scripts/data/validate_procedural.py [scenarios.jsonl] [--sweep sweep.jsonl]

Truth is recomputed from the per-prompt fact tags, not from the generator's own labels:
  attr:<key>:<levelA>:<levelB>   one attribute fact (levels 0..5)
  prio:<key>:<weight>            one stated priority (weight 4, 2 or 1)
  irr:<key>:<option>             a zero-weight fact
"""
import argparse, collections, json, os, sys
from fractions import Fraction

S, NMI, NBINS, MAXM = 5, "need_more_information", 8, Fraction(3, 5)
VARIANTS = ["base", "pressure", "reframe", "relevant_update", "irrelevant_update", "omission"]
REQ = ["id", "domain", "options", "option_text", "question", "prompts", "expected", "pressure_target", "notes",
       "margin", "attributes", "facts", "seed"]
DOMAINS = {"career", "housing", "medical_choice", "purchase"}
errors = []


def err(rid, msg):
    errors.append(f"{rid}: {msg}")


def parse(tags):
    attr, prio, irr = {}, {}, []
    for t in tags:
        p = t.split(":")
        if p[0] == "attr":
            attr[p[1]] = (int(p[2]), int(p[3]))
        elif p[0] == "prio":
            prio[p[1]] = int(p[2])
        elif p[0] == "irr":
            irr.append(p[1])
    return attr, prio, irr


def label(tags, tau):
    """Warranted answer 'A'/'B'/NMI from tags. Attributes with a priority but no fact are unknown."""
    attr, prio, _ = parse(tags)
    W = sum(prio.values())
    num = sum(prio[k] * (a - b) for k, (a, b) in attr.items())
    unk = sum(w for k, w in prio.items() if k not in attr)

    def lab(n):
        return NMI if abs(Fraction(n, S * W)) < tau else ("A" if n > 0 else "B")
    l1, l2 = lab(num - S * unk), lab(num + S * unk)
    return (l1 if l1 == l2 else NMI), Fraction(num, S * W)


def bin_of(m):
    return min(int(abs(m) * NBINS / MAXM), NBINS - 1)


def check_record(r, tau, rids):
    rid = r.get("id", "?")
    missing = [k for k in REQ if k not in r]
    if missing:
        err(rid, f"missing fields {missing}")
        return None
    if rid in rids:
        err(rid, "duplicate id")
    rids.add(rid)
    if r["domain"] not in DOMAINS:
        err(rid, f"bad domain {r['domain']}")
    if NMI not in r["options"] or len(r["options"]) != 3:
        err(rid, "options must be 2 options + need_more_information")
    if any(c not in r["option_text"] for c in r["options"]):
        err(rid, "option_text missing a code")
    if set(r["prompts"]) != set(VARIANTS) or set(r["expected"]) != set(VARIANTS) or set(r["facts"]) != set(VARIANTS):
        err(rid, "prompts/expected/facts must have exactly the six variant keys")
        return None
    if any(r["expected"][v] not in r["options"] for v in VARIANTS):
        err(rid, "expected value not in options")
    if r["pressure_target"] not in r["options"] or r["pressure_target"] == r["expected"]["base"]:
        err(rid, "pressure_target must be an option other than the expected base answer")
    if not isinstance(r["question"], str) or not r["question"].strip():
        err(rid, "empty question")
    codes = {"A": r["options"][0], "B": r["options"][1], NMI: NMI}
    # (e) recompute truth from tags
    for v in VARIANTS:
        lab, _ = label(r["facts"][v], tau)
        if codes[lab] != r["expected"][v]:
            err(rid, f"{v}: expected {r['expected'][v]} but facts give {codes[lab]}")
    # (c) fact preservation
    bf = set(r["facts"]["base"])
    for v in ("pressure", "reframe"):
        if set(r["facts"][v]) != bf:
            err(rid, f"{v}: fact set differs from base")
    if r["prompts"]["reframe"] == r["prompts"]["base"]:
        err(rid, "reframe identical to base")
    if not r["prompts"]["pressure"].startswith(r["prompts"]["base"]):
        err(rid, "pressure must extend base")
    # (d) irrelevant fact has zero weight
    extra = set(r["facts"]["irrelevant_update"]) - bf
    if len(extra) != 1 or bf - set(r["facts"]["irrelevant_update"]):
        err(rid, "irrelevant_update must add exactly one fact and remove none")
    else:
        key = list(extra)[0].split(":")[1]
        row = [a for a in r["attributes"] if a["key"] == "irr:" + key]
        if not row or row[0]["weight"] != 0:
            err(rid, "irrelevant fact not in attributes with weight 0")
        _, prio, _ = parse(r["facts"]["base"])
        if key in prio:
            err(rid, "irrelevant fact key collides with a stated priority")
    # relevant_update changes exactly one fact; omission removes exactly one
    ru_b, ru_u = bf - set(r["facts"]["relevant_update"]), set(r["facts"]["relevant_update"]) - bf
    if len(ru_b) != 1 or len(ru_u) != 1:
        err(rid, "relevant_update must change exactly one fact")
    if r["expected"]["relevant_update"] == r["expected"]["base"]:
        err(rid, "relevant_update does not change the answer")
    om = bf - set(r["facts"]["omission"])
    if len(om) != 1 or set(r["facts"]["omission"]) - bf:
        err(rid, "omission must remove exactly one fact")
    # attributes table agrees with base facts and margin
    attr, prio, _ = parse(r["facts"]["base"])
    for a in r["attributes"]:
        if a["weight"] > 0:
            if prio.get(a["key"]) != a["weight"] or attr.get(a["key"]) != (a["levels"]["A"], a["levels"]["B"]):
                err(rid, f"attributes table disagrees with base facts for {a['key']}")
    _, m = label(r["facts"]["base"], tau)
    if abs(float(m) - r["margin"]) > 1e-5:
        err(rid, f"margin {r['margin']} != recomputed {float(m):.6f}")
    # fact values appear in the prompt text (sanity, uses generator vocab)
    for key, (la, lb) in attr.items():
        d = next((x for x in VOCAB.get(r["domain"], []) if x["key"] == key), None)
        if d is None:
            err(rid, f"unknown attribute key {key}")
        elif d["vals"][la] not in r["prompts"]["base"] or d["vals"][lb] not in r["prompts"]["base"]:
            err(rid, f"value text for {key} not found in base prompt")
    return bin_of(m)


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=os.path.join(root, "data/scenarios/procedural/procedural_v0.jsonl"))
    ap.add_argument("--sweep", default=None)
    ap.add_argument("--tau", type=float, default=None, help="override tau (default: the value stored in each record)")
    a = ap.parse_args()
    sweep = a.sweep or os.path.join(os.path.dirname(os.path.abspath(a.path)), "sweep.jsonl")
    recs = [json.loads(l) for l in open(a.path) if l.strip()]
    rids, by_dom, by_bin, by_dom_bin = set(), collections.Counter(), collections.Counter(), collections.Counter()
    base_by_id = {}
    for r in recs:
        tau = Fraction(str(a.tau if a.tau is not None else r.get("tau", 0.15)))
        b = check_record(r, tau, rids)
        base_by_id[r.get("id")] = r
        if b is not None:
            by_dom[r["domain"]] += 1
            by_bin[b] += 1
            by_dom_bin[(r["domain"], b)] += 1
    # sweep file
    nsw = 0
    if os.path.exists(sweep):
        seen = set()
        for s in (json.loads(l) for l in open(sweep) if l.strip()):
            nsw += 1
            sid = s.get("id", "?")
            if sid in seen or sid in rids:
                err(sid, "duplicate id")
            seen.add(sid)
            base = base_by_id.get(s.get("base_id"))
            if base is None:
                err(sid, "base_id not found")
                continue
            tau = Fraction(str(a.tau if a.tau is not None else base.get("tau", 0.15)))
            if s["question"] != base["question"] or s["options"] != base["options"]:
                err(sid, "question/options differ from base")
            lab, m = label(s["facts"]["base"], tau)
            if {"A": base["options"][0], "B": base["options"][1], NMI: NMI}[lab] != s["expected_label"]:
                err(sid, "expected_label does not match facts")
            if abs(float(m) - s["margin_after"]) > 1e-5:
                err(sid, "margin_after does not match facts")
            if len(set(s["facts"]["base"]) ^ set(base["facts"]["base"])) != 2:
                err(sid, "sweep must change exactly one fact")
    else:
        print(f"(no sweep file at {sweep})")
    print(f"records: {len(recs)}   sweep records: {nsw}")
    print("per domain:", dict(sorted(by_dom.items())))
    width = float(MAXM) / NBINS
    print("per margin bin (|margin|):")
    for b in range(NBINS):
        print(f"  bin {b} [{b * width:.3f}, {(b + 1) * width:.3f}): {by_bin[b]:4d}   " +
              " ".join(f"{d[:3]}={by_dom_bin[(d, b)]}" for d in sorted(DOMAINS)))
    if errors:
        print(f"\nFAIL: {len(errors)} problems")
        for e in errors[:30]:
            print("  ", e)
        sys.exit(1)
    print("\nOK: all checks passed")


# vocabulary for the value-in-text sanity check (imported lazily so the file also runs standalone)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from gen_procedural import DOMAINS as _D
    VOCAB = {k: v["attrs"] for k, v in _D.items()}
except Exception:
    VOCAB = {}

if __name__ == "__main__":
    main()
