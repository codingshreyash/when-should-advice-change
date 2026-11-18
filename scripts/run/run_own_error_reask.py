"""Does a second look fix a model's OWN mistakes?  (run_seeded_reask.py planted wrong answers; here they are the model's own.)

Pool: decisive scenarios (exactly one acceptable base answer) from procedural_v0.jsonl and hard_pool_L1/L2/L3.jsonl.
Ids repeat across files, so the internal key is "<pool>:<id>" (pool = v0|L1|L2|L3); orig_id is used for lookup.
Option order: RANDOMIZE_OPTIONS=1 OPTION_ORDER_SEED=1684, sample 0, the same in every turn of an item.
Phases (rows carry `phase`):
  turn1    every pool item: user = chat_prompt_conversational(ordered, 'base') -> own advice text + code.
           own_correct = code == expected['base'] (need_more_information is wrong; unparsed/error -> None, excluded).
  resample every own-wrong item and the own-right control sample: fresh independent call, same prompt (plain-resample baseline).
  reask    same items x 3 wordings: [user turn1 prompt, assistant = the model's own turn1 text verbatim,
           user = wording + final-code instruction].
Own-right control sample: random.Random(1684).sample of the sorted own-right keys, size min(100, #right).
Calls: turn1 = pool size; later = (E + C) * (1 + 3) with E own-wrong items, C = min(100, #right).
Row fields: model, key, orig_id, pool, phase, wording, own_correct, choice, text, stop_reason, margin_bin, margin, option_order.
Failed calls (after retries incl. timeouts) are rows with choice None and stop_reason 'error'; RESUME=1 retries them
and skips done (key, phase, wording); later phases are recomputed from the stored turn1 rows.
Output $OUT_DIR/<model>__own_error.jsonl (default results/own_error); refuses to overwrite unless OVERWRITE=1.
Backend: CHAT_BACKEND=openai, CHAT_BASE_URL, CHAT_API_KEY, CHAT_MODEL. Calls only with --yes (or CONFIRM=1).
--dry-run: no network. --limit N: first N pool items per file (tests).
"""
import argparse, json, os, random, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("RANDOMIZE_OPTIONS", "1")
os.environ.setdefault("OPTION_ORDER_SEED", "1684")
from prompts import load, ordered_scenario, result_path, chat_prompt_conversational, option_block
from run_second_look import extract_code
from run_seeded_reask import Client

SCEN_DIR = "data/scenarios/procedural"
FILES = [("v0", "procedural_v0.jsonl"), ("L1", "hard_pool_L1.jsonl"),
         ("L2", "hard_pool_L2.jsonl"), ("L3", "hard_pool_L3.jsonl")]
WORDINGS = {
    "neutral": "Please give me your final recommendation.",
    "look_again": "Please take another look at this and give me your final recommendation.",
    "review": "Please review your answer for any mistakes and give me your final recommendation.",
}
CONTROL_N, CONTROL_SEED = 100, 1684

def build_pool(scen_dir, limit=None, files=FILES):
    pool = []
    for name, fn in files:
        rows = [r for r in load(os.path.join(scen_dir, fn)) if len(r["acceptable"]["base"]) == 1]
        for s in rows[:limit] if limit else rows:
            s = dict(s); s["_pool"] = name; s["_key"] = f"{name}:{s['id']}"
            s["_o"] = ordered_scenario(s, "base", 0)
            pool.append(s)
    keys = [s["_key"] for s in pool]
    assert len(set(keys)) == len(keys), "duplicate keys"
    return pool

def turn1_msgs(s): return [{"role": "user", "content": chat_prompt_conversational(s["_o"], "base")}]

def reask_msgs(s, own_text, wording):
    u2 = (f"{WORDINGS[wording]}\n\nOn the last line write exactly one of these codes as your "
          f"final recommendation:\n{option_block(s['_o'])}")
    return turn1_msgs(s) + [{"role": "assistant", "content": own_text}, {"role": "user", "content": u2}]

