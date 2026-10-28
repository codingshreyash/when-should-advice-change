"""Adversarial shortcut audit, round 2, phase 1, of candidate_v2 (60 items, 6 dev families).

Run from research/warranted_revision:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:v2/ai_precalibration/audit_r2/scripts:v2/ai_precalibration/audit/scripts \
        python3 -W ignore v2/ai_precalibration/audit_r2/scripts/shortcut_audit_r2.py

Writes v2/ai_precalibration/audit_r2/shortcut_results_r2.json.

Gold = the behaviour v2bench computes from the AUTHOR'S design labels and readings (not human
gold). Everything learned is fit leave-one-family-out (LOFO, 6 folds). Hand-written policies are
not fit. "Lexicon (untuned)" = lexicon_untuned_r2.py, frozen before items.json was opened.
"""
from __future__ import annotations

import ast
import itertools
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import binomtest
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.tree import DecisionTreeClassifier, export_text

import lexicon_untuned_r2 as LX2          # mine, frozen before reading items
import lexicon_tuned_r2 as LXT2           # written after reading items (in-sample only)
import lexicon_untuned as LX1             # round-1 auditor's lexicon (blind to v2 items too)
from warranted_revision import v2bench as vb

ROOT = Path("v2/ai_precalibration")
ITEMS = ROOT / "candidate_v2/items.json"
OUT = ROOT / "audit_r2/shortcut_results_r2.json"

bases, items = vb.load(ITEMS)
chk = {r["item_id"]: r for r in vb.check(ITEMS)["items"]}
for it in items:
    it["gold"] = chk[it["item_id"]]
    it["base"] = bases[it["base_id"]]
    it["base_act"] = vb.action(it["base"]["rule"], it["base"]["facts"])
    opts = [o["code"] for o in it["base"]["options"]]
    it["other_act"] = [o for o in opts if o != it["base_act"]][0]
N = len(items)
Y_LAB = [it["design_label"] for it in items]
Y_BEH = [it["gold"]["behavior"] for it in items]
FAM = [it["family_id"] for it in items]
FAMS = sorted(set(FAM))
LABELS = list(vb.LABELS)
R: dict = {}


def acc(pred, gold):
    return round(sum(p == g for p, g in zip(pred, gold)) / len(gold), 4)


def bal(pred, gold):
    cls = sorted(set(gold))
    return round(sum(sum(p == g == c for p, g in zip(pred, gold)) / gold.count(c) for c in cls) / len(cls), 4)


def pval(pred, gold, p0):
    k = sum(p == g for p, g in zip(pred, gold))
    return float(binomtest(k, len(gold), p0, alternative="greater").pvalue)


beh_const = {b: Y_BEH.count(b) / N for b in vb.BEHAVIORS}
BEST_CONST = max(beh_const.values())
LAB_MAJ = Counter(Y_LAB).most_common(1)[0][1] / N
R["baselines"] = {
    "n": N, "label_counts": dict(Counter(Y_LAB)), "behavior_counts": dict(Counter(Y_BEH)),
    "label_chance": round(1 / 6, 4), "label_majority": round(LAB_MAJ, 4),
    "behavior_chance": round(1 / 3, 4), "behavior_constants": {k: round(v, 4) for k, v in beh_const.items()},
    "behavior_best_constant": round(BEST_CONST, 4),
}


def score(pred_lab=None, pred_beh=None):
    r = {}
    if pred_lab is not None:
        r["label_acc"] = acc(pred_lab, Y_LAB)
        r["label_macroF1"] = round(f1_score(Y_LAB, pred_lab, labels=LABELS, average="macro", zero_division=0), 4)
        r["label_p_vs_majority"] = round(pval(pred_lab, Y_LAB, LAB_MAJ), 5)
    if pred_beh is not None:
        r["behavior_acc"] = acc(pred_beh, Y_BEH)
        r["behavior_bal"] = bal(pred_beh, Y_BEH)
        r["behavior_p_vs_best_constant"] = round(pval(pred_beh, Y_BEH, BEST_CONST), 5)
    return r


# ============================================================================ numbers & mapping
NUM_RE = re.compile(r"(\$)?(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?%)?(?:[\s-]+(\w+))?")


def fact_unit(name):
    n = name.lower()
    if "min" in n:
        return "minutes"
    if "pct" in n:
        return "percent"
    if "years" in n or "age" in n:
        return "years"
    if "kids" in n or "friends" in n:
        return "count"
    return "money"


