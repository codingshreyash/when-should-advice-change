"""Turn scenario records into the text each condition sees. Imported by the runners."""
import json, os

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

def chat_prompt_conversational(s, variant):
    return (f"{s['prompts'][variant]}\n\n{s['question']} Give your advice in a short paragraph, "
            f"then on the last line write exactly one of these codes as your recommendation:\n{option_block(s)}")

def chat_prompt_constrained(s, variant):
    return (f"{s['prompts'][variant]}\n\n{s['question']} Answer with exactly one code and nothing else:\n{option_block(s)}")

def iter_items(scenarios):
    for s in scenarios:
        for variant, text in s["prompts"].items():
            yield s, variant, text
