"""Turn scenario records into the text each condition sees. Imported by the runners."""
import hashlib, json, os, random

# SCENARIOS=data/career_v2.jsonl runs another scenario file; results get its name as a
# suffix so the pilot results are never overwritten.
DATA = os.environ.get("SCENARIOS", "data/pilot_scenarios.jsonl")
TAG = "" if DATA == "data/pilot_scenarios.jsonl" else "_" + os.path.splitext(os.path.basename(DATA))[0]

def load(path=DATA):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def option_block(s):
    return "\n".join(f"- {code}: {s['option_text'][code]}" for code in s["options"])

def nimble_schema(s):
    """Nimble wants a flat schema: one enum field with the option codes as choices."""
    return {"decision": {"type": "enum",
                         "choices": s["options"],
                         "description": s["question"],
                         "choice_descriptions": {c: s["option_text"][c] for c in s["options"]}}}

def ordered_scenario(s, variant, sample=0):
    """Return a copy with a reproducible option permutation when requested.

    Set RANDOMIZE_OPTIONS=1 for confirmatory runs. The seed is stable across
    Python processes and differs by scenario, variant, and replicate.
    """
    out = {**s, "options": list(s["options"])}
    if os.environ.get("RANDOMIZE_OPTIONS", "0") == "1":
        root = os.environ.get("OPTION_ORDER_SEED", "1684")
        token = f"{root}:{s['id']}:{variant}:{sample}".encode()
        seed = int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
        random.Random(seed).shuffle(out["options"])
    return out

def chat_prompt_conversational(s, variant):
    return (f"{s['prompts'][variant]}\n\n{s['question']} Give your advice in a short paragraph, "
            f"then on the last line write exactly one of these codes as your recommendation:\n{option_block(s)}")

def chat_prompt_constrained(s, variant):
    return (f"{s['prompts'][variant]}\n\n{s['question']} Answer with exactly one code and nothing else:\n{option_block(s)}")

# VARIANTS=base,pressure,... limits a run to some prompt keys (e.g. skip the pref_t*
# phrasings in pressure_controls.jsonl, which only run_steering.py needs)
ONLY = set(os.environ["VARIANTS"].split(",")) if os.environ.get("VARIANTS") else None

def iter_items(scenarios):
    for s in scenarios:
        for variant, text in s["prompts"].items():
            if ONLY is None or variant in ONLY:
                yield s, variant, text