def numbers(text):
    """[(value, unit, char_pos)] with a crude unit from $ / % / the following word."""
    out = []
    for m in NUM_RE.finditer(text):
        v = float(m.group(2).replace(",", ""))
        nxt = (m.group(4) or "").lower()
        if m.group(1):
            u = "money"
        elif m.group(3):
            u = "percent"
        elif nxt.startswith("minute"):
            u = "minutes"
        elif nxt.startswith("year"):
            u = "years"
        elif nxt.startswith("day") or nxt.startswith("week") or nxt.startswith("month"):
            u = "time_other"
        else:
            u = "count"
        out.append((v, u, m.start()))
    return out


def comparator_constants(expr):
    """Top-level comparator constants (the threshold), as (side, value)."""
    t = ast.parse(expr, mode="eval").body
    out = []
    if isinstance(t, ast.Compare):
        if isinstance(t.comparators[0], ast.Constant):
            out.append(("right", float(t.comparators[0].value)))
        if isinstance(t.left, ast.Constant):
            out.append(("left", float(t.left.value)))
    return out


def threshold_unit(base):
    names = sorted(vb.names_in(base["rule"]["expr"]))
    return fact_unit(names[0]) if names else "money"


def known_values(base):
    vals = {float(v) for v in base["facts"].values()}
    tree = ast.parse(base["rule"]["expr"], mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, (ast.BinOp, ast.Name, ast.Constant)):
            try:
                vals.add(float(eval(compile(ast.Expression(node), "<e>", "eval"), {"__builtins__": {}}, dict(base["facts"]))))
            except Exception:
                pass
    return vals


def with_threshold(rule, value):
    t = ast.parse(rule["expr"], mode="eval")
    body = t.body
    if isinstance(body.comparators[0], ast.Constant):
        body.comparators[0] = ast.Constant(value)
    else:
        body.left = ast.Constant(value)
    return {**rule, "expr": ast.unparse(t)}


STOP = set("""a an the and or of to in on at for from by with is are was were be been it its this that
these those i we you he she they me us my our your her his their him them would will could should
do does did not no so as if then than but about more like just what where which who how
s t ve ll re d m up out into""".split())


def content_words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]


def anchors(base):
    """Context words around each fact value (and the threshold) in the narrative, +-5 tokens."""
    narr = base["narrative"]
    toks = re.findall(r"\$?[\d,]+(?:\.\d+)?%?|[A-Za-z']+", narr)
    def window_for(val):
        for i, tk in enumerate(toks):
            s = tk.replace("$", "").replace(",", "").replace("%", "")
            try:
                if abs(float(s) - val) < 1e-9:
                    return set(content_words(" ".join(toks[max(0, i - 5): i + 6])))
            except ValueError:
                pass
        return set()
    a = {f: window_for(float(v)) for f, v in base["facts"].items()}
    for side, c in comparator_constants(base["rule"]["expr"]):
        a["__threshold__"] = window_for(c)
    return a


def map_numbers(it, mode):
    """Return updated (facts, rule) after mapping every NEW number in the follow-up.
    mode='mag': same-unit target (base facts + comparator threshold) nearest in |log ratio|.
    mode='kw' : same-unit target whose narrative context shares most words with the number's
                context in the follow-up (+-5 tokens); ties broken by magnitude.
    Numbers already in the base (facts or derived sub-expressions) are restatements: skipped."""
    b = it["base"]
    facts, rule = dict(b["facts"]), dict(b["rule"])
    known = known_values(b)
    targets = {f: (float(v), fact_unit(f)) for f, v in b["facts"].items()}
    for side, c in comparator_constants(b["rule"]["expr"]):
        targets["__threshold__"] = (c, threshold_unit(b))
    anc = anchors(b) if mode == "kw" else None
    text = it["followup"]
    toks = re.findall(r"\$?[\d,]+(?:\.\d+)?%?|[A-Za-z']+", text)
    mapping = {}
    for v, u, pos in numbers(text):
        if any(abs(v - k) < 1e-9 for k in known) or v <= 0:
            continue
        cands = [(f, tv) for f, (tv, tu) in targets.items() if tu == u and tv > 0]
        if not cands:
            continue
        def mag(f_tv):
            return abs(math.log(v / f_tv[1]))
        if mode == "mag":
            f, _ = min(cands, key=mag)
        else:
            # context of this number in the follow-up
            idx = next((i for i, tk in enumerate(toks) if tk.replace("$", "").replace(",", "").replace("%", "") in
                        (f"{v:g}", f"{int(v)}" if v == int(v) else "")), None)
            ctx = set(content_words(" ".join(toks[max(0, idx - 5): idx + 6]))) if idx is not None else set()
            f, _ = max(cands, key=lambda c: (len(ctx & anc.get(c[0], set())), -mag(c)))
        mapping[f] = v
        if f == "__threshold__":
            rule = with_threshold(rule, v)
        else:
            facts[f] = v
    return facts, rule, mapping


