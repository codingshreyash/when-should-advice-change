# GPU smoke run

Notes from setting this up. Nothing here has run on a GPU yet.

## Choices

- **Model:** `Qwen/Qwen3.5-9B`, the protocol's first choice and the base model behind our
  earlier Nimble comparison. It's an image+text model, so it loads with
  `Qwen3_5ForConditionalGeneration` (same as `scripts/run/brev_setup.sh`). Thinking mode is
  turned off through the chat template. We still need to pin the exact commit:

      curl -s https://huggingface.co/api/models/Qwen/Qwen3.5-9B | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'])"

  Put the result in `configs/gpu_smoke.json` as `revision`. No HF token is needed.
- **Instance:** `hyperstack_A6000` (48 GB, about $0.60/h when checked on 2026-10-25), with
  `massedcompute_A6000` ($0.68/h) as backup. It was the cheapest option with enough memory,
  and 48 GB means no 4-bit quantization. It comes through Shadeform, a reseller, so check
  the console after the first run to make sure it was actually deleted.
- **Budget:** the controller caps the instance at 4 hours or 80% of `MAX_GPU_USD`, whichever
  is less. At $0.60/h that's about $2.40 worst case. The smoke set is 5 cases x 4
  conditions, 900 model calls, probably 1.5 to 2 hours.

## Brev CLI

Checked against `--help` from brev v0.6.335:

- `brev login --token <token>` works non-interactively.
- `brev create <name> --type <type>` creates the instance. Without `--type`, Brev picks the
  cheapest match on its own, and a comma list means "try these in order". The controller
  allows exactly one type so the price you enter is the price you pay. `--dry-run` checks a
  type without creating anything.
- `brev delete <name>` deletes it; this takes a few minutes. Piped `brev ls` prints one
  name per line, which the controller uses to confirm deletion.
- `brev refresh` rewrites the SSH config. We assume `ssh <name>` works afterwards. That's
  the main thing still unconfirmed.

## Running it

1. Pin the revision (above) and commit.
2. Add a `BREV_API_TOKEN` repository secret (Settings > Secrets and variables > Actions).
3. Get `.github/workflows/warranted-revision-gpu-smoke.yml` onto `main`, so the
   "Run workflow" button shows up.
4. Run it with `dry_run` checked, today's hourly price, `max_gpu_usd` 15 or less,
   instance type `hyperstack_A6000`, and a new `run_id`. This only prints the plan.
5. Run it again with `dry_run` unchecked and `commands_verified` checked.
6. Afterwards, confirm in the Brev console that the instance is gone and the charge looks
   right. Don't start another run if either is off.

To check the plan locally without touching Brev:

    python gpu/brev_controller.py plan --hourly 0.60 --max-usd 15 --run-id test --instance-type hyperstack_A6000
