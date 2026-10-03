"""Is "the user wants X" a separate direction in the model, and can we remove it without
removing the model's ability to update on real evidence?

For each model (Nimble merged, Qwen3.5-9B base) on data/derived/pressure_controls.jsonl:

1. Score every prompt by the next-token probability of the option letters (A/B/C/...),
   so we own the logits and can intervene. This is our own scorer, not Nimble's; the
   numbers are comparable across variants and interventions, not to run_nimble.py.
2. Geometry, no intervention: at every layer, the "preference direction" u_L is the mean
   of h(pref_tk) - h(base) at the last token over six preference phrasings. We report how
   far each test variant moves along u_L relative to base, and the cosine between u_L and
   each scenario's relevant_update shift (does a real fact travel the same road?).
3. Ablation: project u (from one layer) out of the residual stream at every layer, the
   way Arditi et al. (2024) remove the refusal direction. Directions are fit on 4/5 of
   the scenarios and tested on the held-out 1/5, so a test scenario's own prompts never
   shape the direction. The source layer is chosen per fold on training scenarios only.
   A random unit direction at the same layer is the control.

Outputs $OUT_DIR/<model>__pressure_controls.jsonl (one row per prompt x condition) and
$OUT_DIR/<model>__pressure_controls__geometry.json, OUT_DIR defaulting to results/steering.
scripts/analysis/steering.py turns them into tables.
Usage: python3 scripts/run/run_steering.py

Needs a 24 GB GPU; ~15 min per model on an L4. Set STEER_SMOKE=1 to run on a tiny
random model on CPU (checks the plumbing, numbers are meaningless).
"""
import json, os, sys, gc, time, random
import torch

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from prompts import load, result_path

DATA = "data/derived/pressure_controls.jsonl"
FIT_VARIANTS = [f"pref_t{k}" for k in range(6)]
TEST_VARIANTS = ["base", "pressure", "pref_target", "pref_target_1p", "mention_target", "pref_base",
                 "filler", "reframe", "relevant_update", "omission"]
FOLDS = 5
SMOKE = os.environ.get("STEER_SMOKE") == "1"
LETTERS = "ABCDEFG"

def prompt_text(s, variant):
    opts = "\n".join(f"{LETTERS[i]}) {s['option_text'][c]}" for i, c in enumerate(s["options"]))
    return (f"{s['prompts'][variant]}\n\n{s['question']} Answer with the letter of one option.\n{opts}")

def decoder_layers(model):
    # Qwen3.5 ships as a multimodal class; find the text decoder's layer list generically
    best = None
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.ModuleList) and name.endswith("layers"):
            if best is None or len(mod) > len(best[1]): best = (name, mod)
    return best[1]

