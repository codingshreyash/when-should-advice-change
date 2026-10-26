#!/usr/bin/env bash
# Runs ON the GPU instance, started by gpu/brev_controller.py. Usage:
#   bash gpu/remote_job.sh <run_id> <deadline_minutes> <config> <shard i/n> <bench 0|1>
# The in-instance `timeout` is only a soft guard; the billing stop is the controller's
# provider-side delete.
set -euo pipefail
RUN_ID="$1"; DEADLINE_MIN="$2"; CONFIG="${3:-configs/gpu_smoke.json}"; SHARD="${4:-1/1}"; BENCH="${5:-0}"
PY=$(command -v python3.12 || command -v python3)
# Stock Ubuntu images often ship without venv support (same fallback as scripts/run/brev_setup.sh).
$PY -m venv .venv || { sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv && $PY -m venv .venv; }
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -e '.[gpu,dev]'
# Qwen3.5 needs a transformers release that ships Qwen3_5ForConditionalGeneration.
python -c "import transformers as t; assert hasattr(t, 'Qwen3_5ForConditionalGeneration')" \
  || python -m pip install -q -U transformers
python -c "import transformers as t; assert hasattr(t, 'Qwen3_5ForConditionalGeneration'), t.__version__; print('transformers', t.__version__)"
mkdir -p /tmp/wrev
nvidia-smi --query-gpu=name,memory.total --format=csv > /tmp/wrev/gpu.txt || true
# Preflight: the CPU suite must pass on the box before any model call.
python -m pytest -q

install_kernels() {
  # Optional fast kernels for Qwen3.5's linear-attention layers. Best effort, time-limited,
  # never fatal; whether they actually load is recorded by the benchmark/run logs.
  timeout 600 python -m pip install -q "flash-linear-attention[cuda]" || echo "flash-linear-attention not installed"
  timeout 300 python -m pip install -q --only-binary=:all: causal-conv1d || echo "causal-conv1d wheel not available"
}

IS_PROBE=$(python -c "import json; print(int(json.load(open('$CONFIG')).get('experiment') in ('scaffold_probe', 'goal_screen')))")
if [ "$IS_PROBE" = "1" ] && [ "$BENCH" != "1" ]; then
  # The probe's short direct calls don't need the optional kernels; skip the install time.
  echo "scaffold probe: skipping optional kernel install"
elif [ "$BENCH" = "1" ]; then
  # Same fixed batch before and after installing the kernels.
  # Benchmark failures never stop the job. If the kernel build breaks generation, remove it so
  # the run itself uses the known-good fallback path.
  python -m warranted_revision.bench --config configs/gpu_smoke.json --label fallback \
    --out /tmp/wrev/bench-fallback.json || echo "fallback benchmark failed"
  install_kernels
  python -m warranted_revision.bench --config configs/gpu_smoke.json --label kernels \
    --out /tmp/wrev/bench-kernels.json \
    || { echo "kernel benchmark failed; uninstalling kernels for the run";
         python -m pip uninstall -y -q flash-linear-attention fla-core causal-conv1d || true; }
else
  install_kernels
fi
pip freeze > /tmp/wrev/pip_freeze.txt

OUT="$HOME/results/warranted_revision/$RUN_ID"
mkdir -p "$HOME/results/warranted_revision"
python - "$RUN_ID" "$CONFIG" "$SHARD" <<'PY'
import json, os, sys
run_id, config, shard = sys.argv[1:4]
cfg = json.load(open(config)); cfg["run_id"] = run_id; cfg["shard"] = shard
cfg["out_root"] = os.path.expanduser("~/results/warranted_revision")
json.dump(cfg, open("/tmp/wrev/config.json", "w"), indent=2)
if "inputs" in cfg:
    open("/tmp/wrev/gold_path", "w").write(cfg["inputs"].replace("_inputs.jsonl", "_gold.jsonl"))
PY
if python -c "import json,sys; sys.exit(json.load(open('/tmp/wrev/config.json')).get('experiment') != 'goal_screen')"; then
  # Goal screen: its own runner; the analysis applies the pre-registered rule (exploratory).
  # A 30-call preflight on this box gates the full run (all calls made, no errors, <= 10%
  # unparseable, projected runtime x 1.5 within the minutes left); a failed gate stops here
  # and the controller still copies back and deletes the instance.
  T0=$(date +%s)
  python -m warranted_revision.goal_screen --config /tmp/wrev/config.json --dry-run
  PRE="$OUT-preflight"
  timeout "${DEADLINE_MIN}m" python -m warranted_revision.goal_screen --config /tmp/wrev/config.json --preflight
  LEFT=$(( DEADLINE_MIN - ( $(date +%s) - T0 ) / 60 ))
  if ! python -m warranted_revision.goal_screen_job gate --run "$PRE" --remaining-min "$LEFT"; then
    mkdir -p "$OUT"; mv "$PRE" "$OUT/preflight"; cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
    echo "GOAL_SCREEN PREFLIGHT_GATE FAILED: full run not started"
    exit 3
  fi
  timeout "${LEFT}m" python -m warranted_revision.goal_screen --config /tmp/wrev/config.json
  mv "$PRE" "$OUT/preflight"
  cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
  python -m warranted_revision.goal_screen_analysis --run "$OUT" || echo "GOAL_SCREEN ERROR"
  python -m warranted_revision.goal_screen_analysis --run "$OUT" \
    --subset v2/ai_precalibration/screen_v1/primary.json || echo "GOAL_SCREEN ERROR"
  gzip -k "$OUT/calls.jsonl"
elif python -c "import json,sys; sys.exit(json.load(open('/tmp/wrev/config.json')).get('experiment') != 'scaffold_probe')"; then
  # Scaffold probe: its own runner and records; gold-free gates printed as a PROBE_CHECK line.
  python -m warranted_revision.scaffold_probe --config /tmp/wrev/config.json --dry-run
  timeout "${DEADLINE_MIN}m" python -m warranted_revision.scaffold_probe --config /tmp/wrev/config.json
  cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
  python -m warranted_revision.probe_analysis --run "$OUT" || echo "PROBE_CHECK ERROR"
  gzip -k "$OUT/probe_calls.jsonl"
else
  python -m warranted_revision.runner --config /tmp/wrev/config.json --dry-run
  timeout "${DEADLINE_MIN}m" python -m warranted_revision.runner --config /tmp/wrev/config.json
  cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
  cp /tmp/wrev/bench-*.json "$OUT/" 2>/dev/null || true
  python -m warranted_revision.evaluate --run "$OUT" --gold "$(cat /tmp/wrev/gold_path)"
  python -m warranted_revision.report --run "$OUT" --compress
  # Pre-declared shard checks; the PILOT_CHECK line in the job log decides the next shard.
  python -m warranted_revision.pilot_check --run "$OUT" || echo "PILOT_CHECK ERROR"
fi
echo "remote job finished: $OUT"
