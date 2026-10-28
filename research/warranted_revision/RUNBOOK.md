# Reproducible Execution and Cost Controls

## Roles

- **Cloud CPU environment:** code, tests, data generation, static audits, dry-run outputs, plotting, draft write-up, PR. No GPU or experiment API credentials are assumed.
- **Brev GPU environment:** only pinned base-model inference and bounded candidate search. Never assume the CPU cloud environment has the user's Brev login or can create GPU instances.
- **Evaluator:** offline process that reads raw predictions and ground truth; never exposes gold labels to inference or selection code.

## Required outputs

Each run lives under a unique immutable `results/warranted_revision/<run_id>/` prefix:

```
manifest.json                    git SHA, data hash, hardware, model revision, seeds, decoding, limits
predictions.jsonl                one row per model call, including raw and strictly parsed output
search_traces.jsonl              candidate states and scores, with gold information excluded
metrics.json                     denominators, accuracy/holding, refusals, costs, CI
report.md                        a one-page factual result and failures/limitations
plots/update_vs_pressure.png     paired axes, model calls or tokens annotated
plots/condition_breakdown.png    accuracy and refusal breakdown
```

Aggregate tables must include `n_families`, `n_cases`, `n_replicates`, `n_refusals`, mean model calls, compute time, and honest intervals. Do not commit API keys or private Brev credentials, checkpoint/model caches, or large raw checkpoints. Raw outputs can be uploaded as immutable artifacts rather than included in Git history; point the report at their location. A successful workflow exit is not evidence of a successful experiment: check that outputs and denominators exist.

## Preflight

1. Run all unit and data-invariant tests without a GPU.
2. Verify inference receives **prompt text and allowed schema only** and cannot access evaluation labels.
3. Verify a model cannot create a spurious success just by always repeating its first answer.
4. Verify option order is held constant within a scenario/replicate across variants, and counterbalanced across replicates.
5. Verify strict answer parsing and that missing/refused outputs remain visible.
6. Print the expected number of calls and compute budget before any paid job. Stop on mismatch.

## Brev budget safety

User's available Brev balance is approximately $95, but **first unattended GPU run must be capped at $15 of compute exposure**. Keep the balance for follow-up work. Read the actual selected instance price from the Brev provisioning screen or API; no hourly rate is assumed in this protocol.

- Refuse to start without an explicitly provided `GPU_HOURLY_USD` and `MAX_GPU_USD=15` (or lower).
- Calculate a conservative permitted runtime from remaining spend including setup overhead. Use a wall-clock watchdog and a cloud/provider-side cancellation mechanism.
- `timeout` or `sudo shutdown` inside a container is **not** a guaranteed provider billing stop. If provider-side stop/delete cannot be tested, an unattended Brev run is NOT approved; do CPU-only work instead.
- Create a dedicated instance for the experiment. No action may stop or delete unrelated resources.
- Guarantee a `finally`/always-run cleanup on success, failure, and interruption, ideally under an independent controller. Preserve artifacts to GitHub or external storage **before** deletion.
- Check actual charges afterward; if first run exceeds its allocation, stop. Never run training automatically.

NVIDIA Brev docs: https://docs.nvidia.com/brev/concepts/gpu-instances (stopped instances still incur storage costs; deleted instances do not).

## Day-one execution order

1. Implement contracts and unit tests.
2. Generate and audit exploratory cases with hidden gold labels.
3. Implement direct, structured, best-of-N, and premise-search in a common interface.
4. Run synthetic baselines and save a sample report clearly marked `SYNTHETIC / NO MODEL INFERENCE`.
5. Verify model loading and stop/cleanup behavior, if Brev access is configured.
6. Execute at most the bounded GPU smoke test, then generate real result tables and a failure gallery.
7. Leave `report.md` with explicit statuses: completed, blocked, not attempted, not verified. Do not fabricate model accuracy if GPU credentials are absent.

Do not launch full training, iterate on a frozen holdout, silently widen the research goal, rewrite the existing paper, or rewrite unrelated repository files.

## GPU smoke path in this repository

See `gpu/README.md` for the model, instance, Brev commands and the step-by-step launch.