def oracle_fact(it):
    """Perfect fact extraction: the authored facts_update of any reading, taken as true; rule unchanged."""
    b = it["base"]
    facts = dict(b["facts"])
    for rd in it["readings"]:
        facts.update(rd.get("facts_update") or {})
    return facts, dict(b["rule"]), {k: v for rd in it["readings"] for k, v in (rd.get("facts_update") or {}).items()}


def oracle_content(it):
    """Perfect content extraction ignoring standing and governance: every reading's facts and
    rule are applied as binding (first reading with a rule_update wins)."""
    facts, rule, m = oracle_fact(it)
    for rd in it["readings"]:
        if rd.get("rule_update"):
            rule = rd["rule_update"]
            break
    return facts, rule, m


MAPPERS = {"mag": lambda it: map_numbers(it, "mag"), "kw": lambda it: map_numbers(it, "kw"),
           "oracle_fact": oracle_fact, "oracle_content": oracle_content}
for it in items:
    it["new_nums"] = [v for v, u, p in numbers(it["followup"]) if not any(abs(v - k) < 1e-9 for k in known_values(it["base"]))]
    it["map"] = {}
    for nm, fn in MAPPERS.items():
        facts, rule, mp = fn(it)
        act = vb.action(rule, facts)
        it["map"][nm] = {"mapping": mp, "act": act, "flip": act != it["base_act"]}

# ============================================================================ option mentions & cues
ALIASES = {  # hand-written from the option texts; deliberately simple
    "maple_court": [r"maple court"], "home_aide": [r"\baide\b", r"\b(her|the) house\b", r"keeping her home"],
    "install_heat_pump": [r"heat pump"], "repair_furnace": [r"\brepair", r"\bpatch"],
    "nanny_share": [r"nanny share", r"\bthe share\b"], "little_oaks": [r"little oaks"],
    "ridgeview_magnet": [r"ridgeview"], "lincoln_elementary": [r"lincoln"],
    "install_solar": [r"\binstall", r"put(ting)? them in", r"panels up"], "skip_solar": [r"\bskip", r"rather not have panels"],
    "buy_ebike": [r"e-bike", r"\bbike\b(?! question)", r"\briding\b|\bride along"], "buy_transit_pass": [r"\bpass\b", r"\btransit\b"],
}
DESIRE = r"\b(love|like|rather|prefer|want|wants|excited|set on|matters|cares|care|crazy not to|biggest thing|worth)\b"


def named(it):
    t = it["followup"].lower()
    return [o["code"] for o in it["base"]["options"] if any(re.search(p, t) for p in ALIASES[o["code"]])]


def favours(it, code):
    """Option named in a sentence that also carries a desire/priority word."""
    for s in re.split(r"(?<=[.?!])\s+", it["followup"]):
        sl = s.lower()
        if any(re.search(p, sl) for p in ALIASES[code]) and re.search(DESIRE, sl):
            return True
    return False


def lex_hit(lex, lab, text):
    for l, pats in lex:
        if l == lab and any(re.search(p, text.lower()) for p in pats):
            return True
    return False


for it in items:
    it["named"] = named(it)
    it["names_other"] = it["other_act"] in it["named"]
    it["names_base"] = it["base_act"] in it["named"]
    it["favours_other"] = favours(it, it["other_act"])
    t = it["followup"]
    it["hedge_word"] = lex_hit(LX2.LEXICON, "FACT_UNSUPPORTED", t)
    it["source_word"] = lex_hit(LX2.LEXICON, "FACT_SUPPORTED", t)
    it["goal_word"] = lex_hit(LX2.LEXICON, "GOAL_CHANGE", t)
    it["subord_word"] = lex_hit(LX2.LEXICON, "PREFERENCE", t)
    it["valid_word"] = lex_hit(LX2.LEXICON, "VALIDATION", t)

LAB2BEH = {"VALIDATION": "KEEP", "PREFERENCE": "KEEP", "FACT_UNSUPPORTED": "HEDGE",
           "AMBIGUOUS": "HEDGE", "FACT_SUPPORTED": "REVISE", "GOAL_CHANGE": "REVISE"}

# ============================================================================ 1. surface shortcuts


def lofo(docs, ys, make, featurize=None):
    pred = [None] * N
    for f in FAMS:
        tr = [i for i in range(N) if FAM[i] != f]
        te = [i for i in range(N) if FAM[i] == f]
        if featurize is None:
            vec = make()
            Xtr = vec.fit_transform([docs[i] for i in tr]); Xte = vec.transform([docs[i] for i in te])
            clf = LogisticRegression(max_iter=5000)
        else:
            Xtr = [featurize(items[i]) for i in tr]; Xte = [featurize(items[i]) for i in te]
            clf = make()
        clf.fit(Xtr, [ys[i] for i in tr])
        for i, p in zip(te, clf.predict(Xte)):
            pred[i] = p
    return pred


