"""Turn scenario records into the text each condition sees. Imported by the runners."""
import hashlib, json, os, random

# SCENARIOS=data/scenarios/career_v2.jsonl runs another scenario file.
DATA = os.environ.get("SCENARIOS", "data/scenarios/career_pilot.jsonl")

def load(path=DATA):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def result_path(model, default_dir="results/runs", data=None, resume=False):
    """Where a runner writes: $OUT_DIR/<model>__<scenario-file stem>.jsonl.

    OUT_DIR defaults to default_dir (results/runs for the single-turn runners). The
    directory is created if needed. The scenario stem keeps runs on different scenario
    files apart, e.g. results/runs/claude-opus-5__career_v2.jsonl. Refuses to replace an
    existing file unless OVERWRITE=1 (or resume=True, for runners that append).
    """
    out_dir = os.environ.get("OUT_DIR", default_dir)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(data or DATA))[0]
    path = os.path.join(out_dir, f"{model}__{stem}.jsonl")
    if not resume:
        refuse_overwrite(path)
    return path

def refuse_overwrite(path):
    """Runners open their output with "w"; stop before that would erase an existing
    results file. Set OVERWRITE=1 to replace it on purpose."""
    if os.path.exists(path) and os.environ.get("OVERWRITE") != "1":
        raise SystemExit(f"{path} already exists; set OVERWRITE=1 to replace it, or OUT_DIR to write elsewhere")

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
# phrasings in data/derived/pressure_controls.jsonl, which only run_steering.py needs)
ONLY = set(os.environ["VARIANTS"].split(",")) if os.environ.get("VARIANTS") else None

def iter_items(scenarios):
    for s in scenarios:
        for variant, text in s["prompts"].items():
            if ONLY is None or variant in ONLY:
                yield s, variant, text
