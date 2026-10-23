"""Chat model in two conditions: conversational (free text, code on last line) and
constrained (code only). Uses the Anthropic Python SDK; set ANTHROPIC_API_KEY.

The Claude API exposes no logprobs, so the constrained condition records the choice
only. Sampling parameters are fixed by the API on current models, and thinking is
left at the model default in both conditions. For a model whose logits you own (e.g.
the same Qwen3.5-9B run locally), score the option codes directly instead.

Output: $OUT_DIR/<model>__<scenario stem>.jsonl, OUT_DIR defaulting to results/runs.
An existing output file is never replaced unless OVERWRITE=1. RESUME=1 continues an
interrupted run instead: it keeps every prompt answered in both conditions, drops a
half-finished one, and appends only what is missing (option order depends only on
scenario and sample, so resumed prompts get the order they would have had; every variant
of a scenario shares that order within a sample).
Usage: CHAT_MODEL=claude-opus-5 SCENARIOS=data/scenarios/career_v2.jsonl python3 scripts/run/run_chat.py
"""
import collections, json, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from prompts import (load, iter_items, ordered_scenario, result_path,
                     chat_prompt_conversational, chat_prompt_constrained)

MODEL = os.environ.get("CHAT_MODEL", "claude-opus-5")
SAMPLES = int(os.environ.get("SAMPLES", "1"))   # set 5 on the base variant later for the noise baseline
RESUME = os.environ.get("RESUME") == "1"

def completed(path):
    """(id, variant, sample) answered in both conditions; rewrites the file without the
    rows of any half-finished item so appending keeps it consistent."""
    if not os.path.exists(path): return set()
    rows = [json.loads(l) for l in open(path) if l.strip()]
    key = lambda r: (r["id"], r["variant"], r.get("sample", 0))
    n = collections.Counter(key(r) for r in rows)
    keep = [r for r in rows if n[key(r)] == 2]
    with open(path, "w") as f:
        for r in keep: f.write(json.dumps(r) + "\n")
    return {key(r) for r in keep}

def extract_code(text, options):
    for line in reversed(text.strip().splitlines()):
        for o in options:
            if re.fullmatch(rf"\W*{re.escape(o)}\W*", line.strip()):
                return o
    # fallback: last option mentioned anywhere
    hits = [(text.rfind(o), o) for o in options if o in text]
    return max(hits)[1] if hits else None

def ask(client, prompt, max_tokens):
    r = client.messages.create(model=MODEL, max_tokens=max_tokens,
                               messages=[{"role": "user", "content": prompt}])
    txt = "".join(b.text for b in r.content if b.type == "text")
    d = r.stop_details if r.stop_reason == "refusal" else None
    refusal = {"category": d.category, "explanation": d.explanation} if d else None
    return txt, r.stop_reason, refusal

def main():
    import anthropic
    # Org-level keys (not scoped to a workspace) must name one on every request.
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    # cloud environments reserve ANTHROPIC_API_KEY, so a project-named variable works too
    key = os.environ.get("CS1684_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key, default_headers={"anthropic-workspace-id": ws} if ws else None)
    path = result_path(MODEL, resume=RESUME)
    done = completed(path) if RESUME else set()
    with open(path, "a" if RESUME else "w") as out:
        for s, variant, _ in iter_items(load()):
            for k in range(SAMPLES):
                if (s["id"], variant, k) in done: continue
                ordered = ordered_scenario(s, variant, k)
                # conversational
                txt, stop, refusal = ask(client, chat_prompt_conversational(ordered, variant), 8000)
                out.write(json.dumps({"model": MODEL, "condition": "conversational", "id": s["id"],
                                      "variant": variant, "sample": k, "stop_reason": stop, "refusal": refusal,
                                      "option_order": ordered["options"],
                                      "choice": extract_code(txt, s["options"]), "text": txt}) + "\n")
                # constrained
                # max_tokens covers any thinking the model does before the code
                txt, stop, refusal = ask(client, chat_prompt_constrained(ordered, variant), 4000)
                out.write(json.dumps({"model": MODEL, "condition": "constrained", "id": s["id"],
                                      "variant": variant, "sample": k, "stop_reason": stop, "refusal": refusal,
                                      "option_order": ordered["options"],
                                      "choice": extract_code(txt, s["options"]), "text": txt.strip()}) + "\n")
                out.flush()
            print(s["id"], variant, "ok")

if __name__ == "__main__":
    main()
