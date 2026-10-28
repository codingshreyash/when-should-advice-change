"""CS 1684 decision-procedure experiment: four read-outs of the same Qwen3.5-9B weights.

Preregistered in ``docs/PREREGISTRATION_DECISION_PROCEDURES.md`` (repository root). Arms:

* A: base weights through Nimble's candidate scorer (decision only)
* B: base weights, chat generation, constrained prompt (one code)
* C: base weights, chat generation, conversational prompt (paragraph, code on last line)
* D: Bespoke-Nimble adapter merged into the same base, through the same scorer as A

Prompts, schemas and option orders come from the original project's ``scripts/lib/prompts.py``
(loaded by path, never copied), so every arm sees exactly what the earlier runners showed.
The option order is seeded per scenario and sample only: within (scenario, sample) every
variant and every arm sees the same order.

Usage (the GPU box runs these from ``gpu/remote_job.sh``)::

    python -m warranted_revision.decision_procedure run --config C --dry-run    # plan only
    python -m warranted_revision.decision_procedure run --config C --preflight  # on-box gate input
    python -m warranted_revision.decision_procedure run --config C              # full run
    python -m warranted_revision.decision_procedure gate --run DIR --remaining-min N
    python -m warranted_revision.decision_procedure summary --run DIR           # counts only
    python -m warranted_revision.decision_procedure lock [--write]              # frozen-file hashes

Model code (torch, transformers, Nimble) is imported only by the real backends, on the box.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

PKG_ROOT = Path(__file__).resolve().parents[2]  # research/warranted_revision
LOCK = PKG_ROOT / "configs" / "decision_procedure_lock.json"
#: Repository files the experiment reads; the GPU bundle carries them under ``cs1684/``.
CS1684_FILES = (
    "scripts/lib/prompts.py",
    "data/derived/pressure_controls.jsonl",
    "data/scenarios/career_pilot.jsonl",
    "data/scenarios/career_v2.jsonl",
    "docs/PREREGISTRATION_DECISION_PROCEDURES.md",
)
#: Blind-label files, bundled when they exist (they are produced after this code is frozen).
CS1684_LABELS = ("data/labeling/career_pilot_blind.jsonl", "data/labeling/career_v2_blind.jsonl")
VARIANTS = (
    "base",
    "pressure",
    "reframe",
    "relevant_update",
    "subthreshold_update",
    "irrelevant_update",
    "omission",
    "mention_target",
)
#: Load order on the box: one model in memory at a time.
ARM_ORDER = ("D", "A", "B", "C")
#: On-box preflight gate thresholds (preregistration section 7) and runtime margin.
MIN_PARSE_OVERALL = 0.95
MIN_PARSE_VARIANT = 0.90
RUNTIME_MARGIN = 1.5


class GateError(RuntimeError):
    pass


def cs1684_root() -> Path:
    """The bundle's ``cs1684/`` copy on the GPU box, else the repository root."""
    bundled = PKG_ROOT / "cs1684"
    return bundled if bundled.is_dir() else PKG_ROOT.parents[1]


def resolve(rel: str) -> Path:
    """A repository-relative path, wherever this package is running from."""
    prefix = "research/warranted_revision/"
    if rel.startswith(prefix):
        return PKG_ROOT / rel[len(prefix) :]
    return cs1684_root() / rel


# --------------------------------------------------------------------------- config


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Arm(Strict):
    name: Literal["A", "B", "C", "D"]
    weights: Literal["base", "nimble"]
    procedure: Literal["scorer", "constrained", "conversational"]
    max_new_tokens: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _shape(self) -> Arm:
        generative = self.procedure != "scorer"
        if generative != (self.max_new_tokens is not None):
            raise ValueError("generative arms need max_new_tokens; scorer arms take none")
        if generative and self.weights != "base":
            raise ValueError("only the base weights are run generatively")
        return self


class Pinned(Strict):
    model_id: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")


class NimblePin(Pinned):
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    code_repo: str = "https://github.com/bespokelabsai/nimble.git"


class Preflight(Strict):
    scenario_ids: list[str] = Field(min_length=1)
    samples: int = Field(default=1, ge=1)


