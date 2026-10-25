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
