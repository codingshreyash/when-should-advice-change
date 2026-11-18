"""Did the neutral rewrite remove the pressure sentence and keep the facts?

  (a) leakage   share of rewritten PRESSURE prompts that still carry the pressure wording.
                generated scenarios (have `attributes`): contains 'want to hear'.
                other scenarios: the pressure sentence is found by diffing the original pressure
                prompt against the original base prompt; a rewrite leaks if it shares any word
                4-gram with that sentence. 'base4' repeats the 4-gram test on the rewritten BASE
                prompt, a false-positive baseline (common phrases).
  (b) facts     generated scenarios only. A variant item passes when every attribute value text
                that appears in its original prompt, and every number in the original prompt,
                appears in the rewrite (case-insensitive, thousands commas ignored).
  (c) length    mean words(rewritten) / words(original) per variant.
  (d) truncated rewrites that hit max_new_tokens (the original text was kept for these).

Usage: python3 scripts/analysis/rewrite_check.py REWRITTEN.jsonl [--scenarios ORIG.jsonl ...]
(originals are also stored in the rewritten file as `original_prompts`; --scenarios overrides.)
"""
import argparse, collections, json, re, statistics

FACT_VARIANTS = ["base", "relevant_update", "omission", "irrelevant_update"]

def read(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def words(t): return re.findall(r"[a-z0-9$%']+", t.lower())
def grams(t, n=4):
    w = words(t); return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
def norm(t): return re.sub(r"(?<=\d),(?=\d)", "", t.lower())
def numbers(t): return re.findall(r"\d+(?:\.\d+)?", norm(t))

def sentences(t): return [x.strip() for x in re.split(r"(?<=[.!?])\s+", t) if x.strip()]

def pressure_sentence(orig_base, orig_press):
    if orig_press.startswith(orig_base):
        return orig_press[len(orig_base):].strip()
    b = set(sentences(orig_base))
    return " ".join(x for x in sentences(orig_press) if x not in b)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rewritten"); ap.add_argument("--scenarios", nargs="*", default=[])
    a = ap.parse_args()
    R = read(a.rewritten)
    O = {r["id"]: r["prompts"] for p in a.scenarios for r in read(p)}
    orig = lambda r: O.get(r["id"], r.get("original_prompts", {}))

    print(f"file: {a.rewritten}  ({len(R)} scenarios)")
    print(f"instruction: {R[0]['rewrite_meta']['instruction']}\n")

    # (a) leakage
    leak, base4 = [], []
    for r in R:
        o, p = orig(r), r["prompts"]
        if "pressure" not in p or "base" not in o or "pressure" not in o: continue
        if "attributes" in r:
            leak.append(("want to hear" in p["pressure"].lower(), r["id"]))
        else:
            g = grams(pressure_sentence(o["base"], o["pressure"]))
            leak.append((bool(g & grams(p["pressure"])), r["id"]))
            if "base" in p: base4.append(bool(g & grams(p["base"])))
    if leak:
        print(f"(a) leakage: {sum(x for x, _ in leak)}/{len(leak)} rewritten pressure prompts "
              f"still carry the pressure wording ({sum(x for x, _ in leak) / len(leak):.2f})"
              + (f"; false-positive baseline on rewritten base: {sum(base4)}/{len(base4)}" if base4 else ""))
    else:
        print("(a) leakage: no pressure prompts")

    # (b)-(d) per variant table
    variants = sorted({v for r in R for v in r["prompts"]})
    print("\n(b) fact preservation (generated scenarios), (c) length ratio, (d) truncated")
    print(f"{'variant':<18}{'n':>5}{'facts ok':>10}{'text ok':>9}{'nums ok':>9}{'len ratio':>11}{'trunc':>7}")
    fails = []
    for v in variants:
        n = ok = tok = nok = 0; ratios = []; tr = 0
        for r in R:
            if v not in r["prompts"]: continue
            new, old = r["prompts"][v], orig(r).get(v)
            if old is None: continue
            ratios.append(len(words(new)) / max(1, len(words(old))))
            tr += bool(r["rewrite_meta"]["truncated"].get(v))
            if "attributes" in r and v in FACT_VARIANTS:
                nn = norm(new); no = norm(old)
                vals = [t for at in r["attributes"] for t in at.get("values", {}).values() if t and norm(t) in no]
                miss_t = [t for t in vals if norm(t) not in nn]
                miss_n = [x for x in dict.fromkeys(numbers(old)) if not re.search(r"(?<![\d.])" + re.escape(x) + r"(?![\d]|\.\d)", nn)]
                n += 1; tok += not miss_t; nok += not miss_n; ok += not (miss_t or miss_n)
                if miss_t or miss_n: fails.append((len(miss_t) + len(miss_n), r["id"], v, miss_t, miss_n))
        f = lambda x: f"{x / n:.2f}" if n else "-"
        print(f"{v:<18}{len(ratios):>5}{f(ok):>10}{f(tok):>9}{f(nok):>9}"
              f"{(statistics.fmean(ratios) if ratios else float('nan')):>11.2f}{tr:>7}")
    print(f"\ntruncated total: {sum(sum(r['rewrite_meta']['truncated'].values()) for r in R)}")
    if fails:
        print("\n5 worst fact failures (missing value texts / numbers):")
        for c, i, v, mt, mn in sorted(fails, key=lambda x: -x[0])[:5]:
            print(f"  {i} {v}: texts {mt} numbers {mn}")

if __name__ == "__main__":
    main()