class DPConfig(Strict):
    experiment: Literal["decision_procedure"]
    run_id: str
    label: str = ""
    #: The technical pilot reports counts only; the analysis refuses it.
    technical_pilot: bool = False
    scenarios: str = "data/derived/pressure_controls.jsonl"
    scenario_ids: list[str] | None = None  # None = every scenario in the file
    variants: list[str] = list(VARIANTS)
    samples: int = Field(ge=1)
    option_order_seed: int
    arms: list[Arm]
    base: Pinned
    nimble: NimblePin
    scorer_temperature: float = Field(default=1.0, gt=0)
    max_batch: int = Field(default=8, ge=1)
    max_calls: int
    preflight: Preflight | None = None
    shard: str = "1/1"
    out_root: str | None = None

    @model_validator(mode="after")
    def _arms(self) -> DPConfig:
        names = [a.name for a in self.arms]
        if len(set(names)) != len(names):
            raise ValueError("arm names must be unique")
        if set(self.variants) - set(VARIANTS):
            raise ValueError(f"unknown variants {sorted(set(self.variants) - set(VARIANTS))}")
        if self.shard != "1/1":
            raise ValueError("the decision-procedure run is not sharded")
        return self


def load_config(path: Path | str) -> DPConfig:
    return DPConfig.model_validate(json.loads(Path(path).read_text()))


# --------------------------------------------------------------------------- prompts and items


