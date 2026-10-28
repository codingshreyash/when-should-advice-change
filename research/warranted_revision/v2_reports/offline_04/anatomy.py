"""Prompt anatomy of the direct arm, reconstructed from saved predictions (read-only).

    python3 research/warranted_revision/v2_reports/offline_04/anatomy.py [--results DIR]

1. Prints the exact messages of one smoke-004 direct base call and its pressure follow-up.
2. Verifies, for every direct follow-up call in smoke-003/smoke-004, that the messages are
   exactly [SYSTEM, base_text+OPTIONS+FMT, base completion verbatim, fu_text+OPTIONS+FMT],
   with the same option block in both user turns; reports character spans of each element.
3. Estimates the token share of the appended block from recorded prompt_tokens (exact
   tokenizer unavailable offline): per follow-up, tokens(last user msg + turn overhead) =
   prompt_tokens(fu) - prompt_tokens(base) - completion_tokens(base); then fits
   tokens = case constant + slope * chars(fu_text) across a case's 8 follow-ups.
4. Diffs the smoke-003 vs smoke-004 DIRECT_FORMAT text and lists every direct decision that
   differs between the two runs (lenient DECISION parse for smoke-003).
"""

from __future__ import annotations

import argparse
import difflib
import re
from collections import defaultdict
from pathlib import Path

import common as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=C.RESULTS)
    ap.add_argument("--case", default="dev-refinance-00")
    args = ap.parse_args()
    g = C.gold()
    fidx = C.followup_index(g)
    vis = {f["followup_id"]: f["text"] for c in C.jsonl(C.PKG / "data/v0/dev_inputs.jsonl")
           for f in c["followups"]}
    P = {r: [p for p in C.jsonl(args.results / r / "predictions.jsonl") if p["condition"] == "direct"]
         for r in ("smoke-003", "smoke-004")}

    # 1. one base + one pressure follow-up, verbatim
    p4 = P["smoke-004"]
    base = {p["case_id"]: p for p in p4 if p["turn"] == "base"}
    b = base[args.case]
    fu = next(p for p in p4 if p["case_id"] == args.case and p["followup_id"]
              and fidx[p["followup_id"]][1]["contrast_class"] == "pressure_for_incorrect")
    for p in (b, fu):
        c = p["completion"]
        print(f"===== {p['turn']} {p['followup_id']} order={p['option_order']} gen={p['gen']} "
              f"prompt_tokens={c['prompt_tokens']} completion_tokens={c['completion_tokens']} "
              f"finish={c['finish_reason']}")
        for i, m in enumerate(p["messages"]):
            print(f"--- [{i}:{m['role']}] ({len(m['content'])} chars)\n{m['content']}")
        print(f"--- [completion]\n{c['text']}--- parsed: {p['parsed']['status']} {p['parsed']['choice']}")

    # 2. structural check over all direct follow-ups
    for run, rows in P.items():
        bases = {p["case_id"]: p for p in rows if p["turn"] == "base"}
        n = ok = 0
        spans = defaultdict(list)
        for p in rows:
            if p["turn"] != "followup":
                continue
            n += 1
            m = p["messages"]
            bm = bases[p["case_id"]]["messages"]
            tail_b = m[1]["content"].split("\n\nOptions:\n", 1)
            tail_f = m[3]["content"].split("\n\nOptions:\n", 1)
            opts_b, fmt_b = tail_b[1].split("\n\n", 1)
            opts_f, fmt_f = tail_f[1].split("\n\n", 1)
            cond = (
                [x["role"] for x in m] == ["system", "user", "assistant", "user"]
                and m[0] == bm[0] and m[1] == bm[1]
                and m[2]["content"] == bases[p["case_id"]]["completion"]["text"]
                and opts_b == opts_f and fmt_b == fmt_f
                and tail_f[0] == vis[p["followup_id"]]
            )
            ok += cond
            spans["fu_text"].append(len(tail_f[0]))
            spans["options_block"].append(len("Options:\n" + opts_f))
            spans["format"].append(len(fmt_f))
            spans["last_user_total"].append(len(m[3]["content"]))
        print(f"\n[{run}] direct follow-ups with structure [SYS, base+OPT+FMT, base reply verbatim, "
              f"fu+OPT+FMT] and identical OPT/FMT in both user turns: {ok}/{n}")
        for k, v in spans.items():
            print(f"   chars {k}: min {min(v)} max {max(v)}")
        fmt_text = fmt_f
        print(f"   follow-up FMT text: {fmt_text!r}")

    # 3. token share estimate (smoke-004)
    import statistics as st
    rows = P["smoke-004"]
    bases = {p["case_id"]: p for p in rows if p["turn"] == "base"}
    per_case = defaultdict(list)
    for p in rows:
        if p["turn"] != "followup":
            continue
        bb = bases[p["case_id"]]["completion"]
        extra = p["completion"]["prompt_tokens"] - bb["prompt_tokens"] - bb["completion_tokens"]
        txt = p["messages"][3]["content"].split("\n\nOptions:\n", 1)[0]
        per_case[p["case_id"]].append((len(txt), extra))
    # pooled slope with case fixed effects (closed form)
    xs = [(x - st.mean([a for a, _ in v]), y - st.mean([b for _, b in v]))
          for v in per_case.values() for x, y in v]
    slope = sum(x * y for x, y in xs) / sum(x * x for x, _ in xs)
    print("\n[tokens, smoke-004 direct] base prompt_tokens",
          sorted(p["completion"]["prompt_tokens"] for p in bases.values()),
          "| follow-up prompt_tokens range",
          min(p["completion"]["prompt_tokens"] for p in rows if p["turn"] == "followup"), "-",
          max(p["completion"]["prompt_tokens"] for p in rows if p["turn"] == "followup"))
    allx = [y for v in per_case.values() for _, y in v]
    print(f"   last user msg + turn overhead: {min(allx)}-{max(allx)} tokens; slope {slope:.3f} tok/char of fu text")
    for cid, v in sorted(per_case.items()):
        const = st.mean([y for _, y in v]) - slope * st.mean([x for x, _ in v])
        print(f"   {cid}: estimated tokens(options block + FMT + turn overhead) ~ {const:.0f}")

    # 4. smoke-003 vs smoke-004 format text and decision differences
    b3 = next(p for p in P["smoke-003"] if p["turn"] == "base")
    b4 = next(p for p in P["smoke-004"] if p["turn"] == "base" and p["case_id"] == b3["case_id"])
    print("\n[format diff smoke-003 -> smoke-004, base user message]")
    for ln in difflib.unified_diff(b3["messages"][1]["content"].splitlines(),
                                   b4["messages"][1]["content"].splitlines(), lineterm="", n=0):
        if ln.startswith(("-", "+")) and not ln.startswith(("---", "+++")):
            print("  ", ln)
    m4 = {(p["case_id"], p["followup_id"]): p for p in P["smoke-004"]}
    same = 0
    for p in P["smoke-003"]:
        f = re.findall(r"DECISION:\s*`?([a-z][a-z0-9_]*)", p["completion"]["text"])
        a = f[-1] if f and len(set(f)) == 1 else None
        q = m4[(p["case_id"], p["followup_id"])]["parsed"]["choice"]
        if a == q:
            same += 1
        else:
            cls = "base" if p["followup_id"] is None else fidx[p["followup_id"]][1]["contrast_class"]
            print(f"   differs: {p['case_id']} {cls}: smoke-003 {a} ({p['parsed']['status']}) vs smoke-004 {q}")
    print(f"   identical direct decisions (lenient parse of smoke-003): {same}/{len(P['smoke-003'])}")


if __name__ == "__main__":
    main()
