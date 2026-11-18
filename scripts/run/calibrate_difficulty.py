"""Calibrate scenario difficulty: turn-1 accuracy of a chat model on the BASE prompt only.

Sends one call per scenario (chat_prompt_conversational, option order fixed per scenario with
RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684, sample 0, exactly as run_second_look.py), parses the code with the
same extract_code (including backslash-escaped underscores) and reports:
  - accuracy on decisive scenarios (acceptable base answer is a single option),
  - the share of close calls (band, three acceptable codes) answered need_more_information,
  - accuracy / answer mix by margin bin.

Backend: CHAT_BACKEND=openai (CHAT_BASE_URL up to /v1, CHAT_API_KEY, CHAT_MODEL). Calls are made only with --yes
(the call count is printed first). Rows go to $OUT_DIR/<model>__<scenario stem>.jsonl (OUT_DIR default
results/calibration); refuses to overwrite unless OVERWRITE=1. --dry-run prints two prompts, no network.
--report FILE summarises an existing rows file without any call.
Usage: CHAT_BACKEND=openai CHAT_BASE_URL=... CHAT_API_KEY=... CHAT_MODEL=m \
       python3 scripts/run/calibrate_difficulty.py --scenarios data/scenarios/procedural/hard_calib.jsonl --yes
"""
import argparse, collections, json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_second_look import OpenAICompat, extract_code      # sets RANDOMIZE_OPTIONS=1, OPTION_ORDER_SEED=1684 defaults
from prompts import load, ordered_scenario, result_path, chat_prompt_conversational

NMI = "need_more_information"


def summarize(rows):
    dec = [r for r in rows if r["decisive"]]
    close = [r for r in rows if not r["decisive"]]
    pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "n/a"
    ok = sum(r["correct"] for r in dec)
    print(f"\nscenarios: {len(rows)}   decisive: {len(dec)}   close calls: {len(close)}")
    print(f"decisive accuracy: {ok}/{len(dec)} = {pct(ok, len(dec))}   (wrong: {sum(r['choice'] not in (None, NMI) and not r['correct'] for r in dec)} other option, "
          f"{sum(r['choice'] == NMI for r in dec)} need_more_information, {sum(r['choice'] is None for r in dec)} unparsed)")
    n_nmi = sum(r["choice"] == NMI for r in close)
    print(f"close calls answered need_more_information: {n_nmi}/{len(close)} = {pct(n_nmi, len(close))}")
    trunc = sum(r["stop_reason"] == "max_tokens" for r in rows)
    print(f"truncated (max_tokens): {trunc}   unparsed: {sum(r['choice'] is None for r in rows)}")
    print("by margin bin (|margin|):   n   decisive  accuracy   NMI-share(close)  unparsed")
    for b in sorted({r["margin_bin"] for r in rows}):
        g = [r for r in rows if r["margin_bin"] == b]
        d = [r for r in g if r["decisive"]]
        c = [r for r in g if not r["decisive"]]
        acc = pct(sum(r["correct"] for r in d), len(d)) if d else "-"
        nm = pct(sum(r["choice"] == NMI for r in c), len(c)) if c else "-"
        print(f"  bin {b}: {len(g):4d}   {len(d):4d}   {acc:>8}   {nm:>8}   {sum(r['choice'] is None for r in g)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default="data/scenarios/procedural/hard_calib.jsonl")
    ap.add_argument("--n", type=int, default=0, help="use only the first N scenarios (0 = all)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=2500, help="reasoning models may need more")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default=None, help="summarise an existing rows file and exit")
    a = ap.parse_args()
    if a.report:
        summarize([json.loads(l) for l in open(a.report) if l.strip()])
        return
    scen = load(a.scenarios)
    if a.n: scen = scen[:a.n]
    for s in scen: s["_o"] = ordered_scenario(s, "base", 0)
    model = os.environ.get("CHAT_MODEL", "claude-opus-5")

    if a.dry_run:
        for s in scen[:2]:
            print(f"===== {s['id']} option_order={s['_o']['options']} margin={s['margin']} acceptable={s['acceptable']['base']} =====")
            print(chat_prompt_conversational(s["_o"], "base") + "\n")
        print(f"DRY RUN: {len(scen)} scenarios = {len(scen)} calls, no network.")
        return

    print(f"model={model} scenarios={len(scen)} calls to make={len(scen)} workers={a.workers} max_tokens={a.max_tokens}")
    if not a.yes:
        sys.exit("Not calling the API: pass --yes to proceed.")
    if os.environ.get("CHAT_BACKEND") != "openai": sys.exit("CHAT_BACKEND=openai required")
    key, base = os.environ.get("CHAT_API_KEY"), os.environ.get("CHAT_BASE_URL")
    if not key or not base: sys.exit("needs CHAT_BASE_URL and CHAT_API_KEY")
    path = result_path(model.replace("/", "_"), default_dir="results/calibration", data=a.scenarios)

    client = OpenAICompat(base, key, model, a.max_tokens, a.temperature)
    lock, rows = threading.Lock(), []

    def work(s):
        o = s["_o"]
        txt, stop, refusal = client.ask([{"role": "user", "content": chat_prompt_conversational(o, "base")}])
        choice = extract_code(txt, s["options"])
        acc = s["acceptable"]["base"]
        row = {"model": model, "id": s["id"], "domain": s["domain"], "option_order": o["options"], "choice": choice,
               "text": txt, "stop_reason": stop, "refusal": refusal, "margin": s["margin"], "margin_bin": s["margin_bin"],
               "hard_level": s.get("hard_level", 0), "decisive": len(acc) == 1, "acceptable": acc,
               "expected": s["expected"]["base"], "correct": choice in acc}
        with lock:
            rows.append(row)
            if len(rows) % 25 == 0 or len(rows) == len(scen): print(f"  {len(rows)}/{len(scen)} calls", flush=True)

    try:
        with ThreadPoolExecutor(a.workers) as ex:
            for f in [ex.submit(work, s) for s in scen]: f.result()
    finally:
        rows.sort(key=lambda r: r["id"])
        with open(path, "w") as f:
            for r in rows: f.write(json.dumps(r) + "\n")
        print("wrote", path)
    summarize(rows)


if __name__ == "__main__":
    main()
