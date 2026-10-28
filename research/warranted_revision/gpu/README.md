# GPU smoke run

Notes from setting this up. Nothing here has run on a GPU yet.

## Choices

- **Model:** `Qwen/Qwen3.5-9B`, the protocol's first choice and the base model behind our
  earlier Nimble comparison. It's an image+text model, so it loads with
  `Qwen3_5ForConditionalGeneration` (same as `scripts/run/brev_setup.sh`). Thinking mode is
  turned off through the chat template. Pinned to commit
  `c202236235762e1c871ad0ccb60c8ee5ba337b9a` (the Hub's `main` on 2026-10-25, from
  `https://huggingface.co/api/models/Qwen/Qwen3.5-9B`). No HF token is needed.
- **Instance:** `massedcompute_L40S` (48 GB, $1.06/h on 2026-10-25). The cheaper
  single A6000s (`hyperstack_A6000`, $0.60/h) show up in `brev search`, but `brev create`
  applies a default 500 GB minimum disk and rejects them. L4s are cheaper ($0.85/h), but at
  24 GB they leave little room once the ~19 GB model is loaded. The controller now asks
  `brev create <name> --dry-run` for the types it accepts and refuses anything not listed.
- **Budget:** the controller caps the instance at 4 hours or 80% of `MAX_GPU_USD`, whichever
  is less. At $1.06/h that's about $4.24 worst case. The smoke set is 5 cases x 4
  conditions, 900 model calls, probably 1.5 to 2 hours.

## Brev CLI

Checked against `--help` from brev v0.6.335:

- `brev login --token <token>` works non-interactively with the `refresh_token` from
  `~/.brev/credentials.json` (tested on 2026-10-25 in a throwaway `HOME`, followed by
  `brev ls`). That token is stored as the `BREV_API_TOKEN` repository secret. If a run
  fails at login, the token may have expired; repeat that step.
- `brev create <name> --type <type>` creates the instance. Without `--type`, Brev picks the
  cheapest match on its own, and a comma list means "try these in order". The controller
  allows exactly one type so the price you enter is the price you pay.
- `brev create --type X --dry-run` just echoes X back; it does not check that `create` accepts
  it. On 2026-10-25, `hyperstack_A6000` appeared in `brev search` but `brev create` rejected it
  as "not a recognized type" (CLI v0.6.337). Nothing was created and nothing was billed.
- `brev delete <name>` deletes it; this takes a few minutes. Piped `brev ls` prints one
  name per line, which the controller uses to confirm deletion.
- `brev refresh` rewrites the SSH config. We assume `ssh <name>` works afterwards. That's
  the main thing still unconfirmed.

## Shards, benchmark and configs

- `--config` / workflow input `config`: any run config under this directory. The controller
  checks the plan against it and ships that exact file to the box.
- `--shard i/n` / input `shard`: run one round-robin slice of the cases on its own instance,
  with its own budget guard and deletion. Seeds don't depend on the shard. Merge finished
  shards with `python -m warranted_revision.aggregate --out-run-id <id> <shard dirs...>`,
  which refuses mismatched configs, commits, models or case coverage.
- `--bench` / input `benchmark`: time a fixed batch before and after installing the fast
  kernels (`bench-fallback.json`, `bench-kernels.json` in the run directory).

## Running it

1. Done: `BREV_API_TOKEN` repository secret.
2. Get `.github/workflows/warranted-revision-gpu-smoke.yml` onto `main`, so the
   "Run workflow" button shows up.
3. Run it with `dry_run` checked, today's hourly price, `max_gpu_usd` 15 or less,
   instance type `massedcompute_L40S`, and a new `run_id`. This only prints the plan.
4. Run it again with `dry_run` unchecked and `commands_verified` checked.
5. Afterwards, confirm in the Brev console that the instance is gone and the charge looks
   right. Don't start another run if either is off.

To check the plan locally without touching Brev:

    python gpu/brev_controller.py plan --hourly 1.06 --max-usd 15 --run-id test --instance-type massedcompute_L40S

## Runs so far

After every run (including dry runs and failed launches), add an entry to
`results/warranted_revision/runs.json` and rerun `python -m warranted_revision.runlog`, which
rewrites `RUN_LOG.md` with totals. Fill in `actual_cost_usd` once Brev's charge is known.

- `smoke-001`: refused by `brev create` (type filter), nothing created.
- `smoke-002`: instance created, failed in the on-box test suite (a path bug), deleted after ~9 min.
- `smoke-003`: full run, 900 calls, ~68 min, ~$1.20. Not interpretable: most direct and
  structured answers broke the answer format. Prompts, token limits and kernels were fixed
  afterwards. Details in `results/warranted_revision/smoke-003/NOTES.md`.
- `smoke-004`: 900 calls, ~56 min, ~$1.00 (estimate). Format checks passed: all decision calls
  strictly valid, no token-limit stops, 96-98% of search and best-of-N ledgers parsed (80%
  structured). See `results/warranted_revision/smoke-004/NOTES.md`.
- `format-001`: 504 calls, ~45 min, ~$0.80 (estimate). Shared JSON ledger template works
  (97-100% ledgers parsed, structured 18/18). Fast kernels can't load with torch 2.8's
  Triton; no speedup (2.0 s/call either way, identical outputs). Report regenerated
  locally after a report-step crash. See `results/warranted_revision/format-001/NOTES.md`.

## CS 1684 decision-procedure experiment

Preregistration: `docs/PREREGISTRATION_DECISION_PROCEDURES.md` (repository root). Arms A–D on
Qwen3.5-9B @ `c2022362` (A: Nimble scorer, no adapter; B: constrained generation; C:
conversational generation; D: Bespoke-Nimble @ `594dfdcf` through the scorer). The configs
are hash-locked in `configs/decision_procedure_lock.json`, and the controller refuses a config
that differs from them in anything other than run id. `remote_job.sh` hands these configs to
`gpu/decision_procedure_job.sh`, which builds its own environment at Nimble's pinned code
(`54c2e82e`), checks that the adapter names the preregistered base, merges, and runs.

**Not yet launched.** The technical pilot waits for the two blind labels.

| step | `config` | `max_gpu_usd` | planned worst case | contents |
|---|---|---|---|---|
| pilot | `configs/decision_procedure_pilot.json` | 2 | $1.60 | 128 calls; counts only, with timing projected onto the full run |
| full | `configs/decision_procedure_full.json` | 3 | $2.40 | 64-call preflight + gate, then 4,800 calls and the preregistered analysis |

`est_seconds_per_call` is ignored for these configs, because the controller uses the
experiment's own estimate, which includes model preparation. Results come back in the job
log:
- `DP_FILE` lines carry the summary, gate and analysis;
- `DP_CALLS` lines carry the gzip+base64 raw rows.

Rebuild them with
`python -m warranted_revision.decision_procedure recover --log job.log --out <dir>`.
