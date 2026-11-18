#!/usr/bin/env bash
# One attended GPU session for the neutral-rewrite test (Qwen3.5-9B base rewrites, then
# Nimble + Qwen3.5-9B score the rewritten prompts). Exploratory. Follow docs/gpu_budget.md:
# someone at the keyboard, a 60-minute phone timer, delete the instance when done.
#
# On a fresh 24 GB box (L4/A10G), from a clone of the repo:
#   git clone <repo url> && cd are-you-sure-about-that && git checkout instability-boundary
#   bash scripts/run/run_gpu_rewrite.sh
#
# Hypothesis: a fixed LLM instruction that restates each prompt neutrally removes Qwen's
# directional pressure effect while keeping the update rate on relevant facts. Stages:
#   rw_career  rewrite the 30 career scenarios (career_pilot + career_v2), 6 variants
#              -> data/derived/rewritten_career30.jsonl
#   rw_proc    rewrite every second scenario of data/scenarios/procedural/procedural_third.jsonl
#              (LIMIT_SCENARIOS=2, ~67 of 134) -> data/derived/rewritten_procedural_third.jsonl
#              (if procedural_third.jsonl is not in the clone it is rebuilt from procedural_v0.jsonl
#              using the ids in results/procedural/nimble-and-qwen__procedural_third.jsonl)
#   score      Nimble + Qwen on both rewritten files, RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684,
#              5 permutations for career, 1 for procedural -> results/rewrite/
#              Option order depends only on seed, scenario id, variant and sample (prompts.py
#              ordered_scenario), not on the prompt text or file name, so the orders equal those
#              of the original runs and the comparison is paired.
#   control    run_nimble.py on data/derived/pressure_controls.jsonl, 1 permutation ->
#              results/pressure_controls/ (mention_target vs pref_target separates priming
#              from deference). VARIANTS limits the keys scored (pref_t* are for run_steering only).
# The rewriting model and the scorers do not share GPU memory: every stage is its own
# process and run_rewrite.py frees the model (del, gc, empty_cache) before exit.
# A stage is skipped when elapsed time already passes MAX_MIN (default 45), checked at stage start.
#
# Knobs:  STAGES="rw_career rw_proc score control"   MAX_MIN=45   CAREER_SAMPLES=5  PROC_SAMPLES=1
#         BATCH=16  MAX_NEW=400   DRY_RUN=1 (print commands only, no GPU needed)
#         STOP_WHEN_DONE=1   shut down 2 min after the last stage (needs sudo)
# Output: data/derived/rewritten_*.jsonl and results/rewrite/, results/pressure_controls/, bundled
#         into /tmp/rewrite_results.tgz. Existing files are never replaced (OVERWRITE=1 to force);
#         a failed stage does not stop the rest.
set -uo pipefail
cd "$(dirname "$0")/../.."
START=$(date +%s)
STAGES=${STAGES:-"rw_career rw_proc score control"}
MAX_MIN=${MAX_MIN:-45}
CAREER_SAMPLES=${CAREER_SAMPLES:-5}
PROC_SAMPLES=${PROC_SAMPLES:-1}
BATCH=${BATCH:-16}
MAX_NEW=${MAX_NEW:-400}
DRY=${DRY_RUN:-0}
VARS="base,pressure,reframe,irrelevant_update,relevant_update,omission"
RW_CAREER=data/derived/rewritten_career30.jsonl
RW_PROC=data/derived/rewritten_procedural_third.jsonl
PROC_THIRD=data/scenarios/procedural/procedural_third.jsonl

do_cmd() { if [ "$DRY" = "1" ]; then echo "[dry-run] $*"; else eval "$@"; fi; }
elapsed_min() { echo $(( ($(date +%s) - START) / 60 )); }

if [ "$DRY" != "1" ]; then
  { [ -f .cache/base-model.json ] && [ -f .cache/nimble-model.json ]; } || bash scripts/run/brev_setup.sh || { echo "setup failed"; exit 1; }
  source .venv/bin/activate
  export PYTHONPATH="$PWD/nimble:${PYTHONPATH:-}"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi
echo "session started $(date -u +%FT%TZ); stages: $STAGES; budget ${MAX_MIN} min"

tmp=$(mktemp -d)
cat data/scenarios/career_pilot.jsonl data/scenarios/career_v2.jsonl > "$tmp/career30.jsonl"
mkdir -p data/derived results/rewrite results/pressure_controls
: > "$tmp/new_files.txt"

timed() {  # name, command...; skips when the budget is used, never aborts the session
  local name=$1; shift
  if [ "$(elapsed_min)" -ge "$MAX_MIN" ]; then echo "SKIP $name: ${MAX_MIN} min budget used"; return 1; fi
  echo "=== $name, $(elapsed_min) min elapsed"
  local t0=$(date +%s)
  do_cmd "$@" || { echo "FAILED $name (see above)"; return 1; }
  echo "$name took $(( $(date +%s) - t0 ))s"
}

rewrite() {  # name, scenario file, limit, out file
  local name=$1 file=$2 limit=$3 out=$4
  timed "$name" "SCENARIOS=$file VARIANTS=$VARS LIMIT_SCENARIOS=$limit OUT=$out python scripts/run/run_rewrite.py --batch $BATCH --max-new-tokens $MAX_NEW" \
    && echo "$out" >> "$tmp/new_files.txt"
}

score() {  # name, scenario file, samples, out dir
  local name=$1 file=$2 n=$3 out=$4 extra=${5:-}
  timed "$name" "RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SAMPLES=$n SCENARIOS=$file OUT_DIR=$out $extra python scripts/run/run_nimble.py" \
    && echo "$out/nimble-and-qwen__$(basename "${file%.jsonl}").jsonl" >> "$tmp/new_files.txt"
}

for s in $STAGES; do
  case $s in
    rw_career) rewrite rw_career "$tmp/career30.jsonl" 1 "$RW_CAREER" ;;
    rw_proc)
      if [ ! -f "$PROC_THIRD" ]; then
        do_cmd "python3 - <<'PY'
import json
ids = {json.loads(l)['id'] for l in open('results/procedural/nimble-and-qwen__procedural_third.jsonl')}
with open('$PROC_THIRD', 'w') as f:
    f.writelines(l for l in open('data/scenarios/procedural/procedural_v0.jsonl') if json.loads(l)['id'] in ids)
PY"
      fi
      rewrite rw_proc "$PROC_THIRD" 2 "$RW_PROC" ;;
    score)
      score score_career "$RW_CAREER" "$CAREER_SAMPLES" results/rewrite
      score score_proc   "$RW_PROC"   "$PROC_SAMPLES"   results/rewrite ;;
    control) CTRL_VARIANTS=${CTRL_VARIANTS:-base,pref_target,pref_target_1p,mention_target,filler,pref_base,pressure}
             score control data/derived/pressure_controls.jsonl 1 results/pressure_controls "VARIANTS=$CTRL_VARIANTS" ;;
    *) echo "unknown stage $s" ;;
  esac
done

if [ "$DRY" != "1" ]; then
  tar czf /tmp/rewrite_results.tgz $(sort -u "$tmp/new_files.txt" | while read f; do [ -f "$f" ] && echo "$f"; done) 2>/dev/null \
    && echo "bundle: /tmp/rewrite_results.tgz" || echo "no result files to bundle"
fi
echo "total $(elapsed_min) min"
echo "NEXT: copy /tmp/rewrite_results.tgz back, then DELETE the instance (not just stop it)."
if [ "${STOP_WHEN_DONE:-0}" = "1" ] && [ "$DRY" != "1" ]; then sudo shutdown -h +2; fi
