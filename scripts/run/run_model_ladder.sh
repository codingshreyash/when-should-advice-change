#!/bin/bash
# Claude size ladder (Haiku 4.5, Sonnet 5.5, Opus 5) under the protocol's settings:
# randomized option order (seed 1684), one sample. Exploratory until blind labels exist.
#
#   career30   all seven prompts of the 30 career scenarios, every model. Opus is rerun
#              here because its legacy career runs used fixed option order.
#   sweep      data/derived/threshold_sweep.jsonl for Haiku and Sonnet (Opus's sweep run
#              used the same settings already).
#
# The 30 scenarios are concatenated into a temporary career30.jsonl, so run_chat.py names
# the results results/career/<model>__career30.jsonl and they never overwrite the legacy
# files (<model>__career_pilot.jsonl, <model>__career_v2.jsonl). Sweep results go to
# results/threshold_sweep/<model>__threshold_sweep.jsonl.
# Models run in parallel, one log each in results/logs/<model>__ladder.log.
#
# Usage: bash scripts/run/run_model_ladder.sh [pid-to-wait-for]
#        RESUME=1 bash scripts/run/run_model_ladder.sh   (finish an interrupted run; see run_chat.py)
set -u
cd "$(dirname "$0")/../.."
if [ $# -ge 1 ]; then
  while kill -0 "$1" 2>/dev/null; do sleep 20; done
fi
tmp=$(mktemp -d)
cat data/scenarios/career_pilot.jsonl data/scenarios/career_v2.jsonl > "$tmp/career30.jsonl"
mkdir -p results/logs

run() {  # model, then (scenario file, output dir) pairs in order
  local model=$1; shift
  local log="results/logs/${model}__ladder.log"
  while [ $# -ge 2 ]; do
    CHAT_MODEL=$model RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SCENARIOS=$1 OUT_DIR=$2 \
      python3 scripts/run/run_chat.py >> "$log" 2>&1
    shift 2
  done
  echo "finished $(date -u +%FT%TZ)" >> "$log"
}

run claude-haiku-4-5-20251001 "$tmp/career30.jsonl" results/career data/derived/threshold_sweep.jsonl results/threshold_sweep &
run claude-sonnet-5-5 "$tmp/career30.jsonl" results/career data/derived/threshold_sweep.jsonl results/threshold_sweep &
run claude-opus-5 "$tmp/career30.jsonl" results/career &
wait
