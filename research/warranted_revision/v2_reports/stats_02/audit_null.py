"""Shortcut-audit null calibration (CPU, synthetic text; no benchmark data used).

Question: when the labels carry NO lexical signal, what does family-grouped CV accuracy of a
TF-IDF logistic regression look like, how wide is its CI, and how many items are needed for the
acceptance rule 'upper 95% bound of balanced accuracy <= chance + delta' to be passable?

Synthetic items: each family has its own vocabulary (topic words) plus shared filler; labels are
assigned independently of text (pure null) OR with a planted cue token in a fraction q of items
of one class (to check sensitivity). Evaluation: GroupKFold(5) by family; balanced accuracy over
pooled out-of-fold predictions; CI = family-cluster bootstrap of the out-of-fold correctness
(studentised via t on family means is also shown); plus a within-family label-permutation null.
Run: python3 audit_null.py  (~2-4 min)
"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import GroupKFold

RNG = np.random.default_rng(11)
FILLER = [f"w{i}" for i in range(300)]


def make(G, m, k, q=0.0):
    texts, y, fam = [], [], []
    for g in range(G):
        topic = [f"t{g}_{i}" for i in range(30)]
        labs = np.resize(np.arange(k), m)  # balanced within family
        RNG.shuffle(labs)
        for lab in labs:
            words = list(RNG.choice(FILLER, 25)) + list(RNG.choice(topic, 10))
            if lab == 0 and RNG.random() < q:
                words.append("cueword")
            texts.append(" ".join(words))
            y.append(lab)
            fam.append(g)
    return texts, np.array(y), np.array(fam)


def cv_pred(texts, y, fam):
    pred = np.empty_like(y)
    for tr, te in GroupKFold(5).split(texts, y, fam):
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
        Xtr = vec.fit_transform([texts[i] for i in tr])
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, y[tr])
        pred[te] = clf.predict(vec.transform([texts[i] for i in te]))
    return pred


def fam_boot_upper(y, pred, fam, B=1000):
    fams = np.unique(fam)
    idx_by = {f: np.where(fam == f)[0] for f in fams}
    vals = []
    for _ in range(B):
        draw = RNG.choice(fams, len(fams))
        ii = np.concatenate([idx_by[f] for f in draw])
        vals.append(balanced_accuracy_score(y[ii], pred[ii]))
    return np.percentile(vals, 97.5)


if __name__ == "__main__":
    print("k  G  m   q   | mean bal.acc  sd   | mean upper95  P(upper<=chance+0.10)")
    for k in (2, 6):
        chance = 1 / k
        for G, m in ((10, 12), (20, 12), (30, 12), (20, 24)):
            for q in (0.0, 0.5):
                accs, ups = [], []
                for _ in range(25):
                    t, y, f = make(G, m, k, q)
                    p = cv_pred(t, y, f)
                    accs.append(balanced_accuracy_score(y, p))
                    ups.append(fam_boot_upper(y, p, f, 400))
                ups = np.array(ups)
                print(f"{k}  {G:2d} {m:2d} {q:.1f}  |  {np.mean(accs):.3f}     {np.std(accs):.3f} |"
                      f"  {ups.mean():.3f}        {(ups <= chance + 0.10).mean():.2f}")