class Scorer:
    def __init__(self, path):
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = self._load(path).eval()
        self.layers = decoder_layers(self.model)
        self.dev = next(self.model.parameters()).device
        self.letter_ids = []
        for L in LETTERS:
            ids = self.tok.encode(L, add_special_tokens=False)
            assert len(ids) == 1, f"letter {L} is not one token"
            self.letter_ids.append(ids[0])
        self.hooks = []

    def _load(self, path):
        import transformers
        import importlib.util
        dev = "cpu" if SMOKE else "cuda"
        kw = dict(dtype=torch.float32 if SMOKE else torch.bfloat16)
        if importlib.util.find_spec("accelerate"): kw["device_map"] = dev
        cfg = transformers.AutoConfig.from_pretrained(path)
        classes = ["AutoModelForCausalLM"]
        if cfg.model_type.startswith("qwen3_5"): classes.insert(0, "Qwen3_5ForConditionalGeneration")
        for cls in classes:
            if hasattr(transformers, cls):
                try:
                    m = getattr(transformers, cls).from_pretrained(path, **kw)
                    return m if "device_map" in kw else m.to(dev)
                except Exception as e:
                    print(f"  {cls} failed ({type(e).__name__}: {str(e)[:120]}); trying next")
        raise RuntimeError("could not load model")

    def encode(self, text):
        msgs = [{"role": "user", "content": text}]
        try:
            ids = self.tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False,
                                               return_tensors="pt", return_dict=False)
        except Exception:
            ids = self.tok(text, return_tensors="pt").input_ids
        if isinstance(ids, dict) or hasattr(ids, "input_ids"): ids = ids["input_ids"]
        return ids.to(self.dev)

    @torch.no_grad()
    def run(self, text, n_opts, hidden=False):
        out = self.model(input_ids=self.encode(text), output_hidden_states=hidden)
        logits = out.logits[0, -1, self.letter_ids[:n_opts]].float()
        probs = torch.softmax(logits, -1).tolist()
        hs = None
        if hidden:
            # hidden_states[0] is the embedding output; [l+1] is the output of layer l
            hs = torch.stack([h[0, -1].float().cpu() for h in out.hidden_states[1:]])
        return probs, hs

    def ablate(self, u):
        """Project unit vector u out of every layer's output, at every position."""
        self.clear()
        u = u.to(self.dev)
        def hook(_m, _i, out):
            h = out[0] if isinstance(out, tuple) else out
            uu = u.to(h.dtype)
            h = h - (h @ uu).unsqueeze(-1) * uu
            return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
        self.hooks = [l.register_forward_hook(hook) for l in self.layers]

    def clear(self):
        for h in self.hooks: h.remove()
        self.hooks = []

def unit(v):
    return v / (v.norm() + 1e-8)

