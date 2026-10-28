"""Audit: do the career scenarios resemble Bespoke-Nimble's published training data?

Run before any GPU spending on the Nimble-vs-Qwen comparison. Compares every career prompt
(all 7 variants of the 30 scenarios, plus the neutral-mention and preference controls in
data/derived/pressure_controls.jsonl) with the text of every record in Nimble's
data/train.jsonl and data/eval.jsonl.

    python3 -I scripts/analysis/nimble_overlap.py <nimble clone> [out.json]

The Nimble clone is read as data only (no code from it is imported). Measures:
  1. lexical: TF-IDF (word 1-2 grams) cosine of each career prompt with its nearest Nimble
     record, against the same measure between different career scenarios as a scale anchor;
  2. verbatim: the longest word n-gram a career prompt shares with any Nimble record;
  3. topic: Nimble records that mention career-decision terms;
  4. task shape: Nimble records with pressure-like first-person requests, and records whose
     answer options or reference target are clarification / abstention / hold codes.
"""
import json, os, re, sys
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

CAREER = ["data/scenarios/career_pilot.jsonl", "data/scenarios/career_v2.jsonl"]
CONTROLS = "data/derived/pressure_controls.jsonl"
CONTROL_KEYS = ["mention_target", "pref_target", "pref_target_1p", "filler"]
MAX_N = 30

CAREER_TERMS = ["job offer", "salary", "resign", "quit", "promotion", "career", "relocat",
                "interview", "severance", "layoff", "laid off", "startup", "equity", "graduate school",
                "mba", "bootcamp", "sabbatical", "freelanc", "commute", "raise", "counteroffer",
                "counter-offer", "hiring manager", "recruiter"]
# Built to catch the 30 pressure sentences in our own scenarios (checked in main(): a
# detector that misses our pressure prompts cannot certify that Nimble has none).
PRESSURE = [r"\b(?:want|wants|like|hope|hoping|hopes) (?:to )?(?:hear|be told|someone)\b",
            r"\bwant reassurance\b", r"\b(?:leaning|inclined|set on|keen on|basically decided)\b",
            r"\balready told\b", r"\bwould rather just\b", r"\bwant to just\b",
            r"\bwant to come clean\b", r"\bI really\b", r"\bI(?:'d| would) (?:really )?(?:like|prefer|love)\b",
            r"\bI want\b", r"\bplease just\b", r"\binsists?\b", r"\bjust tell me\b", r"\bare you sure\b"]
ABSTAIN = re.compile(r"clarif|more_info|more information|insufficient|unresolved|missing|"
                     r"request|hold|defer|abstain|cannot be determined|undetermined|verify", re.I)

def strings(v):
    """Every string inside a JSON value (Nimble's state is a string, a list or a dict)."""
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(x, (dict, list)):
                yield str(k)
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif v is not None:
        yield str(v)

def tokens(text):
    return re.findall(r"[a-z0-9$%]+(?:'[a-z]+)?", text.lower())

def career_items(root="."):
    items = []
    for f in CAREER:
        for line in open(os.path.join(root, f)):
            s = json.loads(line)
            for v, p in s["prompts"].items():
                items.append({"id": s["id"], "variant": v, "text": f"{p}\n{s['question']}"})
    for line in open(os.path.join(root, CONTROLS)):
        s = json.loads(line)
        for v in CONTROL_KEYS:
            if v in s["prompts"]:
                items.append({"id": s["id"], "variant": v, "text": f"{s['prompts'][v]}\n{s['question']}"})
    return items

def option_texts(root="."):
    out = {}
    for f in CAREER:
        for line in open(os.path.join(root, f)):
            s = json.loads(line)
            out[s["id"]] = " ".join(f"{c} {s['option_text'][c]}" for c in s["options"])
    return out

def nimble_records(clone):
    recs = []
    for split in ("train", "eval"):
        for line in open(os.path.join(clone, "data", f"{split}.jsonl")):
            r = json.loads(line)
            q = r["input"]["questions"]["decision"]
            crit = q.get("criteria") or {}
            state = " ".join(strings(r["input"]["state"]))
            recs.append({"id": r["id"], "split": split, "domain": r["domain"], "variant": r["variant"],
                         "type": q["type"], "state": state, "instructions": q.get("instructions", ""),
                         "codes": list(crit) if isinstance(crit, dict) else [],
                         "criteria": " ".join(strings(crit)),
                         "target": (r.get("reference") or {}).get("target")})
    for r in recs:
        r["text"] = f"{r['state']}\n{r['instructions']}\n{r['criteria']}"
    return recs

def ngram_index(docs, n):
    idx = {}
    for i, toks in enumerate(docs):
        for j in range(len(toks) - n + 1):
            idx.setdefault(tuple(toks[j:j + n]), i)
    return idx

def longest_shared(query_toks, indexes):
    """Longest n (<= MAX_N) such that some n-gram of the query occurs in a Nimble record."""
    best, where = 0, None
    for n in range(1, MAX_N + 1):
        hit = None
        for j in range(len(query_toks) - n + 1):
            k = tuple(query_toks[j:j + n])
            if k in indexes[n]:
                hit = (indexes[n][k], " ".join(k))
                break
        if hit is None:
            break
        best, where = n, hit
    return best, where

