#!/bin/bash
# Claude size ladder (Haiku 4.5, Sonnet 5.5, Opus 5) under the protocol's settings:
# randomized option order (seed 1684), one sample. Exploratory until blind labels exist.
#
#   career30   all seven prompts of the 30 career scenarios, every model. Opus is rerun
#              here because its legacy career runs used fixed option order.
#   sweep      data/threshold_sweep.jsonl for Haiku and Sonnet (Opus's sweep run used the
#              same settings already).
#
# The 30 scenarios are concatenated into a temporary career30.jsonl so the results are
# named results/chat_<model>_career30.jsonl and never overwrite the legacy files.
# Models run in parallel, one log each in results/chat_run_ladder_<model>.log.
#
# Usage: bash scripts/run_model_ladder.sh [pid-to-wait-for]
set -u
cd "$(dirname "$0")/.."
if [ $# -ge 1 ]; then
  while kill -0 "$1" 2>/dev/null; do sleep 20; done
fi
tmp=$(mktemp -d)
cat data/pilot_scenarios.jsonl data/career_v2.jsonl > "$tmp/career30.jsonl"

run() {  # model, then scenario files in order
  local model=$1; shift
  for f in "$@"; do
    CHAT_MODEL=$model RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684 SCENARIOS=$f \
      python3 scripts/run_chat.py >> "results/chat_run_ladder_${model}.log" 2>&1
  done
  echo "finished $(date -u +%FT%TZ)" >> "results/chat_run_ladder_${model}.log"
}

run claude-haiku-4-5-20251001 "$tmp/career30.jsonl" data/threshold_sweep.jsonl &
run claude-sonnet-5-5 "$tmp/career30.jsonl" data/threshold_sweep.jsonl &
run claude-opus-5 "$tmp/career30.jsonl" &
wait