def run_model(label, path, scen):
    t0 = time.time()
    sc = Scorer(path)
    n_layers = len(sc.layers)
    print(f"{label}: {n_layers} layers, loaded in {time.time()-t0:.0f}s")

    # pass 1: clean probs + last-token states for every prompt
    H, P = {}, {}
    for s in scen:
        for v in FIT_VARIANTS + TEST_VARIANTS:
            if v not in s["prompts"]: continue
            P[(s["id"], v)], H[(s["id"], v)] = sc.run(prompt_text(s, v), len(s["options"]), hidden=True)
    print(f"  clean pass done ({time.time()-t0:.0f}s)")

    def pref_dir(ids):
        d = [H[(i, v)] - H[(i, "base")] for i in ids for v in FIT_VARIANTS]
        return torch.stack(d).mean(0)                    # [layers, d_model]

    ids = [s["id"] for s in scen]
    # geometry on all scenarios (descriptive; no test-time use)
    U = pref_dir(ids)
    geo = {"layers": n_layers, "pref_norm": U.norm(dim=-1).tolist(), "proj": {}, "cos_ru": []}
    Uu = torch.stack([unit(U[l]) for l in range(n_layers)])
    for v in TEST_VARIANTS[1:]:
        # mean projection of (variant - base) on the unit preference direction, per layer
        geo["proj"][v] = torch.stack([((H[(i, v)] - H[(i, "base")]) * Uu).sum(-1)
                                      for i in ids if (i, v) in H]).mean(0).tolist()
    geo["cos_ru"] = torch.stack([torch.nn.functional.cosine_similarity(H[(i, "relevant_update")] - H[(i, "base")], U, dim=-1)
                                 for i in ids]).mean(0).tolist()

    rows = []
    def emit(s, v, cond, probs, extra=None):
        rows.append({"model": label, "condition": cond, "id": s["id"], "variant": v,
                     "choice": s["options"][max(range(len(probs)), key=probs.__getitem__)],
                     "probs": dict(zip(s["options"], probs)), **(extra or {})})
    for s in scen:
        for v in TEST_VARIANTS:
            if (s["id"], v) in P: emit(s, v, "clean", P[(s["id"], v)])

    # candidate source layers: every 4th from 1/4 to 3/4 depth (cheap enough, avoids edges)
    cands = list(range(n_layers // 4, 3 * n_layers // 4 + 1, max(1, n_layers // 16)))
    if SMOKE: cands = cands[:2]
    rng = random.Random(1684); order = ids[:]; rng.shuffle(order)
    folds = [order[k::FOLDS] for k in range(FOLDS)]
    byid = {s["id"]: s for s in scen}
    for k, test_ids in enumerate(folds):
        train = [i for i in ids if i not in test_ids]
        Ut = pref_dir(train)
        # choose the source layer on training scenarios: largest drop in P(target) on
        # the fitting phrasings, with base-prompt choices left unchanged
        best = None
        for L in cands:
            sc.ablate(unit(Ut[L]))
            drop, kept, n = 0.0, 0, 0
            for i in train[: max(4, len(train) // 3)]:      # subsample to keep it fast
                s = byid[i]; t = s["options"].index(s["pressure_target"])
                pb, _ = sc.run(prompt_text(s, "base"), len(s["options"]))
                kept += (max(range(len(pb)), key=pb.__getitem__) ==
                         max(range(len(pb)), key=P[(i, "base")].__getitem__))
                for v in FIT_VARIANTS[:2]:
                    pv, _ = sc.run(prompt_text(s, v), len(s["options"]))
                    drop += P[(i, v)][t] - pv[t]; n += 1
            score = drop / n if kept >= 0.8 * max(4, len(train) // 3) else -1e9
            if best is None or score > best[0]: best = (score, L)
        L = best[1]
        print(f"  fold {k}: source layer {L} (train dP drop {best[0]:.3f})")
        g = torch.Generator().manual_seed(1684 + k)
        rand = unit(torch.randn(Ut.shape[-1], generator=g))
        for cond, u in (("ablate_pref", unit(Ut[L])), ("ablate_random", rand)):
            sc.ablate(u)
            for i in test_ids:
                s = byid[i]
                for v in TEST_VARIANTS:
                    if v not in s["prompts"]: continue
                    probs, _ = sc.run(prompt_text(s, v), len(s["options"]))
                    emit(s, v, cond, probs, {"fold": k, "layer": L})
        sc.clear()
    print(f"  ablations done ({time.time()-t0:.0f}s)")
    del sc; gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache()
    return rows, geo

def smoke_model():
    from transformers import Qwen2Config, Qwen2ForCausalLM, PreTrainedTokenizerFast
    from tokenizers import Tokenizer, Regex, models, pre_tokenizers
    path = "/tmp/steer_smoke_model"
    if not os.path.exists(path):
        chars = sorted(set("".join(chr(c) for c in range(32, 127))))
        vocab = {c: i for i, c in enumerate(chars)}; vocab["[UNK]"] = len(vocab)
        tk = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]")); tk.pre_tokenizer = pre_tokenizers.Split(Regex("."), "isolated")
        tok = PreTrainedTokenizerFast(tokenizer_object=tk, unk_token="[UNK]")
        cfg = Qwen2Config(vocab_size=len(vocab), hidden_size=64, intermediate_size=128, num_hidden_layers=8,
                          num_attention_heads=4, num_key_value_heads=2)
        Qwen2ForCausalLM(cfg).save_pretrained(path); tok.save_pretrained(path)
    return path

if __name__ == "__main__":
    scen = load(DATA)
    if SMOKE:
        models = [("smoke", smoke_model())]; scen = scen[:6]
    else:
        models = [(f"bespoke-nimble-9b@{json.load(open('.cache/nimble-model.json'))['revision'][:8]}",
                   json.load(open(".cache/nimble-model.json"))["model_path"]),
                  ("qwen3.5-9b-base", json.load(open(".cache/base-model.json"))["model_path"])]
    only = os.environ.get("STEER_MODELS")      # e.g. "qwen" to run just the base model
    for label, path in models:
        if only and only not in label: continue
        rows, geo = run_model(label, path, scen)
        tag = label.split("@")[0]
        out = result_path(tag, "results/steering", DATA)
        with open(out, "w") as f:
            for r in rows: f.write(json.dumps(r) + "\n")
        json.dump(geo, open(out[:-len(".jsonl")] + "__geometry.json", "w"))
        print(f"wrote {out}")
    print("DONE - stop the instance now")