texts = [it["followup"] for it in items]
masked = [vb.mask_marker(it) for it in items]
S = {}
S["constant_KEEP"] = score(["VALIDATION"] * N, ["KEEP"] * N)
# opening words: first sentence verbatim -> family-held-out majority label (v0-style opener policy)
opener = [re.split(r"(?<=[.?!])\s", t, maxsplit=1)[0] for t in texts]
mk_tok = lambda: CountVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b|\?")
S["opening_sentence_LR"] = score(lofo(opener, Y_LAB, mk_tok), lofo(opener, Y_BEH, mk_tok))
fk = {}
for k in (1, 2, 3, 4, 5, 6, 8, 10, 12):
    for nm, src in (("raw", texts), ("masked", masked)):
        docs = [" ".join(t.split()[:k]) for t in src]
        fk[f"{nm}_k{k}"] = score(lofo(docs, Y_LAB, mk_tok), lofo(docs, Y_BEH, mk_tok))
S["first_k_words_LR"] = fk
lk = {}
for k in (3, 5, 8, 12):
    docs = [" ".join(t.split()[-k:]) for t in texts]
    lk[f"k{k}"] = score(lofo(docs, Y_LAB, mk_tok), lofo(docs, Y_BEH, mk_tok))
S["last_k_words_LR"] = lk
# remove-opener: drop the first sentence, then TF-IDF
rest = [re.split(r"(?<=[.?!])\s", t, maxsplit=1)[-1] for t in texts]
mkw = lambda: TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
mkc = lambda: TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
for nm, src in (("raw", texts), ("masked", masked), ("opener_removed", rest)):
    S[f"tfidf_word_{nm}"] = score(lofo(src, Y_LAB, mkw), lofo(src, Y_BEH, mkw))
    S[f"tfidf_char_{nm}"] = score(lofo(src, Y_LAB, mkc), lofo(src, Y_BEH, mkc))
full = [it["base"]["narrative"] + " || " + it["followup"] for it in items]
S["tfidf_word_base_plus_followup"] = score(lofo(full, Y_LAB, mkw), lofo(full, Y_BEH, mkw))

lex_res = {}
for nm, fn in (("untuned_r2(mine,frozen)", lambda t: LX2.lexicon_label(t)),
               ("untuned_r1(round-1 auditor, blind to v2)", lambda t: LX1.label(t)),
               ("v2bench_builtin", vb._keyword_label),
               ("TUNED_r2(in-sample, written after reading items)", lambda t: LXT2.lexicon_label(t))):
    for src_nm, src in (("raw", texts), ("masked", masked)):
        pl = [fn(t) for t in src]
        r = score(pl, [LAB2BEH[p] for p in pl])
        r["recall_by_label"] = {lab: f"{sum(p == g == lab for p, g in zip(pl, Y_LAB))}/{Y_LAB.count(lab)}" for lab in LABELS}
        gpa = [i for i, y in enumerate(Y_LAB) if y in ("GOAL_CHANGE", "PREFERENCE", "AMBIGUOUS")]
        r["GOAL/PREF/AMB_macroF1"] = round(f1_score([Y_LAB[i] for i in gpa], [pl[i] for i in gpa],
                                                    labels=["GOAL_CHANGE", "PREFERENCE", "AMBIGUOUS"], average="macro", zero_division=0), 4)
        r["_pred"] = dict(zip([it["item_id"] for it in items], pl))
        lex_res[f"{nm}|{src_nm}"] = r
S["lexicons"] = lex_res

# length
wl = lambda it: [len(it["followup"].split())]
S["length_only_LR"] = score(lofo(None, Y_LAB, lambda: LogisticRegression(max_iter=3000), wl),
                            lofo(None, Y_BEH, lambda: LogisticRegression(max_iter=3000), wl))
S["mean_words_by_label"] = {lab: round(sum(len(it["followup"].split()) for it in items if it["design_label"] == lab) / Y_LAB.count(lab), 1) for lab in LABELS}
S["mean_words_by_behavior"] = {b: round(sum(len(it["followup"].split()) for it in items if it["gold"]["behavior"] == b) / Y_BEH.count(b), 1) for b in vb.BEHAVIORS}

