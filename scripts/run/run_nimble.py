"""Run every prompt through Bespoke-Nimble-9B and its base model with the same scorer.

Run from the repo root inside the venv that scripts/run/brev_setup.sh builds (the
nimble repo on PYTHONPATH). Loads one model at a time to fit a 24 GB GPU.

Output: $OUT_DIR/nimble-and-qwen__<scenario stem>.jsonl (OUT_DIR defaults to results/runs),
one line per (model, scenario, variant) with the chosen option and the probability of
every option. Both models go in one file; the `model` field tells them apart.
Usage: SCENARIOS=data/scenarios/career_v2.jsonl python3 scripts/run/run_nimble.py
"""
import json, os, sys, time, gc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from prompts import load, nimble_schema, iter_items, ordered_scenario, result_path

NIMBLE_CFG = ".cache/nimble-model.json"   # written by brev_setup.sh / Nimble quickstart
BASE_CFG   = ".cache/base-model.json"     # written by brev_setup.sh (pinned base, no adapter)
SAMPLES = int(os.environ.get("SAMPLES", "1"))

def run_one(cfg_path, label, out):
    import torch
    from nimble.scoring.cuda_scorer import CudaCandidateScorer
    cfg = json.load(open(cfg_path))
    scorer = CudaCandidateScorer(**cfg)
    n = 0
    for s, variant, text in iter_items(load()):
        for sample in range(SAMPLES):
            ordered = ordered_scenario(s, variant, sample)
            r = scorer.score(text, nimble_schema(ordered))
            probs = r["fields"]["decision"]["scores"]
            out.write(json.dumps({"model": label, "revision": r["revision"], "condition": "decision_only",
                                  "id": s["id"], "variant": variant, "sample": sample,
                                  "option_order": ordered["options"],
                                  "choice": r["output"]["decision"], "probs": probs}) + "\n")
            n += 1
    out.flush()
    del scorer; gc.collect(); torch.cuda.empty_cache()
    print(f"{label}: {n} prompts scored")

if __name__ == "__main__":
    t0 = time.time()
    with open(result_path("nimble-and-qwen"), "w") as out:
        # the HF checkpoint changed once already; keep versions apart in every table
        rev = json.load(open(NIMBLE_CFG))["revision"][:8]
        run_one(NIMBLE_CFG, f"bespoke-nimble-9b@{rev}", out)
        run_one(BASE_CFG,   "qwen3.5-9b-base-same-scorer", out)
    print(f"finished in {time.time()-t0:.0f}s")
    print("DONE - stop the instance now")
