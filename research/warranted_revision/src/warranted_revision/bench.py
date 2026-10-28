"""Inference speed benchmark on the GPU box (one fixed batch of real prompts).

Usage (on the GPU box, from ``research/warranted_revision``)::

    python -m warranted_revision.bench --config configs/gpu_smoke.json --label fallback --out bench-fallback.json

Renders the base-turn structured prompts for the first three smoke cases under three option
orders (9 prompts, one batch), decodes them greedily with the pinned model, and records
wall time, generated tokens, tokens per second, whether transformers fell back to its slow
reference kernels (and why the fast ones failed to import), and a hash of every output so
two runs can be checked for identical text.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import logging
import sys
import time
import traceback
from pathlib import Path

from . import prompts as P
from .backends.base import GenRequest
from .backends.hf import HFBackend
from .runner import PKG_ROOT, RunConfig, load_cases
from .schema import GenParams


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def kernel_imports() -> dict[str, str]:
    """Try the exact imports transformers attempts; keep the real error if one fails."""
    out = {}
    for mod in ("fla.ops.gated_delta_rule", "causal_conv1d"):
        try:
            importlib.import_module(mod)
            out[mod] = "ok"
        except Exception:  # noqa: BLE001 - we want whatever went wrong
            out[mod] = traceback.format_exc(limit=3)[-1500:]
    return out


def requests(cfg: RunConfig, max_new_tokens: int) -> list[GenRequest]:
    cases = load_cases(cfg)[:3]
    reqs = []
    for case in cases:
        for rep in range(3):
            order = P.option_order(case, rep, cfg.option_order_seed)
            msgs = tuple(P.conversation(case, order, P.STRUCTURED_FORMAT))
            reqs.append(
                GenRequest(
                    messages=msgs,
                    gen=GenParams(temperature=0.0, max_new_tokens=max_new_tokens, seed=0),
                )
            )
    return reqs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    raw = json.loads(args.config.read_text())
    raw["run_id"] = "bench"
    cfg = RunConfig.model_validate(raw)
    spec = next(s for s in cfg.systems if s.kind == "hf")
    cap = _Capture()
    logging.getLogger("transformers").addHandler(cap)
    imports = kernel_imports()
    backend = HFBackend(spec.name, **spec.params)
    reqs = requests(cfg, cfg.condition_config.max_new_tokens_structured)
    backend.generate(reqs[:1])  # warm-up (compilation, caches); not timed
    t0 = time.time()
    comps = backend.generate(reqs)
    secs = time.time() - t0
    new_tokens = sum(c.completion_tokens for c in comps)
    result = {
        "label": args.label,
        "model": backend.info(),
        "n_requests": len(reqs),
        "max_new_tokens": cfg.condition_config.max_new_tokens_structured,
        "seconds": round(secs, 2),
        "new_tokens": new_tokens,
        "tokens_per_second": round(new_tokens / secs, 2) if secs else None,
        "seconds_per_call": round(secs / len(reqs), 2),
        "hit_token_limit": sum(c.finish_reason == "length" for c in comps),
        "kernel_imports": imports,
        "fallback_warnings": sorted({m.split("`")[1] for m in cap.messages if "falling back" in m}),
        "output_sha256": [hashlib.sha256(c.text.encode()).hexdigest()[:16] for c in comps],
        "config": str(args.config.relative_to(PKG_ROOT))
        if args.config.is_relative_to(PKG_ROOT)
        else str(args.config),
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "model"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
