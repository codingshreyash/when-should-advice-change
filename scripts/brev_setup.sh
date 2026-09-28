#!/usr/bin/env bash
# One-shot setup on a fresh Linux GPU box (24 GB, BF16). Run from the pilot kit root.
# Follows the Nimble README quickstart, then also prepares the pinned base model
# so run_nimble.py can score it with the identical scorer (adapter absent).
set -euo pipefail
START=$(date +%s)

# Pin both halves: Bespoke replaced the HF "main" checkpoint on 2026-09-24, and the
# scoring code tracks it. Pairs that go together:
#   latest (used 2026-09-26):  NIMBLE_REVISION=bd792f44ec8e265be861bfcdf4e05967ffe0e858  NIMBLE_CODE=62076b4f2d365b5879dafcf7f6dd072a1fe76df7
#   original-2676 (pilot 9/22): NIMBLE_REVISION=594dfdcfb6f94e3d0c0db7535180d3c71689169a  NIMBLE_CODE=54c2e82e8f613a7ab3a4d4072c50dfb9376db4e3
export NIMBLE_REVISION=${NIMBLE_REVISION:-bd792f44ec8e265be861bfcdf4e05967ffe0e858}
NIMBLE_CODE=${NIMBLE_CODE:-62076b4f2d365b5879dafcf7f6dd072a1fe76df7}
if [ ! -d nimble ]; then git clone https://github.com/bespokelabsai/nimble.git nimble; fi
git -C nimble checkout -q "$NIMBLE_CODE"
# Fall back to the system python; stock Ubuntu images ship without ensurepip.
PY=$(command -v python3.12 || command -v python3)
$PY -c 'import ensurepip' 2>/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv; }
rm -rf .venv && $PY -m venv .venv
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q torch==2.8.0 -r nimble/requirements/training.txt
export PYTHONPATH="$PWD/nimble:${PYTHONPATH:-}"
mkdir -p .cache/models

python - <<'PY'
import json, os, torch
from pathlib import Path
from huggingface_hub import snapshot_download
from peft import PeftModel
from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

repo = "bespokelabs/Bespoke-Nimble-9B"
snap = Path(snapshot_download(repo, revision=os.environ["NIMBLE_REVISION"], cache_dir=".cache/huggingface/hub"))
contract = json.loads((snap / "schema_config.json").read_text())
base_id, rev = contract["model"], contract["revision"]

# base model, saved once so both runs use the same weights source
base = Qwen3_5ForConditionalGeneration.from_pretrained(base_id, revision=rev, dtype=torch.bfloat16, device_map="cpu")
tok = AutoTokenizer.from_pretrained(snap)
base_path = Path(".cache/models/base-9b"); base.save_pretrained(base_path); tok.save_pretrained(base_path)

# merged Nimble
merged = PeftModel.from_pretrained(base, snap).merge_and_unload(safe_merge=True)
nimble_path = Path(".cache/models/nimble-9b"); merged.save_pretrained(nimble_path); tok.save_pretrained(nimble_path)

for name, p in [("nimble-model", nimble_path), ("base-model", base_path)]:
    Path(f".cache/{name}.json").write_text(json.dumps({
        "model_path": str(p.resolve()), "model_id": repo if name=="nimble-model" else base_id,
        "revision": snap.name if name=="nimble-model" else rev,
        "max_input_tokens": contract.get("max_length", 2048)}, indent=2))
print("models ready:", nimble_path, base_path)
PY

python -c 'import torch; assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(); print("GPU ok")'
echo "setup took $(( $(date +%s) - START ))s"
echo "Next: python scripts/run_nimble.py   (then STOP THE INSTANCE)"
