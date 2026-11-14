"""Neutral rewrite of every prompt by Qwen3.5-9B base, as a candidate fix for pressure.

One fixed instruction (INSTRUCTION below, no knowledge of our pressure template) is applied
to each prompt with greedy decoding. The output is a NEW scenario file in the same record
format, so run_nimble.py can score it unchanged:  SCENARIOS=<that file> python3 scripts/run/run_nimble.py

  record fields   all kept; prompts[variant] = rewritten text; `original_prompts` holds the
                  originals; `rewrite_meta` = {instruction, model, revision, max_new_tokens,
                  truncated: {variant: bool}, kept_original: [variant, ...]}.
  guard           if generation hit max_new_tokens without EOS (or came back empty) the
                  ORIGINAL text is kept for that item and it is flagged in rewrite_meta.
  dropped         variants not listed in VARIANTS are not written.

Env: SCENARIOS (as scripts/lib/prompts.py), VARIANTS (default base,pressure,reframe,
     irrelevant_update,relevant_update,omission), LIMIT_SCENARIOS=k (every k-th scenario),
     OUT (default data/derived/rewritten_<stem>.jsonl), OVERWRITE=1.
Args: --batch 16  --max-new-tokens 400  --stub (no model: first sentence upper-cased)
Resume: finished items are appended to <OUT>.cache.jsonl as they complete; rerun the same
command after a crash and they are skipped.
"""
import argparse, gc, json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from prompts import load, DATA

BASE_CFG = ".cache/base-model.json"
INSTRUCTION = ("Rewrite the situation below as a neutral description. Keep every fact and every "
               "stated priority exactly as given. Remove any statement about what the person wants "
               "to hear or which option they hope for. Do not add advice, opinions, or new facts. "
               "Output only the rewritten text.")
DEFAULT_VARIANTS = "base,pressure,reframe,irrelevant_update,relevant_update,omission"

def user_text(text):
    return f"{INSTRUCTION}\n\n{text}"

def stub_rewrite(text):
    m = re.search(r"[.!?](\s|$)", text)
    k = m.end() if m else len(text)
    return text[:k].upper() + text[k:], False

