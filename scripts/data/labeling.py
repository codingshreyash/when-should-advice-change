"""Blind relabeling: make the sheet, then score two labelers' sheets.

  make   python3 scripts/data/labeling.py make data/scenarios/career_v2.jsonl
         -> data/labeling/career_v2_sheet.csv   (hand this out; rows shuffled, opaque row ids)
            data/labeling/career_v2_key.csv     (keep private; maps row id -> scenario::variant)

  score  python3 scripts/data/labeling.py score data/scenarios/career_v2.jsonl A.csv B.csv \\
             --labeler-a ID_A --labeler-b ID_B
         -> agreement and Cohen's kappa, overall and per variant, and each sheet's agreement
            with the scenario author's draft labels (a diagnostic only)
            data/labeling/career_v2_blind.jsonl  (scenarios with `expected` replaced by the
            blind labels; where the two labelers disagree the label is a list of both; every
            row carries `label_source: "blind"` and `label_provenance`: the labeler ids and
            the sha256 of both sheets, the key and the scenario file)

  score refuses, writing nothing, when: the two sheets are the same file or have identical
  contents; the labeler ids are missing or equal; a sheet has a column that is not on the
  handed-out sheet and names a variant, key, reference or draft; a sheet is incomplete (a
  key row is missing, blank or not an option); or a sheet's labels equal the draft labels
  on every row.

Then score results against the blind labels:
         python3 scripts/analysis/metrics.py --labels data/labeling/career_v2_blind.jsonl results/...
"""
import argparse, csv, hashlib, json, os, random, sys, collections

VARIANTS = ("base", "pressure", "reframe", "relevant_update", "subthreshold_update", "irrelevant_update", "omission")
SHEET_COLUMNS = ("row_id", "prompt", "question", "options", "your_label", "why")
#: a sheet column whose name contains one of these is not something a blind labeler fills in
FORBIDDEN_COLUMN_PARTS = ("variant", "key", "reference", "draft", "expected")

def paths(scen_path):
    stem = os.path.splitext(os.path.basename(scen_path))[0]
    d = "data/labeling"
    return (f"{d}/{stem}_sheet.csv", f"{d}/{stem}_key.csv", f"{d}/{stem}_blind.jsonl")

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def sha256(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def make(scen_path):
    sheet, key, _ = paths(scen_path)
    items = [(s, v) for s in load(scen_path) for v in VARIANTS if v in s["prompts"]]
    random.Random(1684).shuffle(items)
    os.makedirs(os.path.dirname(sheet), exist_ok=True)
    with open(sheet, "w", newline="") as fs, open(key, "w", newline="") as fk:
        ws, wk = csv.writer(fs), csv.writer(fk)
        ws.writerow(list(SHEET_COLUMNS))
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
        r = csv.DictReader(f)
        rows = list(r)
        return list(r.fieldnames or []), {row["row_id"]: row for row in rows}

def refuse(msg):
    raise SystemExit(f"score: not scored. {msg}")

def check_inputs(sheet_a, sheet_b, labeler_a, labeler_b):
    """Provenance checks that need only the files and ids."""
    ids = [(x or "").strip() for x in (labeler_a, labeler_b)]
    if not all(ids):
        refuse("Both labeler ids are required (--labeler-a, --labeler-b).")
    if ids[0] == ids[1]:
        refuse("The two labeler ids are the same; score needs sheets from two different people.")
    if os.path.realpath(sheet_a) == os.path.realpath(sheet_b):
        refuse("Both sheet arguments point to the same file; score needs two separately completed sheets.")
    if sha256(sheet_a) == sha256(sheet_b):
        refuse("The two sheets have identical contents; score needs two separately completed sheets.")
    return ids

def score(scen_path, sheet_a, sheet_b, labeler_a=None, labeler_b=None):
    ids = check_inputs(sheet_a, sheet_b, labeler_a, labeler_b)
    _, key, out = paths(scen_path)
    S = {s["id"]: s for s in load(scen_path)}
    with open(key, newline="") as f:
        K = {r["row_id"]: r["item_key"].split("::") for r in csv.DictReader(f)}
    sheets = {}
    for who, p in (("A", sheet_a), ("B", sheet_b)):
        cols, rows = read_sheet(p)
        extra = [c for c in cols if c not in SHEET_COLUMNS and any(x in c.lower() for x in FORBIDDEN_COLUMN_PARTS)]
        if extra:
            refuse(f"Sheet {who} has column(s) {extra}, which are not on the handed-out sheet. "
                   "Labels must come from a copy of the handed-out sheet.")
        sheets[who] = rows
    problems = []
    for who, X in sheets.items():
        for rid in sorted(set(X) - set(K)):
            problems.append(f"sheet {who}: row {rid} is not in the key")
        for rid, (sid, v) in K.items():
            lab = X.get(rid, {}).get("your_label", "").strip()
            if rid not in X:
                problems.append(f"sheet {who}: row {rid} is missing")
            elif lab not in S[sid]["options"]:
                problems.append(f"sheet {who}: row {rid}: {lab!r} is not an option")
    if problems:
        for m in problems: print("PROBLEM", m)
        refuse(f"{len(problems)} row problem(s) listed above; every row needs exactly one option code.")
    lab = {who: {rid: X[rid]["your_label"].strip() for rid in K} for who, X in sheets.items()}
    draft = {rid: S[sid]["expected"].get(v) for rid, (sid, v) in K.items()}
    for who in ("A", "B"):
        same = sum(lab[who][rid] == draft[rid] for rid in K)
        print(f"diagnostic: sheet {who} matches the draft labels on {same}/{len(K)} rows")
        if same == len(K):
            refuse(f"Sheet {who}'s labels equal the scenario author's draft labels on every row, so "
                   "they cannot be told apart from the drafts. Please check with the PI before scoring it.")
    by_var = collections.defaultdict(list)
    labels = collections.defaultdict(dict)
    for rid, (sid, v) in K.items():
        a, b = lab["A"][rid], lab["B"][rid]
        by_var[v].append((a, b))
        labels[sid][v] = a if a == b else [a, b]
    allp = [p for v in VARIANTS for p in by_var[v]]
    print(f"{'variant':16} {'n':>4} {'agree':>6} {'kappa':>6}")
    for v in VARIANTS + ("ALL",):
        ps = allp if v == "ALL" else by_var[v]
        if ps: print(f"{v:16} {len(ps):4d} {sum(a == b for a, b in ps)/len(ps):6.2f} {kappa(ps):6.2f}")
    prov = {
        "labelers": {"A": ids[0], "B": ids[1]},
        "sheet_sha256": {"A": sha256(sheet_a), "B": sha256(sheet_b)},
        "key_sha256": sha256(key),
        "scenarios_sha256": sha256(scen_path),
        "scored_by": "scripts/data/labeling.py score",
    }
    with open(out, "w") as f:
        for sid, s in S.items():
            f.write(json.dumps({**s, "expected": labels[sid], "draft_expected": s["expected"],
                                "label_source": "blind", "label_provenance": prov}) + "\n")
    print(f"blind labels -> {out}")

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    mk.add_argument("scenarios")
    sc = sub.add_parser("score")
    sc.add_argument("scenarios")
    sc.add_argument("sheet_a")
    sc.add_argument("sheet_b")
    sc.add_argument("--labeler-a", required=True)
    sc.add_argument("--labeler-b", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "make":
        make(a.scenarios)
    else:
        score(a.scenarios, a.sheet_a, a.sheet_b, a.labeler_a, a.labeler_b)

if __name__ == "__main__":
    main()
