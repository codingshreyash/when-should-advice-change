"""Figure: each model's decision curve on the threshold sweep, with and without pressure.

One panel per model (columns) and answer format (rows). The x axis is the swept value as
a multiple of the threshold where the right answer flips (log scale, 0.5x to 1.5x); the
y axis is the share of answers choosing the high-side option, pooled over the sweep
scenarios that model completed. A model that applies the rule perfectly follows the
dashed step at 1.0x; pressure that moves the boundary pulls the "toward high" curve
left and the "toward low" curve right. need_more_information counts as not choosing the
high-side option; refusals and unparsed answers are dropped.

Usage: python3 scripts/analysis/plot_threshold.py results/threshold_sweep/*.jsonl
Output: report/figures/threshold_curves.pdf (and .png for a quick look)
"""
import collections, json, math, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SWEEPS = "data/derived/threshold_sweep.jsonl"
OUT = "report/figures/threshold_curves"
NAMES = {"claude-haiku-4-5-20251001": "Haiku 4.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-opus-5": "Opus 5"}
ORDER = list(NAMES)
CONDS = [("constrained", "Code only"), ("conversational", "Written advice")]
# neutral reference + the first two validated categorical slots; line style and marker
# repeat the distinction so the figure reads in grayscale
STYLE = {"": ("No pressure", "#52514e", "-", "o"),
         "_pl": ("Pressure toward low-side option", "#2a78d6", "--", "v"),
         "_ph": ("Pressure toward high-side option", "#eb6834", ":", "^")}

def main(files):
    S = {s["id"]: s for s in map(json.loads, open(SWEEPS))}
    # only the stated-rule sweep is plotted; rows from other sweep files are skipped
    rows = [r for f in files for l in open(f) if l.strip() for r in [json.loads(l)] if r["id"] in S]
    expected = collections.Counter()
    for s in S.values(): expected[s["id"]] = len(s["prompts"]) * 2
    have = collections.Counter((r["model"], r["id"]) for r in rows)
    complete = {(m, i) for (m, i), n in have.items() if n == expected[i]}
    cells = collections.defaultdict(list)
    for r in rows:
        if (r["model"], r["id"]) not in complete or r.get("stop_reason") == "refusal" or r["choice"] is None:
            continue
        s = S[r["id"]]; lvl, _, suf = r["variant"].partition("_")
        k = int(lvl[1:]); suf = "_" + suf if suf else ""
        cells[(r["model"], r["condition"], suf, k)].append(r["choice"] == s["high"])
    ratios = [statistics_mean([lv["ratio"] for s in S.values() for lv in s["levels"] if lv["key"] == f"L{k}"]) for k in range(8)]
    models = [m for m in ORDER if any(k[0] == m for k in cells)]
    plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.edgecolor": "#8a8984",
                         "axes.linewidth": 0.6, "xtick.color": "#52514e", "ytick.color": "#52514e"})
    fig, axes = plt.subplots(len(CONDS), len(models), figsize=(6.3, 3.5), sharex=True, sharey=True, squeeze=False)
    for ci, (cond, cname) in enumerate(CONDS):
        for mi, m in enumerate(models):
            ax = axes[ci][mi]
            ax.step([0.47, 1.0, 1.0, 1.6], [0, 0, 1, 1], where="post", color="#b5b4ad", lw=1, ls=(0, (2, 2)), zorder=1)
            for suf, (label, color, ls, mk) in STYLE.items():
                xs, ys = [], []
                for k in range(8):
                    v = cells.get((m, cond, suf, k))
                    if v: xs.append(ratios[k]); ys.append(sum(v) / len(v))
                ax.plot(xs, ys, color=color, ls=ls, marker=mk, ms=3.2, lw=1.4, label=label, zorder=3,
                        markeredgecolor="#fcfcfb", markeredgewidth=0.5)
            ax.set_xscale("log"); ax.set_xlim(0.47, 1.6); ax.set_ylim(-0.04, 1.04)
            ax.set_xticks([0.5, 0.75, 1.0, 1.25, 1.5]); ax.set_xticklabels(["0.5", "0.75", "1", "1.25", "1.5"])
            ax.minorticks_off(); ax.grid(axis="y", color="#e6e5e0", lw=0.5); ax.set_axisbelow(True)
            for side in ("top", "right"): ax.spines[side].set_visible(False)
            n = len({i for (mm, i) in complete if mm == m})
            if ci == 0: ax.set_title(f"{NAMES[m]}" + ("" if n == len(S) else f" ({n} of {len(S)} scenarios)"), fontsize=8.5)
            if mi == 0: ax.set_ylabel(cname, fontsize=8.5)
            if ci == len(CONDS) - 1: ax.set_xlabel("value / threshold")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.01))
    fig.supylabel("share of answers choosing the high-side option", fontsize=8, color="#52514e", x=0.005)
    fig.tight_layout(rect=(0.02, 0.06, 1, 1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # no timestamps, so rerunning on the same data gives byte-identical files
    fig.savefig(OUT + ".pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT + ".png", dpi=200, metadata={"Software": None})
    print(f"wrote {OUT}.pdf; complete scenarios per model:",
          {NAMES[m]: len({i for (mm, i) in complete if mm == m}) for m in models})

def statistics_mean(xs):
    return sum(xs) / len(xs)

if __name__ == "__main__":
    main(sys.argv[1:])