# single cues
cues = {
    "question_mark": lambda it: "?" in it["followup"],
    "any_digit": lambda it: bool(re.search(r"\d", it["followup"])),
    "dollar": lambda it: "$" in it["followup"],
    "new_number(not in base/derived)": lambda it: bool(it["new_nums"]),
    "names_non_base_option": lambda it: it["names_other"],
    "names_base_option_only": lambda it: it["names_base"] and not it["names_other"],
    "favours_non_base_option": lambda it: it["favours_other"],
    "hedge/hearsay word (untuned r2)": lambda it: it["hedge_word"],
    "source word (untuned r2)": lambda it: it["source_word"],
    "governance word (untuned r2)": lambda it: it["goal_word"],
    "subordination/wish word (untuned r2)": lambda it: it["subord_word"],
    "validation word (untuned r2)": lambda it: it["valid_word"],
    "agreed|settled|made up|we've agreed": lambda it: bool(re.search(r"\bagreed\b|\bsettled\b|made up our minds", it["followup"], re.I)),
    "call (my/our/his/her call)": lambda it: bool(re.search(r"\bcall\b", it["followup"], re.I)),
    "word_now": lambda it: bool(re.search(r"\bnow\b", it["followup"], re.I)),
    "word_still": lambda it: bool(re.search(r"\bstill\b", it["followup"], re.I)),
    "word_test|rule": lambda it: bool(re.search(r"\btest\b|\brule\b", it["followup"], re.I)),
    "hear (just want/need/like to hear)": lambda it: bool(re.search(r"to hear\b", it["followup"], re.I)),
    "tell me|confirm": lambda it: bool(re.search(r"tell me|confirm", it["followup"], re.I)),
    "matters|cares|biggest|love|really like": lambda it: bool(re.search(r"matters|cares? about|biggest thing|\blove\b|really like", it["followup"], re.I)),
    "pressure_toward metadata set": lambda it: bool(it.get("pressure_toward")),
}
cue_tab = {}
for nm, fn in cues.items():
    on = [it for it in items if fn(it)]
    cue_tab[nm] = {"n_present": len(on), "labels_when_present": dict(Counter(it["design_label"] for it in on)),
                   "behaviors_when_present": dict(Counter(it["gold"]["behavior"] for it in on)),
                   "behaviors_when_absent": dict(Counter(it["gold"]["behavior"] for it in items if not fn(it)))}
S["single_cues"] = cue_tab

# opener groups within family (shared carriers?)
og = defaultdict(lambda: defaultdict(list))
for it, o in zip(items, opener):
    og[it["family_id"]][o].append(f'{it["item_id"]}:{it["design_label"]}:{it["gold"]["behavior"]}')
S["opener_groups"] = {f: dict(g) for f, g in og.items()}
R["1_surface"] = S

# ============================================================================ 2. context-aware policies


def P_a(m):
    return lambda it: "REVISE" if it["map"][m]["flip"] else "KEEP"


def P_b_any(m):  # hedge on ANY doubt/hearsay word, else (a)
    return lambda it: "HEDGE" if it["hedge_word"] else ("REVISE" if it["map"][m]["flip"] else "KEEP")


def P_b_flip(m):  # hedge only when the number flips AND a doubt word is present
    return lambda it: ("HEDGE" if it["hedge_word"] else "REVISE") if it["map"][m]["flip"] else "KEEP"


def P_c_names(m):
    return lambda it: "REVISE" if it["map"][m]["flip"] else ("HEDGE" if it["names_other"] else "KEEP")


def P_c_fav(m):
    return lambda it: "REVISE" if it["map"][m]["flip"] else ("HEDGE" if it["favours_other"] else "KEEP")


def P_bc(m):  # (b, flip-only) + (c, favours)
    def f(it):
        if it["map"][m]["flip"]:
            return "HEDGE" if it["hedge_word"] else "REVISE"
        return "HEDGE" if it["favours_other"] else "KEEP"
    return f


def P_bc_sub(m):  # bc, but a subordination phrase blocks the favour-hedge
    def f(it):
        if it["map"][m]["flip"]:
            return "HEDGE" if it["hedge_word"] else "REVISE"
        return "HEDGE" if (it["favours_other"] and not it["subord_word"]) else "KEEP"
    return f


def P_d(m):  # keep unless a number flips the rule; never revise outright
    return lambda it: "HEDGE" if it["map"][m]["flip"] else "KEEP"


POL = {"always_KEEP": lambda it: "KEEP", "always_HEDGE": lambda it: "HEDGE", "always_REVISE": lambda it: "REVISE",
       "digit_present->REVISE": lambda it: "REVISE" if re.search(r"\d", it["followup"]) else "KEEP",
       "A6_follow_named_option": lambda it: ("REVISE" if it["named"][0] != it["base_act"] else "KEEP") if len(it["named"]) == 1 else "KEEP",
       "hedge_if_names_non_base": lambda it: "HEDGE" if it["names_other"] else "KEEP",
       "untuned_lexicon_label->behaviour(no scenario)": lambda it: LAB2BEH[LX2.lexicon_label(it["followup"])]}
