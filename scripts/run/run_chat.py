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
CONDITIONS=conversational (or constrained) runs one format only; the default is both.
Each row records `choice_strict` (a final line that is exactly one option code) beside
`choice` (strict, else the option code mentioned last), and the git commit it ran from.
Usage: CHAT_MODEL=claude-opus-5 SCENARIOS=data/scenarios/career_v2.jsonl python3 scripts/run/run_chat.py
"""
import collections, json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from prompts import (load, iter_items, ordered_scenario, result_path,
                     chat_prompt_conversational, chat_prompt_constrained)

MODEL = os.environ.get("CHAT_MODEL", "claude-opus-5")
SAMPLES = int(os.environ.get("SAMPLES", "1"))   # set 5 on the base variant later for the noise baseline
RESUME = os.environ.get("RESUME") == "1"
CONDITIONS = os.environ.get("CONDITIONS", "conversational,constrained").split(",")
assert set(CONDITIONS) <= {"conversational", "constrained"} and CONDITIONS, CONDITIONS

def completed(path, scenarios):
    """(id, variant, sample) answered in exactly the requested conditions, in the option
    order this configuration would show; rewrites the file without the rows of any
    half-finished item so appending keeps it consistent. A file holding another condition
    or another option order was made with different settings, so resuming it stops."""
    if not os.path.exists(path): return set()
    rows = [json.loads(l) for l in open(path) if l.strip()]
    key = lambda r: (r["id"], r["variant"], r.get("sample", 0))
    other = {r["condition"] for r in rows} - set(CONDITIONS)
    if other:
        sys.exit(f"{path} has {sorted(other)} rows but CONDITIONS={','.join(CONDITIONS)}; not resuming")
    by_id = {s["id"]: s for s in scenarios}
    for r in rows:
        want = ordered_scenario(by_id[r["id"]], r["variant"], r.get("sample", 0))["options"]
        if r.get("option_order") != want:
            sys.exit(f"{path}: {key(r)} was shown options {r.get('option_order')}, this "
                     f"configuration shows {want} (RANDOMIZE_OPTIONS / OPTION_ORDER_SEED differ?); not resuming")
    conds = collections.defaultdict(list)
    for r in rows: conds[key(r)].append(r["condition"])
    done = {k for k, c in conds.items() if sorted(c) == sorted(CONDITIONS)}
    with open(path, "w") as f:
        for r in rows:
            if key(r) in done: f.write(json.dumps(r) + "\n")
    return done

def parse_code(text, options):
    """(strict, recovered). strict: the last line that is exactly one option code (up to
    punctuation), the format both prompts ask for; None otherwise. recovered: strict, or
    failing that the option code mentioned last anywhere in the text, which can pick up a
    code from the explanation. Analyses that judge format compliance use strict."""
    for line in reversed(text.strip().splitlines()):
        for o in options:
            if re.fullmatch(rf"\W*{re.escape(o)}\W*", line.strip()):
                return o, o
    hits = [(text.rfind(o), o) for o in options if o in text]
    return None, (max(hits)[1] if hits else None)

def extract_code(text, options):
    """The recovered parse, as used by run_pushback.py and recheck_refusals.py."""
    return parse_code(text, options)[1]

def code_version():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None

def record(condition, s, variant, k, ordered, txt, stop, refusal, version):
    strict, recovered = parse_code(txt, s["options"])
    # `choice` keeps the recovered parse so older analyses read new files the same way
    return json.dumps({"model": MODEL, "condition": condition, "id": s["id"], "variant": variant,
                       "sample": k, "stop_reason": stop, "refusal": refusal,
                       "option_order": ordered["options"], "choice": recovered,
                       "choice_strict": strict, "code_version": version, "text": txt}) + "\n"

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
    scenarios = load()
    done = completed(path, scenarios) if RESUME else set()
    version = code_version()
    with open(path, "a" if RESUME else "w") as out:
        for s, variant, _ in iter_items(scenarios):
            for k in range(SAMPLES):
                if (s["id"], variant, k) in done: continue
                ordered = ordered_scenario(s, variant, k)
                if "conversational" in CONDITIONS:
                    txt, stop, refusal = ask(client, chat_prompt_conversational(ordered, variant), 8000)
                    out.write(record("conversational", s, variant, k, ordered, txt, stop, refusal, version))
                if "constrained" in CONDITIONS:
                    # max_tokens covers any thinking the model does before the code
                    txt, stop, refusal = ask(client, chat_prompt_constrained(ordered, variant), 4000)
                    out.write(record("constrained", s, variant, k, ordered, txt.strip(), stop, refusal, version))
                out.flush()
            print(s["id"], variant, "ok")

if __name__ == "__main__":
    main()
