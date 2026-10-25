"""Hugging Face ``transformers`` backend for the pinned generative base model (GPU box only).

Imports torch/transformers lazily so the CPU pipeline never needs them. Refuses to load a
model that is not pinned to a full commit hash unless ``allow_unpinned`` is set (which is
then recorded in the manifest).
"""

from __future__ import annotations

import platform
import re
import time
from typing import Any

from ..schema import Completion
from .base import GenRequest

SHA = re.compile(r"^[0-9a-f]{40}$")


class HFBackend:
    synthetic = False
    privileged = False

    def __init__(
        self,
        model_id: str,
        revision: str,
        *,
        dtype: str = "bfloat16",
        load_in_4bit: bool = False,
        max_batch: int = 8,
        chat_template_kwargs: dict[str, Any] | None = None,
        allow_unpinned: bool = False,
        model_class: str = "AutoModelForCausalLM",
    ) -> None:
        if not SHA.match(revision) and not allow_unpinned:
            raise ValueError(f"revision {revision!r} is not a 40-hex commit; pin the model")
        import torch
        import transformers
        from transformers import AutoTokenizer

        # Some checkpoints (e.g. Qwen3.5) register a conditional-generation class rather than
        # a causal-LM auto class; the class name is part of the pinned configuration.
        model_cls = getattr(transformers, model_class)
        self.model_class = model_class

        self.torch = torch
        self.model_id, self.revision = model_id, revision
        self.dtype, self.load_in_4bit, self.max_batch = dtype, load_in_4bit, max_batch
        self.chat_template_kwargs = chat_template_kwargs or {}
        self.allow_unpinned = allow_unpinned
        self.label = f"hf:{model_id}@{revision[:12]}" + ("-4bit" if load_in_4bit else "")
        kw: dict[str, Any] = {"revision": revision, "device_map": "auto"}
        if load_in_4bit:
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=getattr(torch, dtype),
            )
        else:
            kw["dtype"] = getattr(torch, dtype)
        self.tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        t0 = time.time()
        self.model = model_cls.from_pretrained(model_id, **kw)
        self.model.eval()
        self.load_seconds = time.time() - t0

    def info(self) -> dict[str, Any]:
        import transformers

        torch = self.torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        return {
            "kind": "hf",
            "model_id": self.model_id,
            "revision": self.revision,
            "model_class": self.model_class,
            "dtype": self.dtype,
            "load_in_4bit": self.load_in_4bit,
            "chat_template_kwargs": self.chat_template_kwargs,
            "allow_unpinned": self.allow_unpinned,
            "max_batch": self.max_batch,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "gpu": gpu,
            "python": platform.python_version(),
            "load_seconds": round(self.load_seconds, 1),
            "synthetic": False,
            "privileged": False,
        }

    def _batch(self, reqs: list[GenRequest]) -> list[Completion]:
        torch = self.torch
        g = reqs[0].gen
        prompts = [
            self.tok.apply_chat_template(
                [m.model_dump() for m in r.messages],
                tokenize=False,
                add_generation_prompt=True,
                **self.chat_template_kwargs,
            )
            for r in reqs
        ]
        enc = self.tok(prompts, return_tensors="pt", padding=True).to(self.model.device)
        torch.manual_seed(g.seed)
        sample = g.temperature > 0
        t0 = time.time()
        with torch.no_grad():
            out = self.model.generate(
                **enc,
                max_new_tokens=g.max_new_tokens,
                do_sample=sample,
                temperature=g.temperature if sample else None,
                top_p=g.top_p if sample else None,
                pad_token_id=self.tok.pad_token_id,
            )
        dt = (time.time() - t0) / len(reqs)
        res = []
        width = enc["input_ids"].shape[1]
        for i in range(len(reqs)):
            new = out[i, width:]
            n_new = int((new != self.tok.pad_token_id).sum())
            text = self.tok.decode(new, skip_special_tokens=True)
            n_prompt = int(enc["attention_mask"][i].sum())
            res.append(
                Completion(
                    text=text,
                    prompt_tokens=n_prompt,
                    completion_tokens=n_new,
                    latency_s=dt,
                    finish_reason="length" if n_new >= g.max_new_tokens else "stop",
                )
            )
        return res

    def generate(self, requests: list[GenRequest]) -> list[Completion]:
        """Batch requests that share decoding settings (the batch uses the first seed)."""
        out: list[Completion | None] = [None] * len(requests)
        groups: dict[tuple, list[int]] = {}
        for i, r in enumerate(requests):
            key = (r.gen.temperature, r.gen.top_p, r.gen.max_new_tokens)
            groups.setdefault(key, []).append(i)
        for idxs in groups.values():
            for start in range(0, len(idxs), self.max_batch):
                chunk = idxs[start : start + self.max_batch]
                try:
                    comps = self._batch([requests[i] for i in chunk])
                except Exception as exc:  # keep failures visible as missing outputs
                    comps = [
                        Completion(
                            text="",
                            prompt_tokens=0,
                            completion_tokens=0,
                            latency_s=0.0,
                            finish_reason="error",
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        for _ in chunk
                    ]
                for i, c in zip(chunk, comps, strict=True):
                    out[i] = c
        return [c for c in out if c is not None]
