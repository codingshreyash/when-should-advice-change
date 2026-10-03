#!/usr/bin/env bash
# Everything that needs the GPU for the pressure-control + steering study, in one go.
# Run on a fresh 24 GB box from the repo root. Expect ~45 min total on an L4
# (~10 setup, ~2 Nimble scorer on the controls, ~15 per model for steering).
# Stops itself at the end if STOP_WHEN_DONE=1 (needs sudo), so an unattended run can't idle.
set -euo pipefail
START=$(date +%s)
[ -f .cache/nimble-model.json ] || bash scripts/brev_setup.sh
source .venv/bin/activate
export PYTHONPATH="$PWD/nimble:${PYTHONPATH:-}"

python scripts/build_pressure_controls.py
# 1. Nimble's own scorer on the controls (both models), comparable to results/nimble_career_v2.jsonl
SCENARIOS=data/pressure_controls.jsonl python scripts/run_nimble.py
# 2. our scorer + direction ablation
python scripts/run_steering.py

echo "all GPU work took $(( $(date +%s) - START ))s"
echo "copy results/ back (scp or git push), then DELETE the instance"
if [ "${STOP_WHEN_DONE:-0}" = "1" ]; then sudo shutdown -h +2; fi