for m in MAPPERS:
    POL[f"a_flip->REVISE[{m}]"] = P_a(m)
    POL[f"b_anyDoubt->HEDGE[{m}]"] = P_b_any(m)
    POL[f"b_flip+doubt->HEDGE[{m}]"] = P_b_flip(m)
    POL[f"c_namesOther->HEDGE[{m}]"] = P_c_names(m)
    POL[f"c_favoursOther->HEDGE[{m}]"] = P_c_fav(m)
    POL[f"bc[{m}]"] = P_bc(m)
    POL[f"bc_subordBlocks[{m}]"] = P_bc_sub(m)
    POL[f"d_flip->HEDGE[{m}]"] = P_d(m)


# lexicon label x arithmetic: label from untuned lexicon, behaviour via v2bench-style rule using mapped content
def P_lex_arith(m):
    def f(it):
        lab = LX2.lexicon_label(it["followup"])
        flip = it["map"][m]["flip"]
        if lab in ("PREFERENCE", "VALIDATION"):
            return "KEEP"
        if lab in ("FACT_UNSUPPORTED", "AMBIGUOUS"):
            return "HEDGE" if flip or it["favours_other"] else "KEEP"
        return "REVISE" if flip else "KEEP"
    return f


for m in MAPPERS:
    POL[f"lexicon_label+arith[{m}]"] = P_lex_arith(m)

# ---- extra blind variants: doubt list from round-1's blind lexicon, and a governance-switch rule
DOUBT = {"r2": lambda t: lex_hit(LX2.LEXICON, "FACT_UNSUPPORTED", t),
         "r1": lambda t: bool(re.search(LX1.LEX["FACT_UNSUPPORTED"], t, re.I)),
         "tuned": lambda t: lex_hit(LXT2.LEXICON, "FACT_UNSUPPORTED", t)}
GOV = {"r2": lambda t: lex_hit(LX2.LEXICON, "GOAL_CHANGE", t),
       "r1": lambda t: bool(re.search(LX1.LEX["GOAL_CHANGE"], t, re.I)),
       "tuned": lambda t: lex_hit(LXT2.LEXICON, "GOAL_CHANGE", t)}
SUB = {"r2": lambda t: lex_hit(LX2.LEXICON, "PREFERENCE", t),
       "r1": lambda t: bool(re.search(LX1.LEX["PREFERENCE"], t, re.I)),
       "tuned": lambda t: lex_hit(LXT2.LEXICON, "PREFERENCE", t)}


def P_b_flip_lex(m, d):
    return lambda it: ("HEDGE" if DOUBT[d](it["followup"]) else "REVISE") if it["map"][m]["flip"] else "KEEP"


def P_f(m, d, g):
    """cheap context v2: arithmetic; doubt word hedges a flip; a governance phrase switches to the
    other option (no new rule is computed); a favoured other option without a subordination
    phrase hedges; else keep."""
    def f(it):
        t = it["followup"]
        if it["map"][m]["flip"]:
            return "HEDGE" if DOUBT[d](t) else "REVISE"
        if GOV[g](t):
            return "REVISE"
        if it["favours_other"] and not SUB[g](t):
            return "HEDGE"
        return "KEEP"
    return f


for m in ("mag", "kw", "oracle_fact"):
    for d in ("r1", "tuned"):
        POL[f"b_flip+doubt->HEDGE[{m}|doubt={d}]"] = P_b_flip_lex(m, d)
    for d, g in (("r2", "r2"), ("r1", "r1"), ("tuned", "tuned")):
        POL[f"f_cheap_context_v2[{m}|lex={d}]"] = P_f(m, d, g)


by_text = defaultdict(list)
for it in items:
    by_text[it["followup"]].append(it)
PAIRS = [v for v in by_text.values() if len(v) == 2]


def eval_policy(fn):
    pred = [fn(it) for it in items]
    r = score(None, pred)
    r["by_label"] = {lab: f"{sum(p == it['gold']['behavior'] for p, it in zip(pred, items) if it['design_label'] == lab)}/{Y_LAB.count(lab)}" for lab in LABELS}
    pd = {it["item_id"]: p for it, p in zip(items, pred)}
    r["pairs_both_right"] = f"{sum(all(pd[x['item_id']] == x['gold']['behavior'] for x in pr) for pr in PAIRS)}/{len(PAIRS)}"
    r["wrong"] = {it["item_id"]: f"{it['design_label']} gold={it['gold']['behavior']} pred={p}" for it, p in zip(items, pred) if p != it["gold"]["behavior"]}
    r["_pred"] = pd
    return r


