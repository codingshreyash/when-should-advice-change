"""Convert public multiple-choice sets into our scenario schema (Arm A of docs/real_world_check.md).

Sets (raw files are downloaded by hand, see docs/real_world_check.md):
  medqa   GBaker/MedQA-USMLE-4-options, phrases_no_exclude_test.jsonl (CC-BY-4.0), 4 options
  csqa    tau/commonsense_qa, validation split as JSON rows (MIT), 5 options. The test split has no labels.
Each set: seeded random sample (random.Random(1684)) of N items, written to
data/scenarios/realworld/<set>.jsonl. Option codes are choice_a, choice_b, ... (not bare letters, so the
code extractor cannot match a stray letter in free text). There is no need_more_information option.
Fields the runners need: id, domain, options, option_text, question, prompts.base, acceptable.base (the gold
code), expected.base, margin (None), margin_bin ("none"). No variants, no margin.

Usage: python3 scripts/data/gen_realworld.py medqa RAW.jsonl [--n 600]
       python3 scripts/data/gen_realworld.py csqa RAW.json  [--n 600]
"""
import argparse, json, os, random

def convert(set_name, raw, n, seed=1684):
    items = []
    if set_name == "medqa":
        for i, r in enumerate(raw):
            letters = sorted(r["options"])
            gold = r["answer_idx"]
            items.append((f"medqa_{i:04d}", r["question"], [r["options"][k] for k in letters], letters.index(gold), "medical_choice"))
    else:
        for r in raw:
            letters = r["choices"]["label"]
            items.append((f"csqa_{r['id'][:8]}", r["question"], r["choices"]["text"], letters.index(r["answerKey"]), "everyday_choice"))
    items = sorted(items)
    chosen = sorted(random.Random(seed).sample(items, min(n, len(items))))
    out = []
    for id_, q, texts, gi, dom in chosen:
        codes = [f"choice_{chr(97 + j)}" for j in range(len(texts))]
        out.append({"id": id_, "domain": dom, "options": codes, "option_text": dict(zip(codes, texts)),
                    "question": "Which option is the best answer?", "prompts": {"base": q},
                    "acceptable": {"base": [codes[gi]]}, "expected": {"base": codes[gi]},
                    "margin": None, "margin_bin": "none"})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set", choices=["medqa", "csqa"]); ap.add_argument("raw")
    ap.add_argument("--n", type=int, default=600); ap.add_argument("--out-dir", default="data/scenarios/realworld")
    a = ap.parse_args()
    raw = ([json.loads(l) for l in open(a.raw) if l.strip()] if a.set == "medqa" else json.load(open(a.raw)))
    out = convert(a.set, raw, a.n)
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, f"{a.set}.jsonl")
    with open(path, "w") as f:
        for s in out: f.write(json.dumps(s) + "\n")
    print(f"wrote {path}: {len(out)} items from {len(raw)}")

if __name__ == "__main__":
    main()
