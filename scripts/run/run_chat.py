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
scenario, variant and sample, so resumed prompts get the order they would have had).
Usage: CHAT_MODEL=claude-opus-5 SCENARIOS=data/scenarios/career_v2.jsonl python3 scripts/run/run_chat.py

Any OpenAI-compatible endpoint (NVIDIA inference, OpenRouter, a local vLLM server) works
with CHAT_BACKEND=openai. Set CHAT_BASE_URL (up to and including /v1), CHAT_API_KEY and
CHAT_MODEL; the code uses only the standard library. Example:
  CHAT_BACKEND=openai CHAT_BASE_URL=https://openrouter.ai/api/v1 CHAT_API_KEY=... \
  CHAT_MODEL=<model id> SCENARIOS=... python3 scripts/run/run_chat.py
Rows keep the same fields. `stop_reason` is mapped from finish_reason (stop -> end_turn,
length -> max_tokens, content_filter -> refusal); the model's own refusal text, if any,
goes in `refusal`. Free-tier or hosted models may differ in sampling settings, so name the
endpoint in the write-up; results from different backends are different models.
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

BACKEND = os.environ.get("CHAT_BACKEND", "anthropic")

class OpenAICompat:
    """Chat completions over plain HTTP. Retries 429 and 5xx with backoff."""
    def __init__(self, base_url, key):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.key = key

    def ask(self, prompt, max_tokens):
        import time, urllib.request, urllib.error
        body = json.dumps({"model": MODEL, "max_tokens": max_tokens,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(self.url, data=body, headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    r = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                    time.sleep(min(60, 2 ** attempt * 3)); continue
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}") from None
            except urllib.error.URLError:
                if attempt < 5: time.sleep(min(60, 2 ** attempt * 3)); continue
                raise
        ch = r["choices"][0]
        msg = ch.get("message", {})
        txt = msg.get("content") or ""
        stop = {"stop": "end_turn", "length": "max_tokens",
                "content_filter": "refusal"}.get(ch.get("finish_reason"), ch.get("finish_reason"))
        refusal = {"category": None, "explanation": msg["refusal"]} if msg.get("refusal") else None
        if refusal: stop = "refusal"
        return txt, stop, refusal

def main():
    if BACKEND == "openai":
        key = os.environ.get("CHAT_API_KEY")
        base = os.environ.get("CHAT_BASE_URL")
        if not key or not base:
            sys.exit("CHAT_BACKEND=openai needs CHAT_BASE_URL and CHAT_API_KEY")
        client = OpenAICompat(base, key)
        run(client, lambda c, p, n: c.ask(p, n))
        return
    import anthropic
    # Org-level keys (not scoped to a workspace) must name one on every request.
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    # cloud environments reserve ANTHROPIC_API_KEY, so a project-named variable works too
    key = os.environ.get("CS1684_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key, default_headers={"anthropic-workspace-id": ws} if ws else None)
    run(client, ask)

def run(client, ask):
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
