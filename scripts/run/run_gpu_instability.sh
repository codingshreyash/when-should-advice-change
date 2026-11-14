#!/usr/bin/env bash
# One attended GPU session for the instability study (Nimble + Qwen3.5-9B, same scorer).
# Exploratory until blind labels exist. Follow docs/gpu_budget.md: someone at the keyboard,
# a 60-minute phone timer, delete the instance when done.
#
# On a fresh 24 GB box (L4/A10G), from a clone of the repo:
#   git clone <repo url> && cd when-should-advice-change && git checkout instability-boundary
#   bash scripts/run/run_gpu_instability.sh
#
# The scorers are deterministic, so "samples" here are option permutations
# (RANDOMIZE_OPTIONS=1, seed 1684), as PROTOCOL.md asks. Stages run in priority order:
#   smoke   20 generated scenarios, 1 permutation: checks the setup before the long runs
#   career  30 career scenarios, all 7 variants (incl. irrelevant + subthreshold), 5 permutations
#   sweep   data/derived/threshold_sweep.jsonl, 1 permutation (same as the Opus sweep)
#   proc    400 generated scenarios, PROC_SAMPLES permutations (default 1)
# Each stage loads both models again (a few minutes). A stage is skipped when elapsed time
# already passes MAX_MIN (default 45), so the session cannot run past the timer.
#
# Knobs:  STAGES="smoke career sweep proc"   which stages to run
#         MAX_MIN=45  PROC_SAMPLES=1  CAREER_SAMPLES=5  SWEEP_SAMPLES=1
#         DRY_RUN=1   print the commands only (works without a GPU)
#         STOP_WHEN_DONE=1   shut the machine down 2 min after the last stage (needs sudo)
# Output: results/career/, results/threshold_sweep/, results/procedural/ and one bundle
#         at /tmp/instability_results.tgz to copy back (brev copy or scp). Existing result
#         files are never replaced (OVERWRITE=1 to force); a failed stage does not stop the rest.
set -uo pipefail
cd "$(dirname "$0")/../.."
START=$(date +%s)
STAGES=${STAGES:-"smoke career sweep proc"}
MAX_MIN=${MAX_MIN:-45}
CAREER_SAMPLES=${CAREER_SAMPLES:-5}
SWEEP_SAMPLES=${SWEEP_SAMPLES:-1}
PROC_SAMPLES=${PROC_SAMPLES:-1}
DRY=${DRY_RUN:-0}

do_cmd() { if [ "$DRY" = "1" ]; then echo "[dry-run] $*"; else eval "$@"; fi; }
elapsed_min() { echo $(( ($(date +%s) - START) / 60 )); }

if [ "$DRY" != "1" ]; then
  [ -f .cache/nimble-model.json ] || bash scripts/run/brev_setup.sh || { echo "setup failed"; exit 1; }
  source .venv/bin/activate
  export PYTHONPATH="$PWD/nimble:${PYTHONPATH:-}"
  python scripts/data/validate_procedural.py | tail -1
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi
echo "session started $(date -u +%FT%TZ); stages: $STAGES; budget ${MAX_MIN} min"

tmp=$(mktemp -d)
cat data/scenarios/career_pilot.jsonl data/scenarios/career_v2.jsonl > "$tmp/career30.jsonl"
mkdir -p results/career results/threshold_sweep results/procedural results/runs
: > "$tmp/new_files.txt"

stage() {  # name, scenario file, out dir, samples
  local name=$1 file=$2 out=$3 n=$4
  if [ "$(elapsed_min)" -ge "$MAX_MIN" ]; then
    echo "SKIP $name: ${MAX_MIN} min budget used"; return
  fi
  echo "=== $name: $file x $n permutation(s), $(elapsed_min) min elapsed"
  local t0=$(date +%s)
  do_cmd "RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SAMPLES=$n SCENARIOS=$file OUT_DIR=$out python scripts/run/run_nimble.py" \
    || { echo "FAILED $name (see above)"; return; }
  echo "$name took $(( $(date +%s) - t0 ))s"
  echo "$out/nimble-and-qwen__$(basename "${file%.jsonl}").jsonl" >> "$tmp/new_files.txt"
}

for s in $STAGES; do
  case $s in
    smoke)  stage smoke  data/scenarios/procedural/sample20.jsonl results/runs 1 ;;
    career) stage career "$tmp/career30.jsonl" results/career "$CAREER_SAMPLES" ;;
    sweep)  stage sweep  data/derived/threshold_sweep.jsonl results/threshold_sweep "$SWEEP_SAMPLES" ;;
    proc)   stage proc   data/scenarios/procedural/procedural_v0.jsonl results/procedural "$PROC_SAMPLES" ;;
    *) echo "unknown stage $s" ;;
  esac
done

if [ "$DRY" != "1" ]; then
  tar czf /tmp/instability_results.tgz $(cat "$tmp/new_files.txt" | while read f; do [ -f "$f" ] && echo "$f"; done) 2>/dev/null \
    && echo "bundle: /tmp/instability_results.tgz" || echo "no result files to bundle"
fi
echo "total $(elapsed_min) min"
echo "NEXT: copy /tmp/instability_results.tgz back, then DELETE the instance (not just stop it)."
if [ "${STOP_WHEN_DONE:-0}" = "1" ] && [ "$DRY" != "1" ]; then sudo shutdown -h +2; fi
