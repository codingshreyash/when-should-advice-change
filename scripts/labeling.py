"""Blind relabeling: make the sheet, then score two labelers' sheets.

  make   python scripts/labeling.py make data/career_v2.jsonl
         -> data/labeling/career_v2_sheet.csv   (hand this out; rows shuffled, opaque row ids)
            data/labeling/career_v2_key.csv     (keep private; maps row id -> scenario::variant)

  score  python scripts/labeling.py score data/career_v2.jsonl A.csv B.csv
         -> agreement and Cohen's kappa, overall and per variant
            data/labeling/career_v2_blind.jsonl  (scenarios with `expected` replaced by the
            blind labels; where the two labelers disagree the label is a list of both)

Then score results against the blind labels:
         python scripts/analyze.py --labels data/labeling/career_v2_blind.jsonl results/...
"""
import csv, json, os, random, sys, collections

VARIANTS = ("base", "pressure", "reframe", "relevant_update", "omission")

def paths(scen_path):
    stem = os.path.splitext(os.path.basename(scen_path))[0]
    d = "data/labeling"
    return (f"{d}/{stem}_sheet.csv", f"{d}/{stem}_key.csv", f"{d}/{stem}_blind.jsonl")

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def make(scen_path):
    sheet, key, _ = paths(scen_path)
    items = [(s, v) for s in load(scen_path) for v in VARIANTS if v in s["prompts"]]
    random.Random(1684).shuffle(items)
    os.makedirs(os.path.dirname(sheet), exist_ok=True)
    with open(sheet, "w", newline="") as fs, open(key, "w", newline="") as fk:
        ws, wk = csv.writer(fs), csv.writer(fk)
        ws.writerow(["row_id", "prompt", "question", "options", "your_label", "why"])
        wk.writerow(["row_id", "item_key"])
        for n, (s, v) in enumerate(items, 1):
            rid = f"r{n:03d}"
            opts = " | ".join(f"{c} = {s['option_text'][c]}" for c in s["options"])
            ws.writerow([rid, s["prompts"][v], s["question"], opts, "", ""])
            wk.writerow([rid, f"{s['id']}::{v}"])
    print(f"{len(items)} rows -> {sheet} (hand out)\nkey -> {key} (keep private)")

def kappa(pairs):
    n = len(pairs)
    if not n: return float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / n**2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0

def read_sheet(p):
    with open(p, newline="") as f:
        return {r["row_id"]: r for r in csv.DictReader(f)}

def score(scen_path, sheet_a, sheet_b):
    _, key, out = paths(scen_path)
    S = {s["id"]: s for s in load(scen_path)}
    with open(key, newline="") as f:
        K = {r["row_id"]: r["item_key"].split("::") for r in csv.DictReader(f)}
    A, B = read_sheet(sheet_a), read_sheet(sheet_b)
    by_var, problems = collections.defaultdict(list), []
    labels = collections.defaultdict(dict)
    for rid, (sid, v) in K.items():
        a, b = (X.get(rid, {}).get("your_label", "").strip() for X in (A, B))
        opts = S[sid]["options"]
        for who, lab in (("A", a), ("B", b)):
            if lab not in opts: problems.append(f"{rid} ({sid}::{v}) labeler {who}: {lab!r} not an option")
        if a in opts and b in opts:
            by_var[v].append((a, b))
            labels[sid][v] = a if a == b else [a, b]
    for m in problems: print("PROBLEM", m)
    allp = [p for v in VARIANTS for p in by_var[v]]
    print(f"{'variant':16} {'n':>4} {'agree':>6} {'kappa':>6}")
    for v in VARIANTS + ("ALL",):
        ps = allp if v == "ALL" else by_var[v]
        if ps: print(f"{v:16} {len(ps):4d} {sum(a == b for a, b in ps)/len(ps):6.2f} {kappa(ps):6.2f}")
    with open(out, "w") as f:
        for sid, s in S.items():
            f.write(json.dumps({**s, "expected": labels[sid], "draft_expected": s["expected"]}) + "\n")
    print(f"blind labels -> {out}")

if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"make": make, "score": score}[cmd](*args)
