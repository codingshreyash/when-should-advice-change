"""CPU check of an open-weights goal-screen config against the Hugging Face Hub (no GPU, no weights).

Runs where the Hub is reachable (the GPU workflow's planning job on GitHub Actions)::

    python -m warranted_revision.model_check --config configs/goal_screen_mistral_nemo.json

It downloads only the tokenizer and model config at the pinned revision and checks:

* the revision exists (a placeholder revision prints the Hub's current ``main`` and fails);
* the model's own chat template renders every call shape of the protocol (first turn, free
  turn, decision turn, control) under all three system prompts, with the system prompt present
  exactly once and every turn present in order; where the template places the system prompt
  is recorded (some families put it before the last user turn);
* the longest rendered prompt plus ``max_tokens`` fits the model's context window;
* bf16 weights plus the KV cache for a full batch fit in the GPU's memory with headroom.

Exit status 0 only if every check passes. Needs ``transformers`` and ``jinja2``; a gated
repository additionally needs ``HF_TOKEN``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
import warnings
from pathlib import Path
from typing import Any

from . import goal_screen as gs
from .gpu_guard import SHA_RE
from .runner import PKG_ROOT

HUB = "https://huggingface.co/api/models"
GPU_GB = 48.0
HEADROOM = 0.85  # use at most this share of GPU memory


def _hub(path: str) -> dict[str, Any]:
    req = urllib.request.Request(f"{HUB}/{path}")
    if os.environ.get("HF_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def protocol_messages(cfg: gs.ScreenConfig) -> dict[str, list[dict[str, str]]]:
    """The longest instance of each call shape, so the template and length checks see the
    worst case the run will send."""
    items, controls = gs.load_screen_items(PKG_ROOT / cfg.items, PKG_ROOT / cfg.manifest)
    it = max(items, key=lambda i: len(gs.first_turn(i.base)) + len(i.followup))
    ctl = max(controls, key=lambda c: len(gs.first_turn(c.scenario, gs.WORDING["B"])))
    filler = " ".join(["x"] * 600)  # stands in for a long reply (no trailing whitespace)
    u1 = gs.first_turn(it.base)
    hist = [
        {"role": "user", "content": u1},
        {"role": "assistant", "content": "A1 " + filler},
        {"role": "user", "content": it.followup},
    ]
    return {
        "first": [{"role": "user", "content": u1}],
        "free": hist,
        "decision": hist
        + [
            {"role": "assistant", "content": "A2 " + filler},
            {"role": "user", "content": gs.decision_turn(it.base, "B")},
        ],
        "control": [{"role": "user", "content": gs.first_turn(ctl.scenario, gs.WORDING["B"])}],
    }


def check_template(tok: Any, cfg: gs.ScreenConfig, kwargs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"shapes": {}, "problems": []}
    longest = 0
    for cond, system in gs.SYSTEM_PROMPTS.items():
        for shape, msgs in protocol_messages(cfg).items():
            full = [{"role": "system", "content": system}] + msgs
            try:
                text = tok.apply_chat_template(
                    full, tokenize=False, add_generation_prompt=True, **kwargs
                )
            except Exception as exc:  # noqa: BLE001 - reported as a failed check
                out["problems"].append(f"{cond}/{shape}: template raised {exc!r}")
                continue
            if text.count(system) != 1:
                out["problems"].append(
                    f"{cond}/{shape}: system prompt appears {text.count(system)}x"
                )
            # Templates may strip whitespace around turns; compare stripped content and name
            # the first turn that cannot be found in order.
            pos = 0
            for i, m in enumerate(msgs):
                body = m["content"].strip()
                at = text.find(body, pos)
                if at < 0:
                    seen = "elsewhere" if body in text else "absent"
                    out["problems"].append(
                        f"{cond}/{shape}: turn {i} ({m['role']}) {seen}: {body[:40]!r}"
                    )
                    break
                pos = at + len(body)
            users = [text.find(m["content"]) for m in msgs if m["role"] == "user"]
            sys_at = text.find(system)
            if sys_at < users[0]:
                where = "before_first_user"
            elif len(users) > 1 and users[-2] < sys_at < users[-1]:
                where = "before_last_user"
            else:
                where = "other"
            n = len(tok(text, add_special_tokens=False)["input_ids"])
            longest = max(longest, n)
            if cond == "N":
                out["shapes"][shape] = {
                    "system_position": where,
                    "prompt_tokens": n,
                    "tail": text[-40:],
                }
    out["longest_prompt_tokens"] = longest
    return out


def memory(conf: Any, n_params: int | None, cfg: gs.ScreenConfig, longest: int) -> dict[str, Any]:
    text = getattr(conf, "text_config", None) or conf
    layers = text.num_hidden_layers
    kv_heads = getattr(text, "num_key_value_heads", text.num_attention_heads)
    head_dim = getattr(text, "head_dim", None) or text.hidden_size // text.num_attention_heads
    kv_per_token = 2 * layers * kv_heads * head_dim * 2  # k and v, bf16
    batch = cfg.system.params.get("max_batch", 1)
    tokens = batch * (longest + max(cfg.max_tokens_free, cfg.max_tokens_decision))
    weights_gb = (n_params or 0) * 2 / 1e9
    kv_gb = kv_per_token * tokens / 1e9  # upper bound: full attention in every layer
    return {
        "params": n_params,
        "weights_gb_bf16": round(weights_gb, 1),
        "kv_cache_gb_full_batch": round(kv_gb, 1),
        "max_batch": batch,
        "fits": n_params is not None and weights_gb + kv_gb <= HEADROOM * GPU_GB,
        "context_window": getattr(text, "max_position_embeddings", None),
    }


def check(cfg_path: Path) -> dict[str, Any]:
    cfg = gs.load_config(cfg_path)
    if cfg.system.kind != "hf":
        return {"config": str(cfg_path), "skipped": "not an open-weights config", "ok": True}
    name, params = cfg.system.name, cfg.system.params
    rev = params.get("revision", "")
    meta = _hub(name)
    res: dict[str, Any] = {
        "config": str(cfg_path),
        "model": name,
        "pinned_revision": rev,
        "hub_main_sha": meta.get("sha"),
        "gated": meta.get("gated"),
        "license": (meta.get("cardData") or {}).get("license"),
        "problems": [],
    }
    if not SHA_RE.match(rev):
        res["problems"].append(f"revision {rev!r} is not pinned; Hub main is {meta.get('sha')}")
        res["ok"] = False
        return res
    try:
        _hub(f"{name}/revision/{rev}")
    except Exception as exc:  # noqa: BLE001
        res["problems"].append(f"pinned revision not found: {exc}")
    from transformers import AutoConfig, AutoTokenizer

    warned: list[str] = []

    class _Catch(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            warned.append(record.getMessage())

    catcher = _Catch(logging.WARNING)
    logging.getLogger("transformers").addHandler(catcher)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tok = AutoTokenizer.from_pretrained(
                name, revision=rev, **params.get("tokenizer_kwargs", {})
            )
            conf = AutoConfig.from_pretrained(name, revision=rev)
        warned += [str(w.message) for w in caught]
    except Exception as exc:  # noqa: BLE001 - e.g. a gated repo without HF_TOKEN
        res["problems"].append(f"could not load tokenizer/config: {type(exc).__name__}: {exc}")
        res["ok"] = False
        return res
    finally:
        logging.getLogger("transformers").removeHandler(catcher)
    bad_tok = [w for w in warned if "incorrect tokenization" in w or "incorrect regex" in w]
    res["tokenizer_warnings"] = warned
    if bad_tok:
        res["problems"].append(f"tokenizer warns of incorrect tokenization: {bad_tok[0][:160]}")
    t = check_template(tok, cfg, params.get("chat_template_kwargs", {}))
    res["template"] = t
    res["problems"] += t["problems"]
    n_params = (meta.get("safetensors") or {}).get("total")
    res["memory"] = memory(conf, n_params, cfg, t["longest_prompt_tokens"])
    if not res["memory"]["fits"]:
        res["problems"].append(f"memory estimate does not fit {HEADROOM:.0%} of {GPU_GB} GB")
    ctx = res["memory"]["context_window"]
    need = t["longest_prompt_tokens"] + max(cfg.max_tokens_free, cfg.max_tokens_decision)
    if ctx is not None and need > ctx:
        res["problems"].append(f"longest prompt + max_tokens {need} > context {ctx}")
    res["ok"] = not res["problems"]
    return res


def _hub_file(repo: str, rev: str, name: str) -> dict[str, Any]:
    req = urllib.request.Request(f"https://huggingface.co/{repo}/resolve/{rev}/{name}")
    if os.environ.get("HF_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['HF_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def check_decision_procedure(cfg_path: Path) -> dict[str, Any]:
    """Both pinned revisions exist; the adapter's ``schema_config.json`` names the
    preregistered base; the base's chat template (thinking off) renders the longest
    conversational prompt, which fits the context with ``max_new_tokens``."""
    from . import decision_procedure as dp

    cfg = dp.load_config(cfg_path)
    res: dict[str, Any] = {"config": str(cfg_path), "model": cfg.base.model_id, "problems": []}
    for pin in (cfg.base, cfg.nimble):
        try:
            _hub(f"{pin.model_id}/revision/{pin.revision}")
        except Exception as exc:  # noqa: BLE001
            res["problems"].append(f"{pin.model_id}@{pin.revision[:8]} not found: {exc}")
    try:
        contract = _hub_file(cfg.nimble.model_id, cfg.nimble.revision, "schema_config.json")
        res["nimble_contract"] = {k: contract.get(k) for k in ("model", "revision", "max_length")}
        dp.check_contract(contract, cfg)
    except Exception as exc:  # noqa: BLE001
        res["problems"].append(f"contract: {type(exc).__name__}: {exc}")
    from transformers import AutoConfig, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(cfg.base.model_id, revision=cfg.base.revision)
    conf = AutoConfig.from_pretrained(cfg.base.model_id, revision=cfg.base.revision)
    items = [i for i in dp.build_items(cfg) if i.procedure != "scorer"]
    longest = max(items, key=lambda i: len(i.text))
    text = tok.apply_chat_template(
        [{"role": "user", "content": longest.text}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    n = len(tok(text)["input_ids"])
    ctx = getattr(getattr(conf, "text_config", conf), "max_position_embeddings", None)
    res["template"] = {
        "longest_prompt_tokens": n,
        "context_window": ctx,
        "prompt_once": text.count(longest.text) == 1,
        "ends_with_empty_think": text.rstrip().endswith("</think>"),
    }
    if text.count(longest.text) != 1:
        res["problems"].append("the chat template does not contain the prompt exactly once")
    max_new = max(a.max_new_tokens or 0 for a in cfg.arms)
    if ctx is not None and n + max_new > ctx:
        res["problems"].append(f"longest prompt {n} + {max_new} > context {ctx}")
    res["ok"] = not res["problems"]
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    raw = json.loads(args.config.read_text())
    if raw.get("experiment") == "decision_procedure":
        res = check_decision_procedure(args.config)
        text = json.dumps(res, indent=1)
        if args.out:
            args.out.write_text(text + "\n")
        print(text)
        print(f"[model_check] {'OK' if res['ok'] else 'FAILED'} {res['model']}")
        return 0 if res["ok"] else 1
    if raw.get("experiment") != "goal_screen":
        print(f"[model_check] skipped: {args.config} is not a goal-screen config")
        return 0
    res = check(args.config)
    text = json.dumps(res, indent=1)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)
    print(f"[model_check] {'OK' if res['ok'] else 'FAILED'} {res.get('model')}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
