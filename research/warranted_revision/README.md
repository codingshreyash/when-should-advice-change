# Warranted Decision Revision: Search and Premise Provenance

> **Current status (2026-10-25).** The research direction changed after two review rounds.
> Premise search is kept only as an experimental baseline: it was no better than a majority
> vote over the same samples, and its scorer checked self-consistency, not premises
> (`agent_reports/SYNTHESIS.md`). The v0 and challenge_v1 benchmarks turned out to be solvable
> from wording. The study now first asks whether a benchmark of warranted goal and premise
> changes can be built at all: `BENCHMARK_V2.md`, `PROTOCOL_v0.2.md` (draft),
> `v2/annotation/`, and the review in `v2_reports/SYNTHESIS.md`. A small gold-free diagnostic
> of the old pressure ceiling is planned in `SCAFFOLD_PROBE.md`. The challenge_v1 pilot was
> cancelled. The text below describes the original design and is kept as the record.

## Research question

Can a structured, premise-aware decision procedure reduce unwarranted agreement **and** unwarranted disagreement while preserving the ability to incorporate valid factual corrections and legitimate changes of goals?

A good response is not defined by agreeing or disagreeing with a user. It is defined by whether a changed recommendation follows from a decision-relevant change in evidence, constraints, or stated priorities.

## Mechanism and falsifiable hypotheses

**Hypothesis H1 (representation).** Representing facts, goals, constraints, evidence provenance, and a decision rule explicitly improves correct revision relative to direct prompting.

**Hypothesis H2 (search).** Searching over candidate interpretations and decisions improves correct revision beyond an equally expensive best-of-N sample-and-select baseline. A search advantage must survive controls for compute, verbosity, and option order.

**Hypothesis H3 (verification).** Auditing whether a proposed change is supported by a cited premise reduces unwarranted revisions without reducing warranted revisions. This gain may disappear if premise extraction itself is corrupted by social pressure.

**H0.** None of the interventions improves paired correctness under matched inference budgets. Stable answers alone do not count as success.

## Intervention ladder

All experimental arms must use the *same pinned generative base model*, prompts conveying the same task facts, matched option permutations, and repeated samples.

1. **Direct:** one answer, no imposed intermediate structure.
2. **Structured:** explicit fact, goal, constraint, provenance, and rule extraction before answering; no search.
3. **Best-of-N:** sample candidate structured analyses, select one with the same non-oracle scoring rule used by search. Match candidate/model-call budgets.
4. **Premise search:** search over *alternative interpretations of the new evidence or goal*, proposed rule applications, and final answers; apply non-oracle consistency/provenance checks. Log nodes, scores, branches, and selected answer. A short beam/search implementation is not a reproduction of SMART's uncertainty-adaptive MCTS; call it premise search unless actual MCTS is implemented.
5. **Optional provenance guard:** allow revisions only through a logged, cited edit to the premise ledger; report both model-extracted provenance and oracle-provenance upper bounds. This is an ablation, not a replacement for end-to-end evaluation.

Do not attempt training, reinforcement learning, or Lean theorem proving until the inference-only comparisons work. These remain optional future phases with separately declared compute costs.

## Scope

**First experimental domain:** rule-grounded, numerical or conditional career/financial choices with a deterministically checkable action and clearly declared priorities. Include realistic language variation. Existing career scenarios may be used as a diagnostic, but held-out confirmatory examples must come from separately frozen scenario families and independently reviewed labels.

**Out of scope for the first run:** Reddit moral judgments treated as ground truth, claims that the model's hidden thought process was measured, general-purpose theorem proving, and claims about all model sizes based on one model.

## Documentation

- `PROTOCOL.md`: fixed stimuli, interventions, metrics, comparisons, and decision gates.
- `RUNBOOK.md`: reproducible execution, resources, logging, failure and cleanup behavior.
- A run must emit a machine-readable manifest, raw per-call JSONL, audit summary, comparison tables, confidence intervals, plots, and a failure-case gallery.

This is a research protocol and proposed experiment, **not a statement that model runs have already occurred**.

## Implementation in this directory

Status: Stage 0 (CPU only) is implemented and tested. **No language model has been run under
this protocol yet**; every result committed so far is synthetic and labelled as such.

```
pyproject.toml          package metadata; core deps: pydantic, matplotlib (GPU extras optional)
PROTOCOL.md RUNBOOK.md  fixed design and execution rules
DESIGN_NOTES.md         implementation decisions, deviations, and the relation to SMART
src/warranted_revision/
  schema.py             validated records; model-visible vs hidden (gold) split
  families.py           8 scenario families with deterministic reference rules
  generate.py           seeded case generator, invariant audit, freeze/hash check
  prompts.py parsing.py rendering, paired option order, strict DECISION parsing
  scoring.py            non-oracle candidate scorer shared by best-of-N and premise search
  conditions.py         direct, structured, best_of_n, premise_search (budget-matched)
  backends/             base interface; fake (synthetic); controls (privileged); hf (GPU)
  runner.py             runs conditions, writes immutable run artifacts + manifest
  evaluate.py stats.py  offline evaluator with family-cluster bootstrap
  report.py             report.md and plots
  gpu_guard.py          spend cap / deadline / instance-name guard for the GPU smoke run
data/v0/                frozen dev + holdout inputs and gold, FREEZE.json hashes, smoke ids
configs/                synthetic_dev.json (CPU), gpu_smoke.json (needs a pinned revision)
gpu/                    Brev controller, command templates (unverified), remote script
tests/                  leakage, controls, parsing, option order, splits, budget, refusals, ...
```

Commands (run from this directory, Python 3.10+):

```bash
python -m pip install -e '.[dev]'
python -m pytest -q                                         # CPU suite
ruff check src tests && ruff format --check src tests && mypy src
python -m warranted_revision.generate --out /tmp/v0 --check data/v0   # data reproduces byte-for-byte
python -m warranted_revision.runner --config configs/synthetic_dev.json --run-id <id>
python -m warranted_revision.evaluate --run ../../results/warranted_revision/<id> --gold data/v0/dev_gold.jsonl
python -m warranted_revision.report --run ../../results/warranted_revision/<id> --compress
python gpu/brev_controller.py plan --hourly <USD/h> --max-usd 15 --run-id <id> --instance-type <type>
```