def main(clone, out=None):
    items, opts, recs = career_items(), option_texts(), nimble_records(clone)
    ours = [x for x in items if x["variant"] == "pressure"]
    caught = sum(any(re.search(p, x["text"], re.I) for p in PRESSURE) for x in ours)
    base_hits = sum(any(re.search(p, x["text"], re.I) for p in PRESSURE) for x in items if x["variant"] == "base")
    n_train = sum(r["split"] == "train" for r in recs)

    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    vec.fit([r["text"] for r in recs] + [x["text"] for x in items])
    C = vec.transform([x["text"] for x in items])
    N = vec.transform([r["text"] for r in recs])
    sim = (C @ N.T).toarray()
    nearest = sim.argmax(1)
    max_sim = sim.max(1)

    # scale anchor: each career prompt vs the base prompts of the *other* 29 scenarios
    ids = sorted({x["id"] for x in items})
    base_rows = {x["id"]: i for i, x in enumerate(items) if x["variant"] == "base"}
    CC = (C @ C[[base_rows[i] for i in ids]].T).toarray()
    other = np.array([max(CC[k, j] for j, sid in enumerate(ids) if sid != x["id"])
                      for k, x in enumerate(items)])

    # option-text similarity (the scorer also sees option descriptions)
    O = vec.transform([opts[i] for i in ids])
    opt_sim = (O @ N.T).toarray().max(1)

    ntoks = [tokens(r["text"]) for r in recs]
    indexes = {n: ngram_index(ntoks, n) for n in range(1, MAX_N + 1)}
    shared = [longest_shared(tokens(x["text"]), indexes) for x in items]

    top = np.argsort(-max_sim)[:10]
    topic = Counter()
    topic_records = {}
    for r in recs:
        low = r["text"].lower()
        hits = [t for t in CAREER_TERMS if t in low]
        for t in hits:
            topic[t] += 1
        if hits:
            topic_records[r["id"]] = (r["domain"], r["split"], hits)
    pressure = [r for r in recs if any(re.search(p, r["state"] + " " + r["instructions"], re.I) for p in PRESSURE)]
    abst_code = [r for r in recs if any(ABSTAIN.search(c) for c in r["codes"])]
    abst_target = [r for r in recs if r["target"] and ABSTAIN.search(str(r["target"]))]

    summary = {
        "nimble": {"records": len(recs), "train": n_train, "eval": len(recs) - n_train,
                   "domains": Counter(r["domain"] for r in recs if r["split"] == "train"),
                   "question_types": Counter(r["type"] for r in recs)},
        "career_prompts": len(items),
        "tfidf_max_cosine_to_nimble": {
            "max": float(max_sim.max()), "median": float(np.median(max_sim)),
            "p95": float(np.percentile(max_sim, 95)),
            "nearest_domains": Counter(recs[j]["domain"] for j in nearest)},
        "tfidf_max_cosine_to_other_career_scenarios": {
            "min": float(other.min()), "median": float(np.median(other))},
        "prompts_closer_to_nimble_than_to_any_other_career_scenario": int((max_sim > other).sum()),
        "option_text_max_cosine_to_nimble": {"max": float(opt_sim.max()), "median": float(np.median(opt_sim))},
        "longest_shared_word_ngram": {
            "max": max(n for n, _ in shared),
            "distribution": Counter(n for n, _ in shared),
            "longest_examples": sorted({w[1] for n, w in shared if n >= max(m for m, _ in shared) - 1})[:10]},
        "top10_nearest_pairs": [
            {"career": f"{items[k]['id']}:{items[k]['variant']}", "cosine": round(float(max_sim[k]), 3),
             "nimble": recs[nearest[k]]["id"], "domain": recs[nearest[k]]["domain"],
             "split": recs[nearest[k]]["split"], "nimble_state_start": recs[nearest[k]]["state"][:240]}
            for k in top],
        "topic_terms_in_nimble": dict(topic.most_common()),
        "topic_records": {"count": len(topic_records),
                          "train": sum(v[1] == "train" for v in topic_records.values()),
                          "by_domain": Counter(v[0] for v in topic_records.values())},
        "pressure_detector_check": {"our_pressure_prompts_caught": f"{caught}/{len(ours)}",
                                    "our_base_prompts_flagged": f"{base_hits}/{len(ours)}"},
        "pressure_like_records": {"count": len(pressure), "train": sum(r["split"] == "train" for r in pressure),
                                  "examples": [{"id": r["id"], "domain": r["domain"],
                                                "match": next(re.search(p, r["state"] + " " + r["instructions"], re.I).group(0)
                                                              for p in PRESSURE if re.search(p, r["state"] + " " + r["instructions"], re.I))}
                                               for r in pressure[:15]]},
        "abstention_like": {
            "records_offering_such_a_code": len(abst_code),
            "records_whose_reference_is_such_a_code": len(abst_target),
            "example_codes": Counter(c for r in abst_code for c in r["codes"] if ABSTAIN.search(c)).most_common(15)},
        "variants": Counter(r["variant"] for r in recs),
    }
    text = json.dumps(summary, indent=1, default=lambda o: dict(o) if isinstance(o, Counter) else str(o))
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        open(out, "w").write(text + "\n")
    print(text)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
