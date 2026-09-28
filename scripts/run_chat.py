"""Chat model in two conditions: conversational (free text, code on last line) and
constrained (code only). Uses the Anthropic Python SDK; set ANTHROPIC_API_KEY.

The Claude API exposes no logprobs, so the constrained condition records the choice
only. Sampling parameters are fixed by the API on current models, and thinking is
left at the model default in both conditions. For a model whose logits you own (e.g.
the same Qwen3.5-9B run locally), score the option codes directly instead.
"""
import json, os, re, sys
sys.path.insert(0, "scripts")
from build_prompts import load, iter_items, TAG, chat_prompt_conversational, chat_prompt_constrained

MODEL = os.environ.get("CHAT_MODEL", "claude-opus-5")
SAMPLES = int(os.environ.get("SAMPLES", "1"))   # set 5 on the base variant later for the noise baseline

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
    client = anthropic.Anthropic(default_headers={"anthropic-workspace-id": ws} if ws else None)
    os.makedirs("results", exist_ok=True)
    with open(f"results/chat_{MODEL}{TAG}.jsonl", "w") as out:
        for s, variant, _ in iter_items(load()):
            for k in range(SAMPLES):
                # conversational
                txt, stop, refusal = ask(client, chat_prompt_conversational(s, variant), 8000)
                out.write(json.dumps({"model": MODEL, "condition": "conversational", "id": s["id"],
                                      "variant": variant, "sample": k, "stop_reason": stop, "refusal": refusal,
                                      "choice": extract_code(txt, s["options"]), "text": txt}) + "\n")
                # constrained
                # max_tokens covers any thinking the model does before the code
                txt, stop, refusal = ask(client, chat_prompt_constrained(s, variant), 4000)
                out.write(json.dumps({"model": MODEL, "condition": "constrained", "id": s["id"],
                                      "variant": variant, "sample": k, "stop_reason": stop, "refusal": refusal,
                                      "choice": extract_code(txt, s["options"]), "text": txt.strip()}) + "\n")
            print(s["id"], variant, "ok")

if __name__ == "__main__":
    main()
