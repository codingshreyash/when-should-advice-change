#!/usr/bin/env bash
# Reproduce every number in v2_reports/04_offline.md. Read-only on results/, src/, data/.
# All output goes to a fresh temp dir (printed at the end). No GPU, no network.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(cd "$HERE/../.." && pwd)"            # research/warranted_revision
REPO="$(cd "$PKG/../.." && pwd)"
OUT="$(mktemp -d)"
cd "$OUT"                                    # neutral cwd (avoids module shadowing)
python3 "$HERE/anatomy.py"           > "$OUT/anatomy.txt"
python3 "$HERE/measurement.py"       > "$OUT/measurement.txt"
python3 "$HERE/corrected_metrics.py" > "$OUT/corrected_metrics.txt"
# committed evaluator at 1e5d8b8 on scratch copies: confirms reproduction and the dropped
# format-001 ablation rows
git -C "$REPO" archive 1e5d8b8 research/warranted_revision/src | tar -x -C "$OUT"
for r in smoke-003 smoke-004 format-001; do
  mkdir -p "$OUT/runs/$r"
  cp "$REPO/results/warranted_revision/$r/"{manifest.json,decisions.jsonl,search_traces.jsonl,predictions.jsonl} "$OUT/runs/$r/"
  PYTHONPATH="$OUT/research/warranted_revision/src" python3 -B -m warranted_revision.evaluate \
    --run "$OUT/runs/$r" --gold "$PKG/data/v0/dev_gold.jsonl" > /dev/null
  # optional: corr-1 (commit 7d6e5a5 or later) for the cross-check; prints only
  if [ -f "$PKG/src/warranted_revision/corrections.py" ]; then
    PYTHONPATH="$PKG/src" python3 -B -m warranted_revision.corrections \
      --run "$OUT/runs/$r" --gold "$PKG/data/v0/dev_gold.jsonl" > "$OUT/corr1_$r.json"
  fi
done
python3 - "$OUT" "$REPO" <<'PY'
import json, sys
out, repo = sys.argv[1], sys.argv[2]
for r in ("smoke-003", "smoke-004", "format-001"):
    a = json.load(open(f"{repo}/results/warranted_revision/{r}/metrics.json"))
    b = json.load(open(f"{out}/runs/{r}/metrics.json"))
    A = {x["condition"]: x for x in a["arms"]}; B = {x["condition"]: x for x in b["arms"]}
    def flat(x, p=""):
        if isinstance(x, dict):
            for k, v in x.items():
                yield from flat(v, p + "/" + k)
        else:
            yield p, x
    bad = 0
    for c in A:
        fb = dict(flat(B[c]))
        bad += sum(fb.get(k, "MISSING") != v for k, v in flat(A[c]))
    ka = {(c["kind"], c["a"], c["b"], c["axis"]) for c in a["comparisons"]}
    kb = {(c["kind"], c["a"], c["b"], c["axis"]) for c in b["comparisons"]}
    print(r, "committed leaf values differing at 1e5d8b8:", bad, "| committed comparison rows missing at 1e5d8b8:", sorted(ka - kb))
PY
[ -f "$OUT/corr1_smoke-004.json" ] && python3 "$HERE/crosscheck_corr1.py" "$OUT"
echo "outputs in $OUT"
