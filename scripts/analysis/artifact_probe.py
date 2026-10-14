"""Artifact probe, in the spirit of AFLite (Le Bras et al., 2020): can shallow cues tell
the variants apart, and would a model that only used those cues look good on our metrics?

The set is too small (30 scenarios) to filter the way AFLite does, so instead:

  A  diff features vs. base (length change, words added/removed, numbers changed,
     preference words, option words) -> logistic regression, 6-way variant type
  B  the single prompt text only (what a model actually sees) -> TF-IDF logistic
     regression, 7-way (base + the six variants), plus omission-vs-rest and
     relevant_update-vs-base / pressure-vs-base AUROC
  C  shortcut "policies" scored like a model: move iff the text changed by >= k
     words, move iff a number changed, answer need_more_information iff the prompt
     got k+ words shorter. Same d' as discrimination.py.
  D  do Nimble and its base model track the cue? Spearman between how much the text
     changed and how far the option distribution moved, within each variant
  E  for any results file: do a model's need_more_information answers follow prompt
     length (within omission and within complete prompts), and does it change on
     relevant updates that edit a number more than on the others?

All classifiers use leave-one-scenario-out cross-validation, so a scenario's own
wording never leaks into its test fold. Scenarios come from both data/scenarios files;
the optional results files (with option probabilities) are needed only for part D.
Prints to stdout (saved copy: results/summaries/artifact_probe.txt).

Usage: python3 scripts/analysis/artifact_probe.py [results/career/nimble-and-qwen__career_pilot.jsonl results/career/nimble-and-qwen__career_v2.jsonl]
"""
import json, re, sys, collections
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from stats import z, tv, auroc
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

SOURCES = ["data/scenarios/career_pilot.jsonl", "data/scenarios/career_v2.jsonl"]
VARIANTS = ["pressure", "reframe", "relevant_update", "subthreshold_update", "irrelevant_update", "omission"]
NMI = "need_more_information"
PREF = {"want", "wants", "hope", "hoping", "really", "prefer", "prefers", "rather", "wish",
        "told", "already", "decided", "sure", "convinced", "leaning", "feel", "feels"}
STOP = {"the", "a", "an", "to", "of", "and", "in", "for", "with", "at", "on", "is", "are",
        "they", "their", "them", "be", "or", "as", "it", "this", "that", "from", "by", "has", "have"}

words = lambda t: re.findall(r"[a-z']+", t.lower())
numbers = lambda t: re.findall(r"\d[\d,]*(?:\.\d+)?", t)

def diff_features(s, v):
    b, t = s["prompts"]["base"], s["prompts"][v]
    cb, ct = collections.Counter(words(b)), collections.Counter(words(t))
    added, removed = ct - cb, cb - ct
    nb, nt = collections.Counter(numbers(b)), collections.Counter(numbers(t))
    opt = {w for o in s["options"] if o != NMI for w in words(s["option_text"][o])} - STOP
    return {"len_delta": len(words(t)) - len(words(b)),
            "added": sum(added.values()), "removed": sum(removed.values()),
            "num_added": sum((nt - nb).values()), "num_removed": sum((nb - nt).values()),
            "pref_added": sum(n for w, n in added.items() if w in PREF),
            "opt_added": sum(n for w, n in added.items() if w in opt),
            "sent_delta": t.count(". ") - b.count(". ")}

def loso(X, y, groups, make):
    """leave-one-scenario-out predictions (labels and class probabilities)"""
    pred, prob = np.empty(len(y), dtype=object), None
    for g in sorted(set(groups)):
        te = groups == g; tr = ~te
        m = make().fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
        p = m.predict_proba(X[te])
        if prob is None: prob = np.zeros((len(y), len(m.classes_))); classes = m.classes_
        prob[te] = p
    return pred, prob, classes

def confusion(y, pred, labels):
    print("      true \\ pred " + "".join(f"{l[:9]:>10}" for l in labels))
    for t in labels:
        print(f"   {t:>15} " + "".join(f"{sum((y == t) & (pred == p)):10d}" for p in labels))

def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])

