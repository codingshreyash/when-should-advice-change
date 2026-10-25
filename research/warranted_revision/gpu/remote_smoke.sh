#!/usr/bin/env bash
# Runs ON the GPU instance, started by gpu/brev_controller.py. Usage:
#   bash gpu/remote_smoke.sh <run_id> <deadline_minutes>
# The in-instance `timeout` is only a soft guard; the billing stop is the controller's
# provider-side delete.
set -euo pipefail
RUN_ID="$1"; DEADLINE_MIN="$2"
PY=$(command -v python3.12 || command -v python3)
# Stock Ubuntu images often ship without venv support (same fallback as scripts/run/brev_setup.sh).
$PY -m venv .venv || { sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv && $PY -m venv .venv; }
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -e '.[gpu,dev]'
# Qwen3.5 needs a transformers release that ships Qwen3_5ForConditionalGeneration.
# Fail here, before any inference, rather than mid-run; the installed version is recorded.
python -c "import transformers as t; assert hasattr(t, 'Qwen3_5ForConditionalGeneration')" \
  || python -m pip install -q -U transformers
python -c "import transformers as t; assert hasattr(t, 'Qwen3_5ForConditionalGeneration'), t.__version__; print('transformers', t.__version__)"
# Optional fast kernels for Qwen3.5's linear-attention layers (smoke-003 ran without them and
# transformers fell back to slow reference code). Best effort, time-limited, never fatal.
timeout 600 python -m pip install -q flash-linear-attention || echo "flash-linear-attention not installed (optional)"
timeout 300 python -m pip install -q --only-binary=:all: causal-conv1d || echo "causal-conv1d wheel not available (optional)"
OUT="$HOME/results/warranted_revision/$RUN_ID"
mkdir -p /tmp/wrev && pip freeze > /tmp/wrev/pip_freeze.txt
nvidia-smi --query-gpu=name,memory.total --format=csv > /tmp/wrev/gpu.txt || true
# Preflight: the CPU suite must pass on the box before any model call.
python -m pytest -q
mkdir -p "$HOME/results/warranted_revision"
python - "$RUN_ID" <<'PY'
import json, os, sys
cfg = json.load(open("configs/gpu_smoke.json")); cfg["run_id"] = sys.argv[1]
cfg["out_root"] = os.path.expanduser("~/results/warranted_revision")
json.dump(cfg, open("/tmp/wrev/config.json", "w"), indent=2)
PY
python -m warranted_revision.runner --config /tmp/wrev/config.json --dry-run
timeout "${DEADLINE_MIN}m" python -m warranted_revision.runner --config /tmp/wrev/config.json
cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
python -m warranted_revision.evaluate --run "$OUT" --gold data/v0/dev_gold.jsonl
python -m warranted_revision.report --run "$OUT" --compress
# Results are in ~/results/warranted_revision/<run_id> for the controller to copy back.
echo "remote smoke finished: $OUT"
