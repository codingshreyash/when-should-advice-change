"""Arm B: agreement between two labelers, and against the drafters' proposed answers (if the local key files exist).

Usage: python3 scripts/analysis/armb_agreement.py LABELS_A.csv LABELS_B.csv [--keys data/labeling/armb/keys]
Each CSV has columns id, domain, options, acceptable ("|"-separated codes), unsure. Sets of codes are compared.
  exact       the two acceptable sets are identical
  overlap     the two sets share at least one code
  kappa       Cohen's kappa over item x option binary decisions ("is this option acceptable")
  kept        items with identical sets: these would be kept for Arm B
Against the key: exact and overlap of each labeler, and of the kept set. Only counts are printed (no per-item
answers), so the output is safe to commit. Per-item detail is written to --detail if given.
"""
import argparse, csv, json, glob, collections

def read(p):
    out = {}
    for r in csv.DictReader(open(p, newline="")):
        opts = [l.split(":")[0].strip() for l in r["options"].split("\n")]
        out[r["id"]] = {"dom": r["domain"], "opts": opts, "set": frozenset(x.strip() for x in r["acceptable"].split("|") if x.strip()),
                        "unsure": r["unsure"].strip().lower() == "y"}
    return out

def kappa(pairs):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n; pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--keys", default="data/labeling/armb/keys"); ap.add_argument("--detail", default=None)
    x = ap.parse_args()
    A, B = read(x.a), read(x.b); ids = sorted(A)
    assert set(A) == set(B), "different items"
    ex = [i for i in ids if A[i]["set"] == B[i]["set"]]
    ov = [i for i in ids if A[i]["set"] & B[i]["set"]]
    bins = [(int(o in A[i]["set"]), int(o in B[i]["set"])) for i in ids for o in A[i]["opts"]]
    print(f"items {len(ids)}")
    print(f"exact agreement   {len(ex)}/{len(ids)} = {len(ex)/len(ids):.2f}")
    print(f"overlap agreement {len(ov)}/{len(ids)} = {len(ov)/len(ids):.2f}")
    print(f"Cohen's kappa over item x option decisions: {kappa(bins):.2f} (n={len(bins)})")
    print("by domain (exact):", {d: f"{sum(A[i]['dom']==d for i in ex)}/{sum(A[i]['dom']==d for i in ids)}" for d in sorted({A[i]['dom'] for i in ids})})
    u = [i for i in ids if A[i]["unsure"] or B[i]["unsure"]]
    print(f"rows marked unsure by either: {len(u)}; exact agreement on those {sum(i in ex for i in u)}/{len(u)}; on the rest {sum(i in ex for i in ids if i not in u)}/{len(ids)-len(u)}")
    for n, L in (("A", A), ("B", B)):
        c = collections.Counter("nmi_only" if L[i]["set"] == {"need_more_information"} else ("two_or_more" if len(L[i]["set"]) > 1 else "single_option") for i in ids)
        print(f"labeler {n}: {dict(c)}")
    keys = {}
    for f in glob.glob(x.keys + "/*_proposed_key.jsonl"):
        for l in open(f):
            if l.strip(): k = json.loads(l); keys[k["id"]] = frozenset(k["proposed_acceptable"])
    if keys:
        print(f"--- against the drafters' proposed answers ({len(keys)} items; proposals, not labels)")
        for n, L in (("A", A), ("B", B)):
            print(f"labeler {n}: exact {sum(L[i]['set']==keys[i] for i in ids)}/{len(ids)}, overlap {sum(bool(L[i]['set']&keys[i]) for i in ids)}/{len(ids)}")
        print(f"kept items (A and B identical): {len(ex)}; of these identical to the proposal {sum(A[i]['set']==keys[i] for i in ex)}/{len(ex)}, overlapping {sum(bool(A[i]['set']&keys[i]) for i in ex)}/{len(ex)}")
        if x.detail:
            with open(x.detail, "w") as f:
                for i in ids: f.write(f"{i}\tA={sorted(A[i]['set'])}\tB={sorted(B[i]['set'])}\tkey={sorted(keys[i])}\n")

if __name__ == "__main__":
    main()