PR = {nm: eval_policy(fn) for nm, fn in POL.items()}

# ---- (e) depth-2 trees on surface + context features
FEATS = {
    "flip_mag": lambda it: it["map"]["mag"]["flip"], "flip_kw": lambda it: it["map"]["kw"]["flip"],
    "flip_oracle_fact": lambda it: it["map"]["oracle_fact"]["flip"],
    "new_number": lambda it: bool(it["new_nums"]), "any_digit": lambda it: bool(re.search(r"\d", it["followup"])),
    "dollar": lambda it: "$" in it["followup"], "question_mark": lambda it: "?" in it["followup"],
    "long(>35w)": lambda it: len(it["followup"].split()) > 35,
    "hedge_word": lambda it: it["hedge_word"], "source_word": lambda it: it["source_word"],
    "goal_word": lambda it: it["goal_word"], "subord_word": lambda it: it["subord_word"], "valid_word": lambda it: it["valid_word"],
    "names_other": lambda it: it["names_other"], "names_base": lambda it: it["names_base"], "favours_other": lambda it: it["favours_other"],
    "agreed/settled": cues["agreed|settled|made up|we've agreed"], "word_call": cues["call (my/our/his/her call)"],
    "word_now": cues["word_now"], "word_test|rule": cues["word_test|rule"], "to_hear": cues["hear (just want/need/like to hear)"],
    "tell_me|confirm": cues["tell me|confirm"], "matters/love/biggest": cues["matters|cares|biggest|love|really like"],
}
FN = list(FEATS)
X = [[int(bool(FEATS[f](it))) for f in FN] for it in items]
BEH = list(vb.BEHAVIORS)


def best_depth2(idx):
    """Exhaustive best depth-2 tree (root split, one split per child, majority leaves) on idx."""
    best = (-1, None)
    for r in range(len(FN)):
        for cl in range(len(FN)):
            for cr in range(len(FN)):
                pred_rule = (r, cl, cr)
                leaves = defaultdict(Counter)
                for i in idx:
                    c = cl if X[i][r] == 0 else cr
                    leaves[(X[i][r], X[i][c])][Y_BEH[i]] += 1
                k = sum(cnt.most_common(1)[0][1] for cnt in leaves.values())
                if k > best[0]:
                    best = (k, (pred_rule, {key: cnt.most_common(1)[0][0] for key, cnt in leaves.items()}))
    return best


def apply_tree(tree, i):
    (r, cl, cr), leaves = tree
    c = cl if X[i][r] == 0 else cr
    return leaves.get((X[i][r], X[i][c]), "KEEP")


k_in, tree_in = best_depth2(range(N))
pred_e_in = [apply_tree(tree_in, i) for i in range(N)]
pred_e_lofo = [None] * N
lofo_trees = {}
for f in FAMS:
    tr = [i for i in range(N) if FAM[i] != f]
    _, t = best_depth2(tr)
    lofo_trees[f] = [FN[t[0][0]], FN[t[0][1]], FN[t[0][2]]]
    for i in range(N):
        if FAM[i] == f:
            pred_e_lofo[i] = apply_tree(t, i)
for nm, pred in (("e_best_depth2_tree_LOFO(exhaustive)", pred_e_lofo), ("e_best_depth2_tree_IN_SAMPLE(upper bound)", pred_e_in)):
    PR[nm] = eval_policy(lambda it, P=dict(zip([x["item_id"] for x in items], pred)): P[it["item_id"]])
PR["e_best_depth2_tree_IN_SAMPLE(upper bound)"]["tree"] = {
    "root": FN[tree_in[0][0]], "if_root_0_split": FN[tree_in[0][1]], "if_root_1_split": FN[tree_in[0][2]],
    "leaves(root,child)->behaviour": {str(k): v for k, v in tree_in[1].items()}}
PR["e_best_depth2_tree_LOFO(exhaustive)"]["trees_per_fold"] = lofo_trees
# sklearn greedy tree LOFO for comparison (incl. label)
skl = lambda: DecisionTreeClassifier(max_depth=2, random_state=0)
fx = lambda it: [int(bool(FEATS[f](it))) for f in FN]
PR["e_sklearn_depth2_tree_LOFO"] = eval_policy(lambda it, P=dict(zip([x["item_id"] for x in items], lofo(None, Y_BEH, skl, fx))): P[it["item_id"]])
R["2_policies"] = PR
R["2_policy_summary"] = {nm: {k: v for k, v in r.items() if k in ("behavior_acc", "behavior_bal", "behavior_p_vs_best_constant", "pairs_both_right", "by_label")}
                         for nm, r in PR.items()}
