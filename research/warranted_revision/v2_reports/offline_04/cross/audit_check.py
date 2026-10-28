"""Cross-review (B): checks on v2bench.audit() and behavior(). Read-only; prints only.

    PYTHONPATH=research/warranted_revision/src python3 -B .../cross/audit_check.py
"""
import random, re
from collections import Counter
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from warranted_revision import v2bench as V
from warranted_revision.runner import PKG_ROOT

path = PKG_ROOT / "v2/calibration_draft/items.json"
bases, items = V.load(path)
chk = V.check(path)
beh = {r["item_id"]: r["behavior"] for r in chk["items"]}
fams = sorted({it["family_id"] for it in items})
texts = [it["followup"] for it in items]
y_lab = [it["design_label"] for it in items]
y_beh = [beh[it["item_id"]] for it in items]

def loco(ys, docs=texts, return_pred=False):
    pred = [None] * len(ys)
    for f in fams:
        tr = [i for i, it in enumerate(items) if it["family_id"] != f]
        te = [i for i, it in enumerate(items) if it["family_id"] == f]
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        Xtr = vec.fit_transform([docs[i] for i in tr])
        clf = LogisticRegression(max_iter=2000).fit(Xtr, [ys[i] for i in tr])
        for i, p in zip(te, clf.predict(vec.transform([docs[i] for i in te]))):
            pred[i] = p
    acc = sum(p == g for p, g in zip(pred, ys)) / len(ys)
    return (acc, pred) if return_pred else acc

# 1. LOFO training-majority baseline (the baseline the CV classifiers should beat)
def lofo_majority(ys):
    ok = 0
    for f in fams:
        tr = [ys[i] for i, it in enumerate(items) if it["family_id"] != f]
        maj = Counter(tr).most_common(1)[0][0]
        ok += sum(ys[i] == maj for i, it in enumerate(items) if it["family_id"] == f)
    return ok / len(ys)
print("label: global majority", round(max(Counter(y_lab).values()) / len(y_lab), 3), "LOFO-majority", round(lofo_majority(y_lab), 3))
print("behavior: global KEEP rate", round(y_beh.count("KEEP") / len(y_beh), 3), "LOFO-majority", round(lofo_majority(y_beh), 3))
acc_b, pred_b = loco(y_beh, return_pred=True)
print("tfidf behavior acc", round(acc_b, 3), "predicted classes:", Counter(pred_b))
acc_l, pred_l = loco(y_lab, return_pred=True)
print("tfidf label acc", round(acc_l, 3), "per-label recall:", {l: sum(p == g == l for p, g in zip(pred_l, y_lab)) for l in V.LABELS})
# 2. label-permutation null for the LOFO TF-IDF label accuracy (labels shuffled within family keeps family composition)
rng = random.Random(1684); null = []
for _ in range(200):
    ys = y_lab[:]
    for f in fams:
        idx = [i for i, it in enumerate(items) if it["family_id"] == f]
        vals = [ys[i] for i in idx]; rng.shuffle(vals)
        for i, v in zip(idx, vals): ys[i] = v
    null.append(loco(ys))
print("permutation null (within-family shuffle, 200): mean", round(sum(null) / len(null), 3), "95th pct", round(sorted(null)[189], 3), "p", (1 + sum(n >= acc_l for n in null)) / 201)
# 3. leakage: follow-up strings shared across families
by_text = {}
for it in items:
    by_text.setdefault(it["followup"], set()).add(it["family_id"])
print("follow-up strings appearing in >1 family:", sum(len(v) > 1 for v in by_text.values()))
# 4. keyword lexicon: AMBIGUOUS by default on zero hits
kw = [V._keyword_label(t) for t in texts]
print("lexicon: items predicted AMBIGUOUS (no hit)", kw.count("AMBIGUOUS"), "of which correct", sum(k == g == "AMBIGUOUS" for k, g in zip(kw, y_lab)),
      "| accuracy excluding AMBIGUOUS-default credit", round(sum(k == g and k != "AMBIGUOUS" for k, g in zip(kw, y_lab)) / len(y_lab), 3))

# 5. behavior(): fallback when the adjudicated label has no authored reading
print("\nbehavior() under every alternative adjudicated label:")
fallback = Counter(); examples = []
for it in items:
    b = bases[it["base_id"]]; rds = it["readings"]; have = {r["label"] for r in rds}
    for lab in V.SUBSTANTIVE:
        if lab in have or lab in ("PREFERENCE", "VALIDATION"):
            continue
        out = V.behavior(b, lab, rds)
        fallback[(it["design_label"], lab, out["behavior"])] += 1
        # would a reading with another label but the same content change the answer?
        changing = [r for r in rds if V.reading_action(b, r) != V.action(b["rule"], b["facts"])]
        if changing and out["behavior"] == "KEEP" and len(examples) < 4:
            examples.append((it["item_id"], it["design_label"], "->", lab, out, [r["label"] for r in changing]))
for k, v in sorted(fallback.items()):
    print("  design", k[0], "adjudicated", k[1], "->", k[2], v)
print("  silent KEEP although an authored reading changes the action:")
for e in examples: print("   ", e)
n_swap = sum(1 for it in items for lab in ("FACT_SUPPORTED", "FACT_UNSUPPORTED")
             if lab not in {r["label"] for r in it["readings"]}
             and any(r["label"] in ("FACT_SUPPORTED", "FACT_UNSUPPORTED") and V.reading_action(bases[it["base_id"]], r) != V.action(bases[it["base_id"]]["rule"], bases[it["base_id"]]["facts"]) for r in it["readings"]))
print("  items where a SUPPORTED<->UNSUPPORTED adjudication silently becomes KEEP:", n_swap)

# 6. AMBIGUOUS: unsupported readings treated as 'no change' vs their own accepted behavior (HEDGE)
print("\nAMBIGUOUS items: current vs per-reading-behavior rule")
for it in items:
    if it["design_label"] != "AMBIGUOUS":
        continue
    b = bases[it["base_id"]]
    cur = V.behavior(b, "AMBIGUOUS", it["readings"])
    own = [V.behavior(b, r["label"], [r]) for r in it["readings"]]
    own_set = {(o["behavior"], o.get("action"), o.get("if_true")) for o in own}
    print(f"  {it['item_id']}: readings {[r['label'] for r in it['readings']]} current={cur['behavior']} {cur.get('action') or cur.get('between')}"
          f" | per-reading={[(o['behavior'], o.get('action') or o.get('if_true')) for o in own]}{'  <-- differs' if len(own_set) > 1 and cur['behavior'] != 'HEDGE' else ''}")
# synthetic: AMBIGUOUS between PREFERENCE and a decision-relevant FACT_UNSUPPORTED reading
it = next(i for i in items if i["design_label"] == "FACT_UNSUPPORTED" and V.behavior(bases[i["base_id"]], "FACT_UNSUPPORTED", i["readings"])["behavior"] == "HEDGE")
b = bases[it["base_id"]]
syn = [{"label": "PREFERENCE"}, it["readings"][0]]
print("\nsynthetic AMBIGUOUS {PREFERENCE, FACT_UNSUPPORTED(changes action)} on", it["item_id"], "->", V.behavior(b, "AMBIGUOUS", syn),
      "| same claim as FACT_UNSUPPORTED alone ->", V.behavior(b, "FACT_UNSUPPORTED", it["readings"])["behavior"])