def load_prompts_module(seed: int) -> ModuleType:
    """Import the original project's prompts.py by path, with confirmatory ordering settings.

    ``ordered_scenario`` reads RANDOMIZE_OPTIONS / OPTION_ORDER_SEED at call time; the legacy
    per-variant ordering switch must not be set.
    """
    if os.environ.get("ORDER_PER_VARIANT"):
        raise GateError("ORDER_PER_VARIANT is set; it reproduces the old per-variant ordering")
    os.environ["RANDOMIZE_OPTIONS"] = "1"
    os.environ["OPTION_ORDER_SEED"] = str(seed)
    path = resolve("scripts/lib/prompts.py")
    spec = importlib.util.spec_from_file_location("cs1684_prompts", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@dataclass(frozen=True)
class Item:
    arm: str
    id: str
    variant: str
    sample: int
    option_order: tuple[str, ...]
    text: str  # scorer context, or the chat user message
    schema: dict[str, Any] | None  # scorer arms only
    max_new_tokens: int | None
    weights: str
    procedure: str


def load_scenarios(cfg: DPConfig, ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in resolve(cfg.scenarios).read_text().splitlines() if line]
    keep = list(ids) if ids is not None else cfg.scenario_ids
    if keep is not None:
        by_id = {s["id"]: s for s in rows}
        missing = [i for i in keep if i not in by_id]
        if missing:
            raise ValueError(f"scenario ids not in {cfg.scenarios}: {missing}")
        rows = [by_id[i] for i in keep]
    return rows


def build_items(cfg: DPConfig, *, preflight: bool = False) -> list[Item]:
    """Every call of the run, in arm load order, then scenario, sample, variant."""
    pm = load_prompts_module(cfg.option_order_seed)
    if preflight:
        if cfg.preflight is None:
            raise ValueError("config has no preflight section")
        scen, samples = load_scenarios(cfg, cfg.preflight.scenario_ids), cfg.preflight.samples
    else:
        scen, samples = load_scenarios(cfg), cfg.samples
    arms = sorted(cfg.arms, key=lambda a: ARM_ORDER.index(a.name))
    items = []
    for arm in arms:
        for s in scen:
            for k in range(samples):
                for v in cfg.variants:
                    if v not in s["prompts"]:
                        raise ValueError(f"{s['id']} has no {v} prompt")
                    ordered = pm.ordered_scenario(s, v, k)
                    if arm.procedure == "scorer":
                        text, schema = s["prompts"][v], pm.nimble_schema(ordered)
                    elif arm.procedure == "constrained":
                        text, schema = pm.chat_prompt_constrained(ordered, v), None
                    else:
                        text, schema = pm.chat_prompt_conversational(ordered, v), None
                    items.append(
                        Item(
                            arm=arm.name,
                            id=s["id"],
                            variant=v,
                            sample=k,
                            option_order=tuple(ordered["options"]),
                            text=text,
                            schema=schema,
                            max_new_tokens=arm.max_new_tokens,
                            weights=arm.weights,
                            procedure=arm.procedure,
                        )
                    )
    return items


def plan(cfg: DPConfig, *, preflight: bool = False) -> dict[str, Any]:
    items = build_items(cfg, preflight=preflight)
    per_arm = Counter(i.arm for i in items)
    gen_batches = {
        a: -(-n // cfg.max_batch)
        for a, n in per_arm.items()
        if next(x for x in cfg.arms if x.name == a).procedure != "scorer"
    }
    return {"calls": len(items), "per_arm": dict(per_arm), "generation_batches": gen_batches}


#: Planning estimates for the controller's budget (seconds; deliberately conservative). The
#: on-box gate replaces them with measured times before the full run starts.
EST_PREPARE_S = 1800  # environment, 9B download, merge, two saves
EST_LOAD_S = 120  # one model load
EST_SCORER_CALL_S = 0.3
EST_GEN_BATCH_S = {"constrained": 3.0, "conversational": 15.0}


def estimate_seconds(cfg: DPConfig) -> dict[str, float]:
    """Expected on-box seconds after boot: preparation, then (preflight +) run."""

    def one(preflight: bool) -> float:
        p = plan(cfg, preflight=preflight)
        t = 0.0
        for a in cfg.arms:
            n = p["per_arm"].get(a.name, 0)
            t += EST_LOAD_S
            if a.procedure == "scorer":
                t += n * EST_SCORER_CALL_S
            else:
                t += -(-n // cfg.max_batch) * EST_GEN_BATCH_S[a.procedure]
        return t

    pre = one(True) if cfg.preflight is not None and not cfg.technical_pilot else 0.0
    calls = plan(cfg)["calls"] + (plan(cfg, preflight=True)["calls"] if pre else 0)
    total = EST_PREPARE_S + pre + one(False)
    return {"calls": calls, "seconds": total, "seconds_per_call": total / calls}


# --------------------------------------------------------------------------- parsing


def parse_strict(text: str, options: Iterable[str]) -> str | None:
    """The last line that is exactly one offered code (punctuation around it allowed), else
    None. This is ``choice_strict`` in ``scripts/run/run_chat.py``, the project's strict rule;
    a test checks the two agree."""
    import re

    for line in reversed(text.strip().splitlines()):
        for o in options:
            if re.fullmatch(rf"\W*{re.escape(o)}\W*", line.strip()):
                return o
    return None


# --------------------------------------------------------------------------- backends


class Scorer(Protocol):
    def score(self, context: str, schema: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class GenOut:
    text: str
    completion_tokens: int
    finish_reason: str  # stop | length | error
    error: str | None = None


class Generator(Protocol):
    def generate(self, prompts: list[str], max_new_tokens: int) -> list[GenOut]: ...


@dataclass
class Backends:
    """Factories, so only one model is in memory at a time. ``release`` frees GPU memory."""

    scorer: Callable[[str], Scorer]  # weights -> scorer
    generator: Callable[[], Generator]
    release: Callable[[], None] = lambda: None
    info: Callable[[], dict[str, Any]] = lambda: {}


class NimbleScorer:
    """Nimble's ``CudaCandidateScorer`` on a merged checkpoint written by the setup script."""

    def __init__(self, model_json: Path, temperature: float) -> None:
        from nimble.scoring.cuda_scorer import CudaCandidateScorer  # type: ignore[import-not-found]

        cfg = json.loads(model_json.read_text())
        self.scorer = CudaCandidateScorer(
            model_path=cfg["model_path"],
            model_id=cfg["model_id"],
            revision=cfg["revision"],
            max_input_tokens=cfg.get("max_input_tokens", 2048),
            temperature=temperature,
        )

    def score(self, context: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self.scorer.score(context, schema)


class HFChatGenerator:
    """Greedy chat generation from the saved base weights, thinking off, left-padded batches."""

    def __init__(self, model_path: str, max_batch: int) -> None:
        import torch
        import transformers
        from transformers import AutoTokenizer

        self.torch = torch
        self.max_batch = max_batch
        self.tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        cls = transformers.Qwen3_5ForConditionalGeneration
        self.model = cls.from_pretrained(
            model_path, local_files_only=True, dtype=torch.bfloat16, device_map="cuda"
        ).eval()

    def _batch(self, prompts: list[str], max_new_tokens: int) -> list[GenOut]:
        rendered = [
            self.tok.apply_chat_template(
                [{"role": "user", "content": p}],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            for p in prompts
        ]
        enc = self.tok(rendered, return_tensors="pt", padding=True).to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **enc,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=self.tok.pad_token_id,
            )
        width = enc["input_ids"].shape[1]
        res = []
        for i in range(len(prompts)):
            new = out[i, width:]
            n = int((new != self.tok.pad_token_id).sum())
            text = self.tok.decode(new, skip_special_tokens=True)
            res.append(GenOut(text, n, "length" if n >= max_new_tokens else "stop"))
        return res

    def generate(self, prompts: list[str], max_new_tokens: int) -> list[GenOut]:
        out: list[GenOut] = []
        for start in range(0, len(prompts), self.max_batch):
            chunk = prompts[start : start + self.max_batch]
            try:
                out += self._batch(chunk, max_new_tokens)
            except Exception as exc:  # noqa: BLE001 - recorded as errors, counted by the gate
                out += [GenOut("", 0, "error", f"{type(exc).__name__}: {exc}") for _ in chunk]
        return out


def real_backends(cfg: DPConfig, cache: Path) -> Backends:
    """Backends over the checkpoints written by ``gpu/decision_procedure_setup.sh``."""
    held: dict[str, Any] = {}

    def release() -> None:
        import gc

        import torch

        held.clear()
        gc.collect()
        torch.cuda.empty_cache()

    def scorer(weights: str) -> Scorer:
        release()
        held["m"] = NimbleScorer(cache / f"{weights}-model.json", cfg.scorer_temperature)
        return held["m"]

    def generator() -> Generator:
        release()
        path = json.loads((cache / "base-model.json").read_text())["model_path"]
        held["m"] = HFChatGenerator(path, cfg.max_batch)
        return held["m"]

    def info() -> dict[str, Any]:
        import torch
        import transformers

        return {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "models": {
                w: json.loads((cache / f"{w}-model.json").read_text()) for w in ("base", "nimble")
            },
        }

    return Backends(scorer=scorer, generator=generator, release=release, info=info)


def check_contract(contract: dict[str, Any], cfg: DPConfig) -> None:
    """Nimble's ``schema_config.json`` must name the preregistered base weights, so arms A-C
    run exactly the base that arm D's adapter was trained on."""
    got = (contract.get("model"), contract.get("revision"))
    want = (cfg.base.model_id, cfg.base.revision)
    if got != want:
        raise GateError(f"Nimble {cfg.nimble.revision[:8]} names base {got}, preregistered {want}")


def prepare_models(cfg: DPConfig, cache: Path) -> None:
    """Download the pinned adapter and base, merge, and save both checkpoints (GPU box only).

    Writes ``<cache>/base-model.json`` and ``<cache>/nimble-model.json`` in the format
    Nimble's scorer takes. Same steps as ``scripts/run/brev_setup.sh``, plus the contract check.
    """
    import torch
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    hub = cache / "huggingface" / "hub"
    snap = Path(snapshot_download(cfg.nimble.model_id, revision=cfg.nimble.revision, cache_dir=hub))
    contract = json.loads((snap / "schema_config.json").read_text())
    check_contract(contract, cfg)
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        cfg.base.model_id,
        revision=cfg.base.revision,
        dtype=torch.bfloat16,
        device_map="cpu",
        cache_dir=hub,
    )
    tok = AutoTokenizer.from_pretrained(snap)
    paths = {"base": cache / "models" / "base-9b", "nimble": cache / "models" / "nimble-9b"}
    base.save_pretrained(paths["base"])
    tok.save_pretrained(paths["base"])
    merged = PeftModel.from_pretrained(base, snap).merge_and_unload(safe_merge=True)
    merged.save_pretrained(paths["nimble"])
    tok.save_pretrained(paths["nimble"])
    for w, pin in (("base", cfg.base), ("nimble", cfg.nimble)):
        (cache / f"{w}-model.json").write_text(
            json.dumps(
                {
                    "model_path": str(paths[w].resolve()),
                    "model_id": pin.model_id,
                    "revision": pin.revision,
                    "max_input_tokens": contract.get("max_length", 2048),
                },
                indent=1,
            )
        )


# --------------------------------------------------------------------------- run


def model_label(cfg: DPConfig, weights: str) -> str:
    pin = cfg.nimble if weights == "nimble" else cfg.base
    return f"{pin.model_id}@{pin.revision[:8]}"


def run(
    cfg: DPConfig,
    backends: Backends,
    out_dir: Path,
    *,
    preflight: bool = False,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Make every planned call and write ``calls.jsonl`` and ``manifest.json``.

    A failed call is recorded with its error (never retried or dropped), so the gate and the
    analysis see it. Returns the manifest.
    """
    check_lock()
    check_config_locked(cfg)
    items = build_items(cfg, preflight=preflight)
    if len(items) > cfg.max_calls:
        raise GateError(f"{len(items)} calls planned > max_calls {cfg.max_calls}")
    out_dir.mkdir(parents=True, exist_ok=True)
    calls = out_dir / "calls.jsonl"
    if calls.exists():
        raise GateError(f"{calls} exists; refusing to overwrite")
    arms = {a.name: a for a in cfg.arms}
    t_start = clock()
    timing: dict[str, dict[str, float]] = {}
    with calls.open("w") as f:
        for arm_name in [a for a in ARM_ORDER if a in arms]:
            arm = arms[arm_name]
            todo = [i for i in items if i.arm == arm_name]
            t0 = clock()
            if arm.procedure == "scorer":
                scorer = backends.scorer(arm.weights)
                t_loaded = clock()
                for it in todo:
                    f.write(json.dumps(_score_row(cfg, it, scorer)) + "\n")
            else:
                gen = backends.generator()
                t_loaded = clock()
                outs = gen.generate([i.text for i in todo], arm.max_new_tokens or 1)
                if len(outs) != len(todo):
                    raise GateError(f"arm {arm_name}: {len(outs)} outputs for {len(todo)} prompts")
                for it, o in zip(todo, outs, strict=True):
                    f.write(json.dumps(_gen_row(cfg, it, o)) + "\n")
            f.flush()
            t1 = clock()
            timing[arm_name] = {
                "calls": len(todo),
                "load_s": round(t_loaded - t0, 2),
                "call_s": round(t1 - t_loaded, 2),
            }
    backends.release()
    manifest = {
        "run_id": cfg.run_id,
        "preflight": preflight,
        "config": cfg.model_dump(),
        "planned_calls": len(items),
        "timing": timing,
        "elapsed_s": round(clock() - t_start, 2),
        "git_sha": os.environ.get("WREV_GIT_SHA"),
        "lock": json.loads(LOCK.read_text()) if LOCK.exists() else None,
        "backend": backends.info(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def _base_row(cfg: DPConfig, it: Item) -> dict[str, Any]:
    return {
        "arm": it.arm,
        "model": model_label(cfg, it.weights),
        "procedure": it.procedure,
        "id": it.id,
        "variant": it.variant,
        "sample": it.sample,
        "option_order": list(it.option_order),
        "prompt_sha256": hashlib.sha256(it.text.encode()).hexdigest()[:16],
    }


def _score_row(cfg: DPConfig, it: Item, scorer: Scorer) -> dict[str, Any]:
    row = _base_row(cfg, it)
    try:
        r = scorer.score(it.text, it.schema or {})
        field = r["fields"]["decision"]
        choice = r["output"]["decision"]
        if choice not in it.option_order:
            raise ValueError(f"scorer returned {choice!r}, not an offered option")
        row.update(
            choice=choice,
            choice_strict=choice,
            probs=field["scores"],
            logits=field.get("logits"),
            prompt_tokens=field.get("prompt_token_count"),
            temperature=r.get("temperature"),
            revision=r.get("revision"),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        row.update(choice=None, choice_strict=None, error=f"{type(exc).__name__}: {exc}")
    return row


def _gen_row(cfg: DPConfig, it: Item, o: GenOut) -> dict[str, Any]:
    row = _base_row(cfg, it)
    strict = parse_strict(o.text, it.option_order) if o.finish_reason != "error" else None
    row.update(
        choice=strict,
        choice_strict=strict,
        text=o.text,
        completion_tokens=o.completion_tokens,
        finish_reason=o.finish_reason,
        error=o.error,
    )
    return row


# --------------------------------------------------------------------------- gate and summary


def read_rows(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (run_dir / "calls.jsonl").read_text().splitlines() if x]


def summarize(run_dir: Path) -> dict[str, Any]:
    """Counts only: calls, errors, parse rates, truncations. No choices, no model text."""
    man = json.loads((run_dir / "manifest.json").read_text())
    rows = read_rows(run_dir)
    by_arm: dict[str, Any] = {}
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm]
        per_var: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in rs:
            per_var[r["variant"]][0] += r["choice_strict"] is not None
            per_var[r["variant"]][1] += 1
        parsed = sum(v[0] for v in per_var.values())
        by_arm[arm] = {
            "calls": len(rs),
            "errors": sum(r.get("error") is not None for r in rs),
            "error_types": dict(
                Counter((r["error"] or "").split(":")[0] for r in rs if r.get("error"))
            ),
            "parsed": parsed,
            "parse_rate": round(parsed / len(rs), 4) if rs else None,
            "parse_rate_by_variant": {v: round(a / b, 4) for v, (a, b) in sorted(per_var.items())},
            "truncated": sum(r.get("finish_reason") == "length" for r in rs),
        }
    return {
        "run_id": man["run_id"],
        "preflight": man["preflight"],
        "planned_calls": man["planned_calls"],
        "actual_calls": len(rows),
        "timing": man["timing"],
        "elapsed_s": man["elapsed_s"],
        "by_arm": by_arm,
    }


def gate(run_dir: Path, remaining_min: float, full_cfg: DPConfig | None = None) -> dict[str, Any]:
    """Preflight gate for the full run (preregistration section 7, applied to the preflight).

    Passes only if every planned call was made, scorer arms had no errors, each generative
    arm parsed strictly at >= 95% overall and >= 90% in every variant, and the measured time
    per call projects the full run (x RUNTIME_MARGIN, model loads included) within the
    minutes left. Raises GateError listing every failure; writes ``gate.json`` either way.
    """
    s = summarize(run_dir)
    man = json.loads((run_dir / "manifest.json").read_text())
    cfg = full_cfg or DPConfig.model_validate(man["config"])
    full = plan(cfg)["per_arm"]
    projected_s = 0.0
    for arm, t in s["timing"].items():
        per_call = t["call_s"] / max(1, t["calls"])
        projected_s += t["load_s"] + per_call * full.get(arm, 0)
    s["projected_full_run_min"] = round(projected_s / 60, 1)
    s["remaining_min"] = round(remaining_min, 1)
    arms = {a.name: a for a in cfg.arms}
    problems = []
    if s["actual_calls"] != s["planned_calls"]:
        problems.append(f"made {s['actual_calls']} of {s['planned_calls']} planned calls")
    for arm, a in s["by_arm"].items():
        if arms[arm].procedure == "scorer":
            if a["errors"]:
                problems.append(f"arm {arm}: {a['errors']} scorer errors {a['error_types']}")
            continue
        if a["parse_rate"] is None or a["parse_rate"] < MIN_PARSE_OVERALL:
            problems.append(f"arm {arm}: strict parse {a['parse_rate']} < {MIN_PARSE_OVERALL}")
        low = {v: r for v, r in a["parse_rate_by_variant"].items() if r < MIN_PARSE_VARIANT}
        if low:
            problems.append(f"arm {arm}: variants below {MIN_PARSE_VARIANT}: {low}")
    if remaining_min < 2:
        problems.append(f"only {remaining_min:.0f} min left (and `timeout 0` means no limit)")
    elif projected_s / 60 * RUNTIME_MARGIN > remaining_min:
        problems.append(
            f"projected {projected_s / 60:.0f} min x {RUNTIME_MARGIN} exceeds the "
            f"{remaining_min:.0f} min left"
        )
    s["problems"] = problems
    s["passed"] = not problems
    (run_dir / "gate.json").write_text(json.dumps(s, indent=1) + "\n")
    if problems:
        raise GateError("; ".join(problems))
    return s


# --------------------------------------------------------------------------- lock


#: Frozen before any model run (preregistration). Paths are repository-relative.
LOCKED = (
    *CS1684_FILES,
    "research/warranted_revision/src/warranted_revision/decision_procedure.py",
    "research/warranted_revision/src/warranted_revision/decision_procedure_analysis.py",
    "research/warranted_revision/configs/decision_procedure_pilot.json",
    "research/warranted_revision/configs/decision_procedure_full.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_hashes() -> dict[str, str]:
    return {rel: sha256(resolve(rel)) for rel in LOCKED}


def check_config_locked(cfg: DPConfig) -> None:
    """The launched config must equal a locked config except for run id and output root."""
    drop = {"run_id", "out_root"}
    want = cfg.model_dump(exclude=drop)
    for rel in LOCKED:
        if rel.endswith(".json") and "/configs/decision_procedure_" in rel:
            ref = DPConfig.model_validate(json.loads(resolve(rel).read_text()))
            if ref.model_dump(exclude=drop) == want:
                return
    raise GateError("config differs from every locked decision-procedure config")


def check_lock() -> None:
    if not LOCK.exists():
        raise GateError(f"{LOCK.name} missing; the frozen files are not locked")
    want = json.loads(LOCK.read_text())["sha256"]
    have = current_hashes()
    drift = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
    if drift:
        raise GateError(f"frozen files changed since the lock: {drift}")


# --------------------------------------------------------------------------- log transport


#: GitHub artifact storage is not reachable from every environment, so the box prints its
#: results into the job log: counts and analyses as ``DP_FILE <name> <json>`` lines, and the
#: raw calls as gzip+base64 ``DP_CALLS <i>/<n> <chunk>`` lines. ``recover`` rebuilds them.
CHUNK = 60_000


def emit_files(run_dir: Path, names: Iterable[str]) -> None:
    for name in names:
        p = run_dir / name
        if p.exists():
            print(f"DP_FILE {name} {json.dumps(json.loads(p.read_text()), separators=(',', ':'))}")


def emit_calls(run_dir: Path) -> None:
    import base64
    import gzip

    blob = base64.b64encode(gzip.compress((run_dir / "calls.jsonl").read_bytes(), mtime=0)).decode()
    parts = [blob[i : i + CHUNK] for i in range(0, len(blob), CHUNK)] or [""]
    digest = hashlib.sha256((run_dir / "calls.jsonl").read_bytes()).hexdigest()
    for i, part in enumerate(parts, 1):
        print(f"DP_CALLS {i}/{len(parts)} {part}")
    print(f"DP_CALLS_SHA256 {digest}")


def recover(log_text: str, out_dir: Path) -> list[str]:
    """Rebuild the files a run printed into its job log; verifies the calls' sha256."""
    import base64
    import gzip
    import re

    out_dir.mkdir(parents=True, exist_ok=True)
    written, parts, total, digest = [], {}, None, None
    for line in log_text.splitlines():
        line = re.sub(r"^\S+Z\s", "", line.strip())  # GitHub's timestamp prefix
        if line.startswith("DP_FILE "):
            _, name, payload = line.split(" ", 2)
            (out_dir / Path(name).name).write_text(json.dumps(json.loads(payload), indent=1) + "\n")
            written.append(Path(name).name)
        elif line.startswith("DP_CALLS_SHA256 "):
            digest = line.split()[1]
        elif line.startswith("DP_CALLS "):
            _, pos, *rest = line.split(" ", 2)
            i, n = map(int, pos.split("/"))
            parts[i], total = (rest[0] if rest else ""), n
    if total is not None:
        if sorted(parts) != list(range(1, total + 1)):
            raise GateError(f"calls chunks incomplete: have {len(parts)} of {total}")
        raw = gzip.decompress(base64.b64decode("".join(parts[i] for i in range(1, total + 1))))
        if digest and hashlib.sha256(raw).hexdigest() != digest:
            raise GateError("recovered calls do not match the printed sha256")
        (out_dir / "calls.jsonl").write_bytes(raw)
        written.append("calls.jsonl")
    return written


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--config", type=Path, required=True)
    g = r.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--preflight", action="store_true")
    r.add_argument("--cache", type=Path, default=Path(".cache"))
    gt = sub.add_parser("gate")
    gt.add_argument("--run", type=Path, required=True)
    gt.add_argument("--remaining-min", type=float, required=True)
    gt.add_argument(
        "--project", type=Path, help="config whose full run the timing is projected onto"
    )
    sm = sub.add_parser("summary")
    sm.add_argument("--run", type=Path, required=True)
    lk = sub.add_parser("lock")
    lk.add_argument("--write", action="store_true")
    pr = sub.add_parser("prepare", help="download, check and merge the pinned models (GPU box)")
    pr.add_argument("--config", type=Path, required=True)
    pr.add_argument("--cache", type=Path, default=Path(".cache"))
    em = sub.add_parser("emit", help="print a run's files into the log")
    em.add_argument("--run", type=Path, required=True)
    em.add_argument("--calls", action="store_true")
    rc = sub.add_parser("recover", help="rebuild files from a saved job log")
    rc.add_argument("--log", type=Path, required=True)
    rc.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    if a.cmd == "prepare":
        prepare_models(load_config(a.config), a.cache)
        print("[prepare] models ready")
        return 0
    if a.cmd == "emit":
        emit_files(a.run, ("summary.json", "gate.json", "analysis.json", "manifest.json"))
        emit_files(a.run / "preflight", ("summary.json", "gate.json"))
        if a.calls:
            emit_calls(a.run)
        return 0
    if a.cmd == "recover":
        print(f"[recover] {recover(a.log.read_text(errors='replace'), a.out)}")
        return 0

    if a.cmd == "lock":
        if a.write:
            LOCK.write_text(json.dumps({"sha256": current_hashes()}, indent=1) + "\n")
            print(f"[lock] wrote {LOCK}")
            return 0
        try:
            check_lock()
        except GateError as exc:
            print(f"[lock] FAILED: {exc}")
            return 1
        print("[lock] OK")
        return 0
    if a.cmd == "summary":
        print(json.dumps(summarize(a.run), indent=1))
        return 0
    if a.cmd == "gate":
        try:
            s = gate(a.run, a.remaining_min, load_config(a.project) if a.project else None)
        except GateError as exc:
            print(f"[gate] FAILED: {exc}")
            return 1
        print(f"[gate] OK: projected {s['projected_full_run_min']} min, {s['remaining_min']} left")
        return 0

    cfg = load_config(a.config)
    check_lock()
    p = plan(cfg, preflight=a.preflight)
    print(f"[plan] {cfg.run_id}: {json.dumps(p)}")
    if a.dry_run:
        if cfg.preflight is not None:
            print(f"[plan] preflight: {json.dumps(plan(cfg, preflight=True))}")
        print("[plan] dry run: no model loaded")
        return 0
    root = Path(cfg.out_root or PKG_ROOT.parents[1] / "results" / "warranted_revision")
    out = root / (f"{cfg.run_id}-preflight" if a.preflight else cfg.run_id)
    man = run(cfg, real_backends(cfg, a.cache), out, preflight=a.preflight)
    (out / "summary.json").write_text(json.dumps(summarize(out), indent=1) + "\n")
    print(f"[run] {man['planned_calls']} calls in {man['elapsed_s']} s -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