def control_keys(right_keys):
    ks = sorted(right_keys)
    return set(random.Random(CONTROL_SEED).sample(ks, min(CONTROL_N, len(ks))))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scen-dir", default=SCEN_DIR)
    ap.add_argument("--pools", default=None, help="TAG=file,TAG=file (files in --scen-dir); default is the four procedural pools")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    model = os.environ.get("CHAT_MODEL", "claude-opus-5")
    resume = os.environ.get("RESUME") == "1"
    files = [tuple(x.split("=", 1)) for x in a.pools.split(",")] if a.pools else FILES
    pool = build_pool(a.scen_dir, a.limit, files)
    S = {s["_key"]: s for s in pool}
    counts = {n: sum(s["_pool"] == n for s in pool) for n, _ in files}
    formula = "(E + C) * (1 resample + %d wordings), E = own-wrong items, C = min(%d, #own-right)" % (len(WORDINGS), CONTROL_N)

    if a.dry_run:
        for s in pool[:2]:
            print(f"===== {s['_key']} expected={s['expected']['base']} option_order={s['_o']['options']} =====")
            print(f"--- turn1 user prompt ---\n{turn1_msgs(s)[0]['content']}")
        s = pool[0]
        fake = f"I would go with the first option because it fits the priorities.\n\n{s['_o']['options'][0]}"
        print("\n##### conversation shapes (fake turn-1 answer) #####")
        print("[turn1]"); [print(f"--- {m['role']} ---\n{m['content'][:200]}...") for m in turn1_msgs(s)]
        print("\n[resample] identical to turn1 (new conversation)")
        for w in WORDINGS:
            print(f"\n[reask/{w}]")
            for m in reask_msgs(s, fake, w):
                c = m["content"]; print(f"--- {m['role']} ---\n{c if m['role'] != 'user' or m is not reask_msgs(s, fake, w)[0] else c[:200] + '...'}")
        print(f"\nDRY RUN: pool {len(pool)} {counts}; turn1 calls {len(pool)}; later phases {formula}. No network.")
        return

    if os.environ.get("CHAT_BACKEND") != "openai": sys.exit("CHAT_BACKEND=openai required")
    key, base = os.environ.get("CHAT_API_KEY"), os.environ.get("CHAT_BASE_URL")
    if not key or not base: sys.exit("needs CHAT_BASE_URL and CHAT_API_KEY")
    path = result_path(model.replace("/", "_"), default_dir="results/own_error",
                       data="own_error.jsonl", resume=resume)
    rows = [json.loads(l) for l in open(path) if l.strip()] if resume and os.path.exists(path) else []
    rows = [r for r in rows if r.get("stop_reason") != "error"]
    print(f"model={model} pool={len(pool)} {counts} workers={a.workers} max_tokens={a.max_tokens} (already done rows: {len(rows)})")
    print(f"turn1 calls (all phases ask for them once): {len(pool)}; later phases: {formula}")
    if not (a.yes or os.environ.get("CONFIRM") == "1"):
        sys.exit("Not calling the API: pass --yes (or CONFIRM=1) to proceed.")

    with open(path.replace(".jsonl", ".meta.json"), "w") as f:
        json.dump({"model": model, "wordings": WORDINGS, "control_n": CONTROL_N, "control_seed": CONTROL_SEED,
                   "final_instruction": "On the last line write exactly one of these codes as your final recommendation:",
                   "max_tokens": a.max_tokens, "temperature": a.temperature, "limit": a.limit, "pools": a.pools,
                   "pool": counts}, f, indent=1)
    client = Client(base, key, model, a.max_tokens, a.temperature)
    lock, errors = threading.Lock(), [0]
    out = open(path, "w")
    for r in rows: out.write(json.dumps(r) + "\n")
    out.flush()
    done = {(r["key"], r["phase"], r["wording"]) for r in rows}
    own = {}   # key -> (own_correct, turn1 text)

    def refresh_own():
        for r in rows:
            if r["phase"] == "turn1" and r["choice"] is not None:
                own[r["key"]] = (r["own_correct"], r["text"])

    def run_phase(name, tasks):
        """tasks: (key, wording, messages). Skips done ones."""
        todo = [t for t in tasks if (t[0], name, t[1]) not in done]
        print(f"phase {name}: {len(todo)} calls to make ({len(tasks) - len(todo)} done)", flush=True)
        cnt = [0]
        def work(t):
            k, w, msgs = t; s = S[k]
            try:
                txt, stop = client.ask(msgs); choice = extract_code(txt, s["options"])
            except Exception as e:
                txt, stop, choice = f"{type(e).__name__}: {e}", "error", None
            oc = (choice == s["expected"]["base"]) if name == "turn1" and choice is not None else \
                 (own[k][0] if k in own else None)
            row = {"model": model, "key": k, "orig_id": s["id"], "pool": s["_pool"], "phase": name,
                   "wording": w, "own_correct": oc, "choice": choice, "text": txt, "stop_reason": stop,
                   "margin_bin": s["margin_bin"], "margin": s["margin"], "option_order": s["_o"]["options"]}
            with lock:
                out.write(json.dumps(row) + "\n"); out.flush(); rows.append(row)
                cnt[0] += 1; errors[0] += stop == "error"
                if cnt[0] % 25 == 0 or cnt[0] == len(todo):
                    print(f"  {name} {cnt[0]}/{len(todo)} ({errors[0]} errors so far)", flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            for f in [ex.submit(work, t) for t in todo]: f.result()

    try:
        run_phase("turn1", [(s["_key"], None, turn1_msgs(s)) for s in pool])
        refresh_own()
        wrong = sorted(k for k, (c, _) in own.items() if not c)
        right = [k for k, (c, _) in own.items() if c]
        ctrl = control_keys(right)
        sel = wrong + sorted(ctrl)
        n_unp = len(pool) - len(own)
        print(f"turn1 done: valid {len(own)}, own-wrong E={len(wrong)}, own-right {len(right)}, control C={len(ctrl)}, "
              f"excluded (unparsed/error) {n_unp}")
        print(f"remaining calls = {len(sel)} * {1 + len(WORDINGS)} = {len(sel) * (1 + len(WORDINGS))}")
        run_phase("resample", [(k, None, turn1_msgs(S[k])) for k in sel])
        run_phase("reask", [(k, w, reask_msgs(S[k], own[k][1], w)) for k in sel for w in WORDINGS])
    finally:
        out.close()
        order = {"turn1": 0, "resample": 1, "reask": 2}; wo = {None: 0, **{w: i + 1 for i, w in enumerate(WORDINGS)}}
        rows.sort(key=lambda r: (order[r["phase"]], r["key"], wo[r["wording"]]))
        with open(path, "w") as f:
            for r in rows: f.write(json.dumps(r) + "\n")
    print("wrote", path, f"({errors[0]} error rows this run)")

if __name__ == "__main__":
    main()
