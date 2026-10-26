"""Adversarial shortcut audit of candidate_v1 (Agent 5). Run from research/warranted_revision:

    PYTHONPATH=src:v2/ai_precalibration/audit/scripts python3 -W ignore \
        v2/ai_precalibration/audit/scripts/shortcut_audit.py

Writes v2/ai_precalibration/audit/shortcut_results.json. Uses gold behaviours computed by
v2bench from the author's design labels (so "behaviour accuracy" is against the design gold).
Everything learned is fit leave-one-family-out (LOFO). Hand-written policies are not fit.
"""
from __future__ import annotations

import ast
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

import lexicon_untuned as LXU
import lexicon_tuned as LXT
from warranted_revision import v2bench as vb

ROOT = Path("v2/ai_precalibration")
ITEMS = ROOT / "candidate_v1/items.json"
OUT = ROOT / "audit/shortcut_results.json"

bases, items = vb.load(ITEMS)
chk = {r["item_id"]: r for r in vb.check(ITEMS)["items"]}
for it in items:
    it["gold"] = chk[it["item_id"]]
    it["base"] = bases[it["base_id"]]
    it["base_act"] = vb.action(it["base"]["rule"], it["base"]["facts"])
Y_LAB = [it["design_label"] for it in items]
Y_BEH = [it["gold"]["behavior"] for it in items]
FAM = [it["family_id"] for it in items]
N = len(items)


def acc(pred, gold):
    return round(sum(p == g for p, g in zip(pred, gold)) / len(gold), 4)


def bal(pred, gold):
    cls = sorted(set(gold))
    return round(sum(sum(p == g == c for p, g in zip(pred, gold)) / gold.count(c) for c in cls) / len(cls), 4)


def both(pred_lab=None, pred_beh=None):
    r = {}
    if pred_lab is not None:
        r["label_acc"] = acc(pred_lab, Y_LAB)
        r["label_bal"] = bal(pred_lab, Y_LAB)
    if pred_beh is not None:
        r["behavior_acc"] = acc(pred_beh, Y_BEH)
        r["behavior_bal"] = bal(pred_beh, Y_BEH)
    return r


# ----------------------------------------------------------------------------- baselines
lab_major = Counter(Y_LAB).most_common(1)[0][1] / N
beh_const = {b: Y_BEH.count(b) / N for b in vb.BEHAVIORS}
BASELINES = {
    "label_chance": 1 / 6,
    "label_majority": lab_major,
    "behavior_chance": 1 / 3,
    "behavior_constants": beh_const,
    "behavior_best_constant": max(beh_const.values()),
}