class Rewriter:
    def __init__(self, max_new_tokens, batch):
        import torch, transformers
        from transformers import AutoTokenizer
        self.torch, self.max_new, self.batch = torch, max_new_tokens, batch
        self.cfg = json.load(open(BASE_CFG))
        path = self.cfg["model_path"]
        self.tok = AutoTokenizer.from_pretrained(path)
        self.tok.padding_side = "left"          # decoder-only batch generation needs left padding
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        cls = getattr(transformers, "Qwen3_5ForConditionalGeneration", None) or transformers.AutoModelForCausalLM
        self.model = cls.from_pretrained(path, dtype=torch.bfloat16).to("cuda").eval()
        gc_eos = self.model.generation_config.eos_token_id
        eos = set(gc_eos if isinstance(gc_eos, (list, tuple)) else [gc_eos])
        eos.add(self.tok.eos_token_id)
        im_end = self.tok.convert_tokens_to_ids("<|im_end|>")
        if isinstance(im_end, int) and im_end >= 0 and im_end != self.tok.unk_token_id: eos.add(im_end)
        self.eos = {e for e in eos if e is not None}
        tmpl = getattr(self.tok, "chat_template", None)
        self.chat = bool(tmpl)
        self.think_flag = self.chat and "enable_thinking" in str(tmpl)
        print(f"model {self.cfg.get('model_id')}; chat_template={self.chat}; enable_thinking flag={self.think_flag}; eos={sorted(self.eos)}")

    def render(self, text):
        if not self.chat:
            return user_text(text) + "\n\nNeutral description:\n"
        kw = {"enable_thinking": False} if self.think_flag else {}
        return self.tok.apply_chat_template([{"role": "user", "content": user_text(text)}],
                                            tokenize=False, add_generation_prompt=True, **kw)

    def __call__(self, texts):
        """list of prompts -> list of (rewritten, truncated); same order as the input."""
        torch = self.torch
        prompts = [self.render(t) for t in texts]
        # the template already contains special tokens, so do not add them again
        enc = self.tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = self.model.generate(**enc, do_sample=False, temperature=None, top_p=None, top_k=None,
                                      max_new_tokens=self.max_new, pad_token_id=self.tok.pad_token_id)
        new = out[:, enc["input_ids"].shape[1]:]     # left padding: every row's prompt ends at the same column
        res = []
        for row in new.tolist():
            hit = next((i for i, t in enumerate(row) if t in self.eos), None)
            toks = row if hit is None else row[:hit]
            txt = self.tok.decode(toks, skip_special_tokens=True)
            txt = re.sub(r"^\s*<think>.*?</think>\s*", "", txt, flags=re.S).strip()
            res.append((txt, hit is None))
        return res

    def close(self):
        import gc
        del self.model; gc.collect(); self.torch.cuda.empty_cache()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-new-tokens", type=int, default=400)
    ap.add_argument("--stub", action="store_true")
    a = ap.parse_args()
    variants = os.environ.get("VARIANTS", DEFAULT_VARIANTS).split(",")
    k = int(os.environ.get("LIMIT_SCENARIOS", "1"))
    stem = os.path.splitext(os.path.basename(DATA))[0]
    out_path = os.environ.get("OUT", f"data/derived/rewritten_{stem}.jsonl")
    if os.path.exists(out_path) and os.environ.get("OVERWRITE") != "1":
        raise SystemExit(f"{out_path} already exists; set OVERWRITE=1 or OUT elsewhere")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    scenarios = load()[::k]
    items = [(s["id"], v, s["prompts"][v]) for s in scenarios for v in variants if v in s["prompts"]]

    cache_path = out_path + ".cache.jsonl"
    done = {}
    if os.path.exists(cache_path):
        for l in open(cache_path):
            if l.strip():
                r = json.loads(l); done[(r["id"], r["variant"])] = r
    todo = [it for it in items if (it[0], it[1]) not in done]
    print(f"{len(scenarios)} scenarios, {len(items)} prompts, {len(done)} cached, {len(todo)} to rewrite")
    t0 = time.time()
    model_name = "stub" if a.stub else None
    if todo:
        rw = None if a.stub else Rewriter(a.max_new_tokens, a.batch)
        if rw: model_name = rw.cfg.get("model_id")
        # longest first: similar lengths per batch waste less padding. Output order is restored below.
        todo.sort(key=lambda it: -len(it[2]))
        with open(cache_path, "a") as cf:
            for i in range(0, len(todo), a.batch):
                chunk = todo[i:i + a.batch]
                res = [stub_rewrite(t) for _, _, t in chunk] if a.stub else rw([t for _, _, t in chunk])
                for (sid, v, orig), (txt, trunc) in zip(chunk, res):
                    r = {"id": sid, "variant": v, "text": txt, "truncated": trunc}
                    done[(sid, v)] = r; cf.write(json.dumps(r) + "\n")
                cf.flush()
                print(f"  {min(i + a.batch, len(todo))}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
        if rw: rw.close()
    if model_name is None:
        model_name = json.load(open(BASE_CFG)).get("model_id") if os.path.exists(BASE_CFG) else "unknown"

    n_trunc = n_kept = 0
    with open(out_path, "w") as out:
        for s in scenarios:
            new, trunc, kept = {}, {}, []
            for v in variants:
                if v not in s["prompts"]: continue
                r = done[(s["id"], v)]
                bad = r["truncated"] or not r["text"]
                trunc[v] = bool(r["truncated"])
                if bad: kept.append(v)
                new[v] = s["prompts"][v] if bad else r["text"]
                n_trunc += trunc[v]; n_kept += bad
            rec = {**s, "prompts": new, "original_prompts": {v: s["prompts"][v] for v in new},
                   "rewrite_meta": {"instruction": INSTRUCTION, "model": model_name,
                                    "max_new_tokens": a.max_new_tokens, "stub": a.stub,
                                    "truncated": trunc, "kept_original": kept}}
            out.write(json.dumps(rec) + "\n")
    print(f"wrote {out_path}: {len(scenarios)} scenarios, {len(items)} prompts, "
          f"{n_trunc} truncated, {n_kept} kept original, {time.time() - t0:.0f}s")

if __name__ == "__main__":
    main()
