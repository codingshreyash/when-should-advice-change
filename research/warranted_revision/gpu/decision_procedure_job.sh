#!/usr/bin/env bash
# Runs ON the GPU instance for the CS 1684 decision-procedure experiment; started by
# gpu/remote_job.sh, which hands over before its own install (Nimble's scorer pins its own
# transformers). Usage: bash gpu/decision_procedure_job.sh <run_id> <deadline_minutes> <config>
#
# Steps: environment at the pinned Nimble code -> CPU suite and frozen-file lock -> download,
# contract check and merge -> technical pilot (counts only), or preflight + gate + full run
# + preregistered analysis (if the blind labels are bundled). Results go into the job log
# (DP_FILE / DP_CALLS lines). The in-instance `timeout` is a soft guard; billing stops only
# with the controller's provider-side delete.
set -euo pipefail
RUN_ID="$1"; DEADLINE_MIN="$2"; CONFIG="$3"
T0=$(date +%s)
left_min() { echo $(( DEADLINE_MIN - ( $(date +%s) - T0 ) / 60 )); }
# `timeout 0` means no limit, so refuse to start a step with under 2 minutes left.
bounded() { local m; m=$(left_min); if [ "$m" -lt 2 ]; then echo "DP DEADLINE: $m min left"; return 4; fi; timeout "${m}m" "$@"; }
mkdir -p /tmp/wrev
OUT_ROOT="$HOME/results/warranted_revision"; OUT="$OUT_ROOT/$RUN_ID"; mkdir -p "$OUT_ROOT"

PY=$(command -v python3.12 || command -v python3)
$PY -m venv .venv || { sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv && $PY -m venv .venv; }
source .venv/bin/activate
python -m pip install -q --upgrade pip
pin() { python -c "import json,sys; c=json.load(open('$CONFIG')); print(eval(sys.argv[1], {}, {'c': c}))" "$1"; }
NIMBLE_REPO=$(pin "c['nimble']['code_repo']"); NIMBLE_CODE=$(pin "c['nimble']['code_commit']")
git clone -q "$NIMBLE_REPO" nimble
git -C nimble checkout -q "$NIMBLE_CODE"
python -m pip install -q torch==2.8.0 -r nimble/requirements/training.txt huggingface_hub
python -m pip install -q -e '.[dev]'
export PYTHONPATH="$PWD/nimble:${PYTHONPATH:-}"
python -c "import torch; assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(); print('GPU', torch.cuda.get_device_name(0))"
nvidia-smi --query-gpu=name,memory.total --format=csv > /tmp/wrev/gpu.txt || true
pip freeze > /tmp/wrev/pip_freeze.txt
python -m pytest -q
python -m warranted_revision.decision_procedure lock

python - "$RUN_ID" "$CONFIG" "$OUT_ROOT" <<'PY'
import json, sys
run_id, config, out_root = sys.argv[1:4]
cfg = json.load(open(config)); cfg["run_id"] = run_id; cfg["out_root"] = out_root
json.dump(cfg, open("/tmp/wrev/config.json", "w"), indent=1)
PY
python -m warranted_revision.decision_procedure run --config /tmp/wrev/config.json --dry-run
python -m warranted_revision.decision_procedure prepare --config /tmp/wrev/config.json --cache "$PWD/.cache"
echo "[job] models ready after $(( ( $(date +%s) - T0 ) / 60 )) min; $(left_min) min left"

PILOT=$(python -c "import json; print(int(json.load(open('/tmp/wrev/config.json')).get('technical_pilot', False)))")
if [ "$PILOT" = "1" ]; then
  # Technical pilot: counts only (no outcome metric is computed or printed).
  bounded python -m warranted_revision.decision_procedure run \
    --config /tmp/wrev/config.json --cache "$PWD/.cache"
  # Parse and error checks on the pilot; timing projected onto the confirmatory config.
  python -m warranted_revision.decision_procedure gate --run "$OUT" --remaining-min 100000 \
    --project configs/decision_procedure_full.json || echo "DP PILOT_GATE FAILED"
  cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
  # Raw rows are preserved in the log; no outcome is computed from them.
  python -m warranted_revision.decision_procedure emit --run "$OUT" --calls
  echo "remote job finished: $OUT"
  exit 0
fi

PRE="$OUT-preflight"
bounded python -m warranted_revision.decision_procedure run \
  --config /tmp/wrev/config.json --cache "$PWD/.cache" --preflight
if ! python -m warranted_revision.decision_procedure gate --run "$PRE" --remaining-min "$(left_min)"; then
  mkdir -p "$OUT"; mv "$PRE" "$OUT/preflight"; cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
  python -m warranted_revision.decision_procedure emit --run "$OUT"
  echo "DP PREFLIGHT_GATE FAILED: full run not started"
  exit 3
fi
bounded python -m warranted_revision.decision_procedure run \
  --config /tmp/wrev/config.json --cache "$PWD/.cache"
mv "$PRE" "$OUT/preflight"
cp /tmp/wrev/pip_freeze.txt /tmp/wrev/gpu.txt "$OUT/"
LABELS=$(ls cs1684/data/labeling/*_blind.jsonl 2>/dev/null || true)
if [ -n "$LABELS" ]; then
  # shellcheck disable=SC2086
  python -m warranted_revision.decision_procedure_analysis --run "$OUT" --labels $LABELS > /dev/null \
    || echo "DP ANALYSIS ERROR"
else
  echo "DP ANALYSIS SKIPPED: no blind labels in the bundle"
fi
python -m warranted_revision.decision_procedure emit --run "$OUT" --calls
gzip -k "$OUT/calls.jsonl"
echo "remote job finished: $OUT"