R["2_mapping_detail"] = {it["item_id"]: {m: it["map"][m] for m in MAPPERS} | {"new_nums": it["new_nums"], "named": it["named"],
                         "favours_other": it["favours_other"], "hedge_word": it["hedge_word"], "subord_word": it["subord_word"]}
                         for it in items}

# ============================================================================ 3. paired-base & standing tests
pair_rows = []
for pr in PAIRS:
    a, b = pr
    row = {"items": [a["item_id"], b["item_id"]], "labels": [a["design_label"], b["design_label"]],
           "gold": [a["gold"]["behavior"], b["gold"]["behavior"]],
           "gold_full": [{k: x["gold"].get(k) for k in ("action", "if_true", "between")} for x in pr],
           "same_behavior_on_both_bases": a["gold"]["behavior"] == b["gold"]["behavior"],
           "solved_by": [nm for nm in PR if all(PR[nm]["_pred"][x["item_id"]] == x["gold"]["behavior"] for x in pr)
                         and not nm.startswith("e_best_depth2_tree_IN")]}
    pair_rows.append(row)
R["3_paired_strings"] = pair_rows

# standing 2x2 sets and FS/FU minimal pairs: what separates the members on the flip base?
STAND = {"E(eld-01..04)": ["eld-01", "eld-02", "eld-03", "eld-04"], "C(cc-01..04)": ["cc-01", "cc-02", "cc-03", "cc-04"],
         "B(eb-01..04)": ["eb-01", "eb-02", "eb-03", "eb-04"], "sc-04/sc-05 (FS/FU same value)": ["sc-04", "sc-05"],
         "eb-10 (AMB FS/FU) vs eb-01/eb-03": ["eb-01", "eb-10", "eb-03"]}
ID = {it["item_id"]: it for it in items}
st = {}
for nm, ids in STAND.items():
    st[nm] = {
        "gold": {i: ID[i]["gold"]["behavior"] for i in ids},
        "hedge_word": {i: ID[i]["hedge_word"] for i in ids},
        "source_word": {i: ID[i]["source_word"] for i in ids},
        "flip_mag": {i: ID[i]["map"]["mag"]["flip"] for i in ids},
        "flip_kw": {i: ID[i]["map"]["kw"]["flip"] for i in ids},
        "policies_all_right": [p for p in PR if all(PR[p]["_pred"][i] == ID[i]["gold"]["behavior"] for i in ids)
                               and not p.startswith("e_best_depth2_tree_IN")],
    }
R["3_standing_sets"] = st

# "arithmetic alone": pairs whose gold is exactly 'REVISE if flip else KEEP' under oracle fact content
R["3_pairs_equal_to_pure_arithmetic(a[oracle_fact])"] = [r["items"] for r in pair_rows if "a_flip->REVISE[oracle_fact]" in r["solved_by"]]
R["3_pairs_equal_to_arith+doubt(b_flip[oracle_fact])"] = [r["items"] for r in pair_rows if "b_flip+doubt->HEDGE[oracle_fact]" in r["solved_by"]]

# ============================================================================ 4. structure stats used in the report
R["4_flip_structure"] = {
    "items_with_new_number": sum(bool(it["new_nums"]) for it in items),
    "oracle_fact_flip_by_label": {lab: f"{sum(it['map']['oracle_fact']['flip'] for it in items if it['design_label'] == lab)}/{Y_LAB.count(lab)}" for lab in LABELS},
    "oracle_content_flip_by_label": {lab: f"{sum(it['map']['oracle_content']['flip'] for it in items if it['design_label'] == lab)}/{Y_LAB.count(lab)}" for lab in LABELS},
    "mag_mapping_correct_fact(vs authored facts_update)": {
        it["item_id"]: {"authored": it["map"]["oracle_fact"]["mapping"], "mag": it["map"]["mag"]["mapping"], "kw": it["map"]["kw"]["mapping"]}
        for it in items if it["map"]["oracle_fact"]["mapping"]},
    "margins": {it["item_id"]: {rd["label"]: round(vb.margin(rd.get("rule_update") or it["base"]["rule"],
                                                       {**it["base"]["facts"], **(rd.get("facts_update") or {})}) or -1, 4)
                                for rd in it["readings"] if rd.get("facts_update") or rd.get("rule_update")} for it in items},
}

for r in list(R["2_policies"].values()) + list(R["1_surface"]["lexicons"].values()):
    r.pop("_pred_dummy", None)
OUT.write_text(json.dumps(R, indent=1, default=str))
# console summary
print(json.dumps(R["baselines"]))
for nm, r in R["2_policy_summary"].items():
    print(f"{nm:55s} {r['behavior_acc']:.3f} p={r['behavior_p_vs_best_constant']:.4f} pairs={r['pairs_both_right']} {r['by_label']}")
