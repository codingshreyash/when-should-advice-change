"""Re-run every pref_target_1p call that was refused in the pressure-controls run, 3 samples
each, to see whether the refusals repeat.

usage: python scripts/recheck_refusals.py   (key from CS1684_ANTHROPIC_KEY or ANTHROPIC_API_KEY)
"""
import json, os, sys
sys.path.insert(0, "scripts")
from build_prompts import load, chat_prompt_conversational, chat_prompt_constrained
from run_chat import ask, extract_code, MODEL

SRC, OUT, VARIANT, N = ("results/chat_claude-opus-5_pressure_controls.jsonl",
                        "results/refusal_recheck_pref1p.jsonl", "pref_target_1p", 3)
BUILD = {"conversational": (chat_prompt_conversational, 8000),
         "constrained": (chat_prompt_constrained, 4000)}

def main():
    import anthropic
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    key = os.environ.get("CS1684_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key, default_headers={"anthropic-workspace-id": ws} if ws else None)
    scen = {s["id"]: s for s in load("data/pressure_controls.jsonl")}
    with open(SRC) as f:
        todo = [r for r in map(json.loads, f) if r["variant"] == VARIANT and r["stop_reason"] == "refusal"]
    with open(OUT, "w") as out:
        for r in todo:
            s, (build, max_tokens) = scen[r["id"]], BUILD[r["condition"]]
            for k in range(N):
                txt, stop, refusal = ask(client, build(s, VARIANT), max_tokens)
                if r["condition"] == "constrained":
                    txt = txt.strip()
                out.write(json.dumps({"model": MODEL, "condition": r["condition"], "id": s["id"],
                                      "variant": VARIANT, "sample": k, "stop_reason": stop, "refusal": refusal,
                                      "choice": extract_code(txt, s["options"]), "text": txt}) + "\n")
            out.flush()
            print(s["id"], r["condition"], "ok", flush=True)

if __name__ == "__main__":
    main()