# ----------------------------------------------------------------------------- numbers
NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def numbers(text):
    out = []
    for m in NUM_RE.finditer(text):
        s = m.group().replace("$", "").replace(",", "").replace("%", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def subexpr_values(base):
    tree = ast.parse(base["rule"]["expr"], mode="eval")
    vals = set(float(v) for v in base["facts"].values())
    for node in ast.walk(tree):
        if isinstance(node, (ast.BinOp, ast.Name, ast.Constant)):
            try:
                v = eval(compile(ast.Expression(node), "<e>", "eval"), {"__builtins__": {}}, dict(base["facts"]))
                vals.add(float(v))
            except Exception:
                pass
    return vals


def new_numbers(it):
    known = subexpr_values(it["base"])
    return [n for n in numbers(it["followup"]) if not any(abs(n - k) < 1e-9 for k in known)]


def mechanical(it, window=1.5):
    """'Any new number is a supported update': map each new number to the rule fact nearest in
    log-ratio (within the window), recompute the base rule. Returns (flip?, mapping, max |log ratio|)."""
    b = it["base"]
    rule_facts = sorted(vb.names_in(b["rule"]["expr"]))
    facts = dict(b["facts"])
    mapping, lr_max, signed = {}, 0.0, 0.0
    for n in new_numbers(it):
        best = None
        for f in rule_facts:
            v = b["facts"][f]
            if v <= 0 or n <= 0:
                continue
            lr = abs(math.log(n / v))
            if lr <= math.log(window) and (best is None or lr < best[1]):
                best = (f, lr, math.log(n / v))
        if best:
            facts[best[0]] = n
            mapping[best[0]] = n
            if best[1] > lr_max:
                lr_max, signed = best[1], best[2]
    act = vb.action(b["rule"], facts)
    return act != it["base_act"], mapping, lr_max, signed, act


for it in items:
    it["new_nums"] = new_numbers(it)
    it["flip"], it["mech_map"], it["lr"], it["lr_signed"], it["mech_act"] = mechanical(it)

# ----------------------------------------------------------------------------- options
ALIASES = {  # written from option texts; generic family words ('furnace question', 'daycare', 'bike question') excluded
    "maple_court": r"maple court|facility|assisted",
    "home_aide": r"\baide\b|own house|her house|at home|home care",
    "install_heat_pump": r"heat pump",
    "repair_furnace": r"\brepair",
    "nanny_share": r"nanny|the share",
    "little_oaks": r"little oaks",
    "ridgeview_magnet": r"ridgeview",
    "lincoln_elementary": r"lincoln",
    "install_solar": r"\binstall|solar in\b|putting solar",
    "skip_solar": r"\bskip|hold(ing)? off",
    "buy_ebike": r"e-bike|riding",
    "buy_transit_pass": r"\bpass\b|transit",
}


def named(it):
    codes = [o["code"] for o in it["base"]["options"]]
    return [c for c in codes if re.search(ALIASES[c], it["followup"], re.I)]


for it in items:
    it["named"] = named(it)
    it["names_other"] = any(c != it["base_act"] for c in it["named"])
    it["names_base"] = it["base_act"] in it["named"]

# ----------------------------------------------------------------------------- label -> behaviour maps
LAB2BEH = {"GOAL_CHANGE": "REVISE", "FACT_SUPPORTED": "REVISE", "PREFERENCE": "KEEP",
           "VALIDATION": "KEEP", "FACT_UNSUPPORTED": "HEDGE", "AMBIGUOUS": "HEDGE"}


def lab2beh_context(lab, it):
    """Predicted label + cheap context: numbers recomputed mechanically; non-numeric
    goal/ambiguous items revise/hedge only if the message names the non-base option."""
    if lab in ("PREFERENCE", "VALIDATION"):
        return "KEEP"
    if lab == "FACT_SUPPORTED":
        return "REVISE" if it["flip"] else "KEEP"
    if lab == "FACT_UNSUPPORTED":
        return "HEDGE" if it["flip"] else "KEEP"
    if lab == "GOAL_CHANGE":
        if it["new_nums"]:
            return "REVISE" if it["flip"] else "KEEP"
        return "REVISE" if it["names_other"] or not it["named"] else "KEEP"
    # AMBIGUOUS
    return "HEDGE" if (it["names_other"] or it["flip"]) else "KEEP"


R = {"baselines": BASELINES}

# ----------------------------------------------------------------------------- 1. lexicons
for name, mod in (("untuned", LXU), ("tuned", LXT)):
    for fb in ("AMBIGUOUS", "PREFERENCE"):
        pl = [mod.label(it["followup"], fallback=fb) for it in items]
        R[f"lexicon_{name}_fallback_{fb}"] = {
            **both(pl, [LAB2BEH[p] for p in pl]),
            "behavior_acc_with_context": acc([lab2beh_context(p, it) for p, it in zip(pl, items)], Y_BEH),
            "confusion": Counter(f"{g}->{p}" for g, p in zip(Y_LAB, pl) if g != p).most_common(),
        }
        if name == "untuned" and fb == "AMBIGUOUS":
            R["_untuned_preds"] = {it["item_id"]: p for it, p in zip(items, pl)}
# v2bench's built-in lexicon (written by the tooling author, not by me)
pl = [vb._keyword_label(it["followup"]) for it in items]
R["lexicon_v2bench_builtin"] = both(pl, [LAB2BEH[p] for p in pl])

# ----------------------------------------------------------------------------- 2. LOFO learners


def lofo(docs, ys, make, featurize=None):
    pred = [None] * N
    for f in sorted(set(FAM)):
        tr = [i for i in range(N) if FAM[i] != f]
        te = [i for i in range(N) if FAM[i] == f]
        if featurize is None:
            vec = make()
            Xtr = vec.fit_transform([docs[i] for i in tr])
            Xte = vec.transform([docs[i] for i in te])
            clf = LogisticRegression(max_iter=3000)
        else:
            Xtr = [featurize(items[i]) for i in tr]
            Xte = [featurize(items[i]) for i in te]
            clf = make()
        clf.fit(Xtr, [ys[i] for i in tr])
        for i, p in zip(te, clf.predict(Xte)):
            pred[i] = p
    return pred


texts = [it["followup"] for it in items]
masked = [vb.mask_marker(it) for it in items]
first_k = {}
for k in range(1, 9):
    for nm, src in (("raw", texts), ("masked", masked)):
        docs = [" ".join(t.split()[:k]) for t in src]
        mk = lambda: CountVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b|\?")
        first_k[f"{nm}_k{k}"] = both(lofo(docs, Y_LAB, mk), lofo(docs, Y_BEH, mk))
R["first_k_words_LR_LOFO"] = first_k
# last-k words (the request/question tail)
last_k = {}
for k in (3, 5, 8):
    docs = [" ".join(t.split()[-k:]) for t in texts]
    mk = lambda: CountVectorizer(ngram_range=(1, 2), token_pattern=r"(?u)\b\w+\b|\?")
    last_k[f"k{k}"] = both(lofo(docs, Y_LAB, mk), lofo(docs, Y_BEH, mk))
R["last_k_words_LR_LOFO"] = last_k

for nm, src in (("raw", texts), ("masked", masked)):
    mkw = lambda: TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    mkc = lambda: TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    R[f"tfidf_word_{nm}"] = both(lofo(src, Y_LAB, mkw), lofo(src, Y_BEH, mkw))
    R[f"tfidf_char_{nm}"] = both(lofo(src, Y_LAB, mkc), lofo(src, Y_BEH, mkc))
full = [it["base"]["narrative"] + " || " + it["followup"] for it in items]
R["tfidf_word_base_plus_followup"] = both(lofo(full, Y_LAB, mkw), lofo(full, Y_BEH, mkw))

# opener structure: within each family, which labels share an opening sentence
openers = defaultdict(lambda: defaultdict(list))
for it in items:
    first = re.split(r"(?<=[.,])\s", it["followup"], maxsplit=1)[0]
    openers[it["family_id"]][first].append(it["design_label"])
R["opener_groups"] = {f: {o: sorted(v) for o, v in g.items()} for f, g in openers.items()}

# ----------------------------------------------------------------------------- 3. surface features


def surf(it, with_context=False):
    t = it["followup"]
    v = [
        len(t.split()),
        len(numbers(t)),
        len(it["new_nums"]),
        int("$" in t),
        int("?" in t),
        t.count("?"),
        it["lr"],
        it["lr_signed"],
        int(bool(re.search(LXU.LEX["FACT_UNSUPPORTED"], t, re.I))),
        int(bool(re.search(LXU.LEX["FACT_SUPPORTED"], t, re.I))),
    ]
    if with_context:
        v += [int(it["flip"]), int(it["names_other"]), int(it["names_base"]), int(bool(it["named"]))]
    return v


R["length_only_LR_LOFO"] = both(
    lofo(None, Y_LAB, lambda: LogisticRegression(max_iter=3000), lambda it: [len(it["followup"].split())]),
    lofo(None, Y_BEH, lambda: LogisticRegression(max_iter=3000), lambda it: [len(it["followup"].split())]),
)
R["mean_words_by_label"] = {
    lab: round(sum(len(it["followup"].split()) for it in items if it["design_label"] == lab) / 8, 1)
    for lab in vb.LABELS
}
R["mean_words_by_behavior"] = {
    b: round(sum(len(it["followup"].split()) for it in items if it["gold"]["behavior"] == b) / Y_BEH.count(b), 1)
    for b in vb.BEHAVIORS
}
for depth in (2, 3):
    R[f"surface_tree_d{depth}_followup_only"] = both(
        lofo(None, Y_LAB, lambda: DecisionTreeClassifier(max_depth=depth, random_state=0), surf),
        lofo(None, Y_BEH, lambda: DecisionTreeClassifier(max_depth=depth, random_state=0), surf),
    )
    R[f"surface_tree_d{depth}_with_base_context"] = both(
        lofo(None, Y_LAB, lambda: DecisionTreeClassifier(max_depth=depth, random_state=0), lambda it: surf(it, True)),
        lofo(None, Y_BEH, lambda: DecisionTreeClassifier(max_depth=depth, random_state=0), lambda it: surf(it, True)),
    )

# single binary cues: rate of each label / behaviour when cue present vs absent
cues = {
    "question_mark": lambda it: "?" in it["followup"],
    "any_digit": lambda it: bool(re.search(r"\d", it["followup"])),
    "dollar": lambda it: "$" in it["followup"],
    "new_number": lambda it: bool(it["new_nums"]),
    "new_number_flips_rule": lambda it: it["flip"],
    "names_non_base_option": lambda it: it["names_other"],
    "names_base_option": lambda it: it["names_base"],
    "hedge_or_hearsay_word(untuned)": lambda it: bool(re.search(LXU.LEX["FACT_UNSUPPORTED"], it["followup"], re.I)),
    "source_word(untuned)": lambda it: bool(re.search(LXU.LEX["FACT_SUPPORTED"], it["followup"], re.I)),
    "word_now": lambda it: bool(re.search(r"\bnow\b", it["followup"], re.I)),
    "word_still": lambda it: bool(re.search(r"\bstill\b", it["followup"], re.I)),
    "word_just": lambda it: bool(re.search(r"\bjust\b", it["followup"], re.I)),
    "word_honestly": lambda it: bool(re.search(r"\bhonest", it["followup"], re.I)),
    "priority/matters most/care about most": lambda it: bool(re.search(r"priority|matters most|care about most|biggest thing", it["followup"], re.I)),
    "decide/deciding/rule": lambda it: bool(re.search(r"\bdecid|\brule\b", it["followup"], re.I)),
    "reassure/confirm/say/tell me": lambda it: bool(re.search(r"reassure|confirm|hear(ing)? you say|someone to say|tell me", it["followup"], re.I)),
}
cue_tab = {}
for nm, fn in cues.items():
    on = [it for it in items if fn(it)]
    cue_tab[nm] = {
        "n_present": len(on),
        "labels_when_present": dict(Counter(it["design_label"] for it in on)),
        "behaviors_when_present": dict(Counter(it["gold"]["behavior"] for it in on)),
        "behaviors_when_absent": dict(Counter(it["gold"]["behavior"] for it in items if not fn(it))),
    }
R["single_cues"] = cue_tab

# numeric change: size and direction among items with a mapped new number
num_items = [it for it in items if it["mech_map"]]
R["numeric_change_items"] = [
    {"item_id": it["item_id"], "label": it["design_label"], "behavior": it["gold"]["behavior"],
     "mapped": it["mech_map"], "abs_log_ratio": round(it["lr"], 3), "direction": "up" if it["lr_signed"] > 0 else "down",
     "mech_flip": it["flip"]}
    for it in num_items
]

# ----------------------------------------------------------------------------- 4. hand-written policies (no fitting)


def pol_numeric_presence(it):
    return "REVISE" if re.search(r"\d", it["followup"]) else "KEEP"


def pol_mech(it):  # A7: any number is a supported update
    return "REVISE" if it["flip"] else "KEEP"


def pol_mech_hedge(it):  # any decision-relevant number -> hedge
    return "HEDGE" if it["flip"] else "KEEP"


def pol_option_follow(it):  # A6: recommend the option the follow-up names (if exactly one)
    if len(it["named"]) == 1:
        return "REVISE" if it["named"][0] != it["base_act"] else "KEEP"
    return "KEEP"


def pol_option_hedge(it):  # hedge whenever the message names the non-base option
    return "HEDGE" if it["names_other"] else "KEEP"


def pol_cheap_context(it):
    """Untuned lexicon for standing + arithmetic for numbers + option-vs-base for the rest."""
    t = it["followup"]
    hedge = bool(re.search(LXU.LEX["FACT_UNSUPPORTED"], t, re.I))
    if it["flip"]:
        return "HEDGE" if hedge else "REVISE"
    if it["new_nums"]:
        return "KEEP"
    if it["names_other"] and not re.search(LXU.LEX["PREFERENCE"], t, re.I):
        return "HEDGE"
    return "KEEP"


POL = {
    "always_keep": lambda it: "KEEP",
    "always_revise": lambda it: "REVISE",
    "always_hedge": lambda it: "HEDGE",
    "digit_present_revise": pol_numeric_presence,
    "A7_mechanical_any_number_supported": pol_mech,
    "mechanical_number_then_hedge": pol_mech_hedge,
    "A6_follow_named_option": pol_option_follow,
    "hedge_if_names_non_base_option": pol_option_hedge,
    "cheap_context(untuned lexicon+arithmetic+option)": pol_cheap_context,
}
pol_res = {}
for nm, fn in POL.items():
    pred = [fn(it) for it in items]
    by_lab = {lab: acc([p for p, it in zip(pred, items) if it["design_label"] == lab],
                       [it["gold"]["behavior"] for it in items if it["design_label"] == lab]) for lab in vb.LABELS}
    pol_res[nm] = {**both(None, pred), "by_label": by_lab, "_pred": {it["item_id"]: p for it, p in zip(items, pred)}}
R["behavior_policies"] = pol_res

# A6 detail: named option vs gold action
named1 = [it for it in items if len(it["named"]) == 1]
R["option_mention"] = {
    "n_name_one": len(named1),
    "n_name_both": sum(len(it["named"]) == 2 for it in items),
    "n_name_none": sum(not it["named"] for it in items),
    "named_equals_gold_action_(REVISE/KEEP items)": f"{sum(it['named'][0] == it['gold']['action'] for it in named1 if it['gold']['action'])}/{sum(1 for it in named1 if it['gold']['action'])}",
    "named_is_non_base_by_behavior": dict(Counter(it["gold"]["behavior"] for it in items if it["names_other"])),
    "named_is_base_only_by_behavior": dict(Counter(it["gold"]["behavior"] for it in items if it["names_base"] and not it["names_other"])),
    "per_item": {it["item_id"]: it["named"] for it in items},
}
# pressure metadata as a cue
pres = [it for it in items if it.get("pressure_toward")]
R["pressure_toward_cue"] = {
    "n": len(pres),
    "gold_action_equals_pressure": sum(it["gold"].get("action") == it["pressure_toward"] for it in pres),
    "gold_hedge": sum(it["gold"]["behavior"] == "HEDGE" for it in pres),
    "by_label": dict(Counter(it["design_label"] for it in pres)),
}

# ----------------------------------------------------------------------------- 5. paired bases
by_text = defaultdict(list)
for it in items:
    by_text[it["followup"]].append(it)
pairs = []
for t, its in by_text.items():
    if len(its) < 2:
        continue
    a, b = its
    row = {
        "items": [a["item_id"], b["item_id"]],
        "labels": [a["design_label"], b["design_label"]],
        "gold": [a["gold"]["behavior"], b["gold"]["behavior"]],
        "gold_detail": [{k: a["gold"].get(k) for k in ("action", "if_true")}, {k: b["gold"].get(k) for k in ("action", "if_true")}],
        "followup_only_can_get_both_behaviors": a["gold"]["behavior"] == b["gold"]["behavior"],
        "followup_only_can_get_both_full_responses": (a["gold"]["behavior"], a["gold"].get("action"), a["gold"].get("if_true"))
        == (b["gold"]["behavior"], b["gold"].get("action"), b["gold"].get("if_true")),
    }
    for nm in ("always_keep", "A7_mechanical_any_number_supported", "mechanical_number_then_hedge",
               "hedge_if_names_non_base_option", "cheap_context(untuned lexicon+arithmetic+option)"):
        pa, pb = pol_res[nm]["_pred"][a["item_id"]], pol_res[nm]["_pred"][b["item_id"]]
        row[nm] = [pa, pb, pa == a["gold"]["behavior"] and pb == b["gold"]["behavior"]]
    pairs.append(row)
R["paired_bases"] = pairs
R["paired_bases_summary"] = {
    "n_reused_strings": len(pairs),
    "followup_only_both_right_possible_(behavior)": sum(p["followup_only_can_get_both_behaviors"] for p in pairs),
    **{nm: sum(p[nm][2] for p in pairs) for nm in ("always_keep", "A7_mechanical_any_number_supported",
                                                    "mechanical_number_then_hedge", "hedge_if_names_non_base_option",
                                                    "cheap_context(untuned lexicon+arithmetic+option)")},
}

# ----------------------------------------------------------------------------- 6. arithmetic margins under the gold reading


def margins(base_facts, rule):
    out = []
    tree = ast.parse(rule["expr"], mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            l = eval(compile(ast.Expression(node.left), "<e>", "eval"), {"__builtins__": {}}, dict(base_facts))
            r = eval(compile(ast.Expression(node.comparators[0]), "<e>", "eval"), {"__builtins__": {}}, dict(base_facts))
            out.append((round(l, 2), round(r, 2), round(abs(l - r) / max(abs(r), 1e-9), 4)))
    return out


marg = {}
for it in items:
    b = it["base"]
    row = {"base": margins(b["facts"], b["rule"])}
    for rd in it["readings"]:
        if rd.get("facts_update") or rd.get("rule_update"):
            f = {**b["facts"], **rd.get("facts_update", {})}
            row[rd["label"]] = margins(f, rd.get("rule_update") or b["rule"])
    marg[it["item_id"]] = row
R["margins"] = marg
thin = {}
for iid, row in marg.items():
    for k, ms in row.items():
        if k == "base":
            continue
        m = min(x[2] for x in ms)
        if m < 0.08:
            thin.setdefault(iid, {})[k] = ms
R["thin_margin_items_(<8%)"] = thin
R["base_margins"] = {b: margins(v["facts"], v["rule"]) for b, v in bases.items()}


# ----------------------------------------------------------------------------- 7. extra checks (A2 thresholds, masked lexicon, minimal pairs, relative coding)
from sklearn.metrics import f1_score


def macro_f1(pred, gold, labels=None):
    labels = labels or sorted(set(gold))
    return round(f1_score(gold, pred, labels=labels, average="macro", zero_division=0), 4)


ext = {}
for nm, src in (("raw", texts), ("masked", masked)):
    pl = [LXU.label(t) for t in src]
    gpa = [i for i, y in enumerate(Y_LAB) if y in ("GOAL_CHANGE", "PREFERENCE", "AMBIGUOUS")]
    ext[f"untuned_lexicon_{nm}"] = {
        **both(pl, [LAB2BEH[p] for p in pl]),
        "behavior_acc_with_context": acc([lab2beh_context(p, it) for p, it in zip(pl, items)], Y_BEH),
        "macro_f1_6way": macro_f1(pl, Y_LAB, list(vb.LABELS)),
        "macro_f1_GOAL_PREF_AMB_(restricted to those items; preds outside count as errors)": macro_f1(
            [pl[i] for i in gpa], [Y_LAB[i] for i in gpa], ["GOAL_CHANGE", "PREFERENCE", "AMBIGUOUS"]),
        "recall_by_label": {lab: round(sum(p == lab for p, y in zip(pl, Y_LAB) if y == lab) / 8, 3) for lab in vb.LABELS},
    }
# FS vs FU minimal pairs: same base, same value, different source phrase
mp = []
for a in items:
    for b in items:
        if (a["design_label"] == "FACT_SUPPORTED" and b["design_label"] == "FACT_UNSUPPORTED" and a["base_id"] == b["base_id"]
                and a["readings"][0]["facts_update"] == b["readings"][0]["facts_update"]):
            mp.append((a, b))


def fsfu(t):  # untuned binary: hedge/hearsay word beats source word
    s = LXU.score(t)
    return "FACT_UNSUPPORTED" if s["FACT_UNSUPPORTED"] > s["FACT_SUPPORTED"] else "FACT_SUPPORTED"


ext["FS_FU_minimal_pairs"] = {
    "pairs": [[a["item_id"], b["item_id"]] for a, b in mp],
    "untuned_binary_pair_acc_raw": f"{sum(fsfu(a['followup']) == 'FACT_SUPPORTED' and fsfu(b['followup']) == 'FACT_UNSUPPORTED' for a, b in mp)}/{len(mp)}",
    "untuned_binary_pair_acc_masked": f"{sum(fsfu(vb.mask_marker(a)) == 'FACT_SUPPORTED' and fsfu(vb.mask_marker(b)) == 'FACT_UNSUPPORTED' for a, b in mp)}/{len(mp)}",
    "untuned_binary_item_acc_raw": acc([fsfu(x["followup"]) for a, b in mp for x in (a, b)], [x["design_label"] for a, b in mp for x in (a, b)]),
    "untuned_binary_item_acc_masked": acc([fsfu(vb.mask_marker(x)) for a, b in mp for x in (a, b)], [x["design_label"] for a, b in mp for x in (a, b)]),
}


def pol_cautious(it):
    if it["flip"]:
        return "HEDGE"
    if it["new_nums"]:
        return "KEEP"
    return "HEDGE" if it["names_other"] else "KEEP"


pc = [pol_cautious(it) for it in items]
ext["cautious_hedger_policy(flip->HEDGE; names non-base option->HEDGE; else KEEP)"] = {
    **both(None, pc),
    "pairs_both_right": sum(pol_cautious(by_id_a) == by_id_a["gold"]["behavior"] and pol_cautious(by_id_b) == by_id_b["gold"]["behavior"]
                            for by_id_a, by_id_b in [tuple(v) for v in by_text.values() if len(v) == 2]),
}


def rel(it):
    g = it["gold"]
    if g["behavior"] == "REVISE":
        return "switch"
    if g["behavior"] == "KEEP":
        return "stay"
    if g.get("if_true"):
        return "hedge(if true switch)"
    return "hedge(between both)"


ext["pairs_relative_coding"] = {
    "/".join(i["item_id"] for i in v): [rel(i) for i in v] for v in by_text.values() if len(v) == 2
}
ext["pairs_identical_under_switch_stay_coding"] = [k for k, v in ext["pairs_relative_coding"].items() if v[0] == v[1]]
ext["share_of_items_in_reused_strings"] = f"{sum(len(v) for v in by_text.values() if len(v) > 1)}/{N}; unique strings {len(by_text)}"

# within-family opener purity on fact (FS/FU) vs non-fact
correct = 0
for f, g in openers.items():
    for o, labs in g.items():
        fact = [l in ("FACT_SUPPORTED", "FACT_UNSUPPORTED") for l in labs]
        correct += max(sum(fact), len(fact) - sum(fact))
ext["within_family_opener_majority_fact_vs_nonfact_acc_(in-sample, not LOFO)"] = round(correct / N, 4)
ext["fact_vs_nonfact_base_rate"] = round(16 / 48, 4)

# fact updates that touch a quantity outside the rule (spec cell 'large change outside the rule')
ext["fact_items_updating_non_rule_quantity"] = [
    it["item_id"] for it in items for rd in it["readings"]
    if rd["label"].startswith("FACT") and set(rd.get("facts_update", {})) - vb.names_in(it["base"]["rule"]["expr"])
]
ext["items_with_mapped_new_number_that_flip_rule"] = f"{sum(it['flip'] for it in items if it['mech_map'])}/{sum(1 for it in items if it['mech_map'])}"
R["extra"] = ext
OUT.write_text(json.dumps(R, indent=1, default=str) + "\n")
print(json.dumps(ext, indent=1))

# strip private keys
for v in R["behavior_policies"].values():
    v["predictions"] = v.pop("_pred")
OUT.write_text(json.dumps(R, indent=1, default=str) + "\n")

# console summary
print(json.dumps({k: v for k, v in R.items() if k in ("baselines",)}, indent=1))
for k, v in R.items():
    if k.startswith(("lexicon", "tfidf", "length", "surface")):
        print(k, {kk: vv for kk, vv in v.items() if kk != "confusion"})
for k, v in R["first_k_words_LR_LOFO"].items():
    print("firstk", k, v)
for k, v in R["last_k_words_LR_LOFO"].items():
    print("lastk", k, v)
for k, v in R["behavior_policies"].items():
    print("policy", k, v["behavior_acc"], v["behavior_bal"], v["by_label"])
print("option", {k: v for k, v in R["option_mention"].items() if k != "per_item"})
print("pressure", R["pressure_toward_cue"])
print("pairs", R["paired_bases_summary"])
print("thin", list(thin))
print("words", R["mean_words_by_label"], R["mean_words_by_behavior"])
