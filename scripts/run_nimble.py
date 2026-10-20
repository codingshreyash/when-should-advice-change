"""Run every prompt through Bespoke-Nimble-9B and its base model with the same scorer.

Expects to run from the pilot kit root, inside the nimble repo's Python env, after
brev_setup.sh. Loads one model at a time to fit a 24 GB GPU.

Output: results/nimble.jsonl, one line per (model, scenario, variant) with the
chosen option and the probability of every option.
"""
import json, os, sys, time, gc
sys.path.insert(0, "scripts")
from build_prompts import load, nimble_schema, iter_items, ordered_scenario, TAG

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
    os.makedirs("results", exist_ok=True)
    t0 = time.time()
    with open(f"results/nimble{TAG}.jsonl", "w") as out:
        # the HF checkpoint changed once already; keep versions apart in every table
        rev = json.load(open(NIMBLE_CFG))["revision"][:8]
        run_one(NIMBLE_CFG, f"bespoke-nimble-9b@{rev}", out)
        run_one(BASE_CFG,   "qwen3.5-9b-base-same-scorer", out)
    print(f"finished in {time.time()-t0:.0f}s")
    print("DONE - stop the instance now")
