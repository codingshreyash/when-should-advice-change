"""Compare committed metrics.json with a re-evaluation on a scratch copy.
Usage: python3 compare_metrics.py <committed_run_dir> <scratch_run_dir>"""
import json, sys
a = json.load(open(sys.argv[1] + "/metrics.json"))
b = json.load(open(sys.argv[2] + "/metrics.json"))
def flat(m):
    out = {}
    for arm in m["arms"]:
        k = arm["condition"]
        for key in ("base_accuracy", "axis_warranted_update", "axis_unwarranted_stability", "abstention_missing_information", "update_tpr", "false_update_rate"):
            out[(k, key)] = (arm[key]["value"], tuple(arm[key]["ci95"] or ()), arm[key]["n"], arm[key]["n_families"])
    for c in m["comparisons"]:
        out[(c["kind"], c["a"], c["b"], c["axis"])] = (c["diff"], tuple(c["ci95"] or ()))
    return out
fa, fb = flat(a), flat(b)
only_a = sorted(set(fa) - set(fb), key=str); only_b = sorted(set(fb) - set(fa), key=str)
diff = [(k, fa[k], fb[k]) for k in sorted(set(fa) & set(fb), key=str) if fa[k] != fb[k]]
print(f"keys committed={len(fa)} recomputed={len(fb)} common={len(set(fa)&set(fb))}")
print("only in committed:", len(only_a)); [print("  ", k) for k in only_a]
print("only in recomputed:", len(only_b)); [print("  ", k) for k in only_b]
print("value differences:", len(diff)); [print("  ", k, a_, "->", b_) for k, a_, b_ in diff]