def main(result_files):
    S = [json.loads(l) for f in SOURCES for l in open(f) if l.strip()]
    ids = np.array([s["id"] for s in S])
    print(f"{len(S)} scenarios\n")

    # A: diff features
    F = {(s["id"], v): diff_features(s, v) for s in S for v in VARIANTS}
    print("A. Surface change vs. base, per variant (min / mean / max over scenarios)")
    keys = list(next(iter(F.values())))
    for k in keys:
        cells = []
        for v in VARIANTS:
            x = [F[(s["id"], v)][k] for s in S]
            cells.append(f"{v[:8]} {min(x):4d}/{np.mean(x):5.1f}/{max(x):4d}")
        print(f"   {k:12} " + "   ".join(cells))
    X = np.array([[F[(s["id"], v)][k] for k in keys] for s in S for v in VARIANTS], float)
    y = np.array([v for s in S for v in VARIANTS]); g = np.repeat(ids, len(VARIANTS))
    make = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    pred, _, _ = loso(X, y, g, make)
    print(f"\n   variant type from diff features: accuracy {np.mean(pred == y):.2f} (chance {1 / len(VARIANTS):.2f})")
    confusion(y, pred, VARIANTS)
    for a, b in (("relevant_update", "reframe"), ("relevant_update", "pressure")):
        m = np.isin(y, [a, b]); p2, pr2, cl = loso(X[m], y[m], g[m], make)
        pos = pr2[:, list(cl).index(a)]
        print(f"   {a} vs {b}: accuracy {np.mean(p2 == y[m]):.2f}, AUROC "
              f"{auroc(list(pos[y[m] == a]), list(pos[y[m] == b])):.2f}")

    # B: single text only
    print("\nB. The prompt text alone (what a model sees), TF-IDF unigrams+bigrams")
    V5 = ["base"] + VARIANTS
    T = [s["prompts"][v] for s in S for v in V5]
    y5 = np.array([v for s in S for v in V5]); g5 = np.repeat(ids, len(V5))
    class Tfidf:
        def __init__(self): self.v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); self.m = LogisticRegression(max_iter=2000, C=4.0)
        def fit(self, X, y): self.m.fit(self.v.fit_transform(X), y); self.classes_ = self.m.classes_; return self
        def predict(self, X): return self.m.predict(self.v.transform(X))
        def predict_proba(self, X): return self.m.predict_proba(self.v.transform(X))
    T = np.array(T, dtype=object)
    pred5, _, _ = loso(T, y5, g5, Tfidf)
    print(f"   {len(V5)}-way variant type: accuracy {np.mean(pred5 == y5):.2f} (chance {1 / len(V5):.2f})")
    confusion(y5, pred5, V5)
    for a, rest in (("omission", [v for v in V5 if v != "omission"]), ("relevant_update", ["base"]), ("pressure", ["base"])):
        m = np.isin(y5, [a] + rest); yy = np.where(y5[m] == a, a, "other")
        _, pr, cl = loso(T[m], yy, g5[m], Tfidf)
        pos = pr[:, list(cl).index(a)]
        print(f"   {a} vs {'+'.join(rest) if len(rest) == 1 else 'all other prompts'}: AUROC "
              f"{auroc(list(pos[yy == a]), list(pos[yy == 'other'])):.2f}")
    nb = {v: [len(numbers(s["prompts"][v])) for s in S] for v in V5}
    lw = {v: [len(words(s["prompts"][v])) for s in S] for v in V5}
    print(f"   absolute length, omission vs other prompts: AUROC "
          f"{auroc([-x for x in lw['omission']], [-x for v in V5 if v != 'omission' for x in lw[v]]):.2f} "
          f"(shorter = omission)")
    print(f"   numbers in prompt, omission vs other prompts: AUROC "
          f"{auroc([-x for x in nb['omission']], [-x for v in V5 if v != 'omission' for x in nb[v]]):.2f} "
          f"(fewer = omission)")

    # C: shortcut policies
    print("\nC. Shortcut policies scored like a model (hit = relevant_update moves; "
          "false alarm = pressure or reframe moves)")
    def score(name, moves):
        hit = [moves(s, "relevant_update") for s in S]
        fa = [moves(s, v) for s in S for v in ("pressure", "reframe")]
        dp = lambda xs: z(np.mean(hit), len(hit)) - z(np.mean(xs), len(xs))
        iu = [moves(s, "irrelevant_update") for s in S]
        st = [moves(s, "subthreshold_update") for s in S]
        print(f"   {name:44} hit {np.mean(hit):.2f}  d' vs pressure+reframe {dp(fa):+.2f}"
              f"  vs irrelevant {dp(iu):+.2f} (fa {np.mean(iu):.2f})  vs subthreshold {dp(st):+.2f} (fa {np.mean(st):.2f})")
    for k in (1, 3, 5, 10):
        score(f"move iff |length change| >= {k} words", lambda s, v, k=k: abs(F[(s['id'], v)]['len_delta']) >= k)
    score("move iff any number changed", lambda s, v: F[(s["id"], v)]["num_added"] + F[(s["id"], v)]["num_removed"] > 0)
    score("move iff words changed but no preference words", lambda s, v:
          F[(s["id"], v)]["added"] + F[(s["id"], v)]["removed"] > 2 and F[(s["id"], v)]["pref_added"] == 0)
    print("   for comparison (discrimination.py): Qwen base +0.04, Nimble +0.63, Claude +2.2 to +2.4")
    for k in (1, 4, 8):
        ask = {v: np.mean([F[(s["id"], v)]["len_delta"] <= -k for s in S]) for v in VARIANTS}
        print(f"   need_more_information iff >= {k} words shorter: omission asks {ask['omission']:.2f}, "
              f"false asks reframe {ask['reframe']:.2f} / relevant_update {ask['relevant_update']:.2f} / pressure {ask['pressure']:.2f}")

    # D: do the 9B models follow the cue?
    if result_files:
        print("\nD. Does the model's movement track the surface change? Spearman over scenarios, within variant")
        rows = [json.loads(l) for f in result_files for l in open(f) if l.strip()]
        by = collections.defaultdict(dict)
        for r in rows:
            if "probs" in r: by[r["model"]][(r["id"], r["variant"])] = r["probs"]
        for model, d in sorted(by.items()):
            out = []
            for v in ("relevant_update", "reframe", "pressure"):
                pairs = [(F[(s["id"], v)]["added"] + F[(s["id"], v)]["removed"], tv(d[(s["id"], "base")], d[(s["id"], v)]))
                         for s in S if (s["id"], v) in d and (s["id"], "base") in d]
                a, b = zip(*pairs)
                out.append(f"{v} rho {spearman(a, b):+.2f} (n={len(pairs)})")
            print(f"   {model:30} words changed vs. TV moved: " + "   ".join(out))
            om = [(-F[(s["id"], "omission")]["len_delta"], d[(s["id"], "omission")].get(NMI, 0))
                  for s in S if (s["id"], "omission") in d]
            a, b = zip(*om)
            print(f"   {'':30} omission: words removed vs. P(need more information) rho {spearman(a, b):+.2f}")

    # E: do the models' own answers lean on the two cues? (any results file with choices)
    if result_files:
        print("\nE. Cues in the models' answers (legacy and later runs; refused or unparsed rows skipped)")
        rows = [json.loads(l) for f in result_files for l in open(f) if l.strip()]
        ch = collections.defaultdict(dict)
        for r in rows:
            if r.get("sample", 0) == 0 and r.get("stop_reason") != "refusal" and r.get("choice"):
                ch[(r["model"], r.get("condition", ""))][(r["id"], r["variant"])] = r["choice"]
        numeric = {s["id"]: F[(s["id"], "relevant_update")]["num_added"] + F[(s["id"], "relevant_update")]["num_removed"] > 0 for s in S}
        print(f"   relevant updates that change a number: {sum(numeric.values())}/{len(S)}")
        for (model, cond), d in sorted(ch.items()):
            ask = lambda vs, want: [len(words(s["prompts"][v])) for s in S for v in vs
                                    if (s["id"], v) in d and (d[(s["id"], v)] == NMI) == want]
            complete = ["base", "pressure", "reframe", "relevant_update"]
            cells = []
            for name, vs in (("omission", ["omission"]), ("complete", complete)):
                yes, no = ask(vs, True), ask(vs, False)
                a = auroc([-x for x in yes], [-x for x in no]) if yes and no else float("nan")
                cells.append(f"{name} {len(yes)}/{len(yes) + len(no)} asks, AUROC(shorter->ask) {a:.2f}")
            hit = {True: [], False: []}
            for s in S:
                i = s["id"]
                if (i, "base") in d and (i, "relevant_update") in d:
                    hit[numeric[i]].append(d[(i, "relevant_update")] != d[(i, "base")])
            print(f"   {model[:28]:28} {cond:14} " + "; ".join(cells)
                  + f"; relevant updates changed: numeric {sum(hit[True])}/{len(hit[True])}, other {sum(hit[False])}/{len(hit[False])}")

if __name__ == "__main__":
    main(sys.argv[1:])
