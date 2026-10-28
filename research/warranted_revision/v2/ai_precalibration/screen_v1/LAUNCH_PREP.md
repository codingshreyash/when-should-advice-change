# Goal screen: launch preparation (no subject-model output exists)

These are spending and deployment changes only. None of the following changed:
- the items and gold;
- the prompts;
- the protocol;
- the thresholds;
- the analysis (`MEASUREMENT_CORRECTIONS_1.md`, `7928dea`).

The frozen files are hash-locked in `LAUNCH_LOCK.json`. The paid job checks every hash before
it calls the API, and the test suite fails if any frozen file drifts.

## Changes since the preregistration (spending and deployment only)

1. **Sonnet cap corrected from $10 to $8.** The config committed at `fea4d57` had
   `max_usd: 10.0`, while `PREREGISTRATION.md` §6 and the report to the PI said $8. The
   discrepancy was found during launch preparation, before any run, and the config now says $8.
   (The unused Opus config says $30, not the $20 reported. Opus is not on the launch allowlist
   and will not be run.)
2. **Accounting prices raised to 1.1× list: $2.20 input and $11 output per million tokens.**
   US-only inference is billed at 1.1×. We don't send `inference_geo`, but the higher prices
   keep the guard conservative if the workspace defaults to US-only inference.
3. **The preflight has its own cap of $1** (`preflight_max_usd`).
4. **The launch job** (`goal_screen_job.py`) and its workflow
   (`.github/workflows/warranted-revision-goal-screen-api.yml`).

## Verified on 2026-10-26 (official pages)

- **Model ID:** `claude-sonnet-5-5`, from the API ID row of
  `platform.claude.com/docs/en/about-claude/models/overview.md`.
- **Price:** $2/MTok input and $10/MTok output
  (`platform.claude.com/docs/en/about-claude/pricing.md`).
- **Price multiplier:** "using `inference_geo: "us"` applies a 1.1x pricing multiplier"; the
  default global routing uses standard pricing.
- **Request parameters** (from the Claude API reference for Sonnet 5.5):
  - thinking is turned off with `thinking: {"type": "between_tools"}`, valid at effort
    `high` or below (we use `low`), with no other field alongside it;
  - `temperature`, `top_p` and `top_k` are rejected, and we send none;
  - refusals return `stop_reason: "refusal"`.
- **No refusal fallback.** The reference recommends server-side `fallbacks` by default. We
  deliberately omit them, because a fallback would answer with a different model in the middle
  of the measurement.

## Cost (exact call sequence replayed by `estimate_cost.py`, at the 1.1× prices)

| | calls | typical (150-token replies) | worst case (every reply at max_tokens) | cap |
|---|---|---|---|---|
| Sonnet preflight | 30 | $0.11 | $0.21 | $1 |
| Sonnet full | 1,008 | $3.83 | $7.44 | $8 |
| Qwen3.5-9B (one L40S) | 1,008 | ≈ $2.3 | $3.20 (controller plan, 8 s/call) | $4 |

The worst case over-counts input, because it estimates 1 token per 3 characters plus 10%.

## Launch lock (`LAUNCH_LOCK.json`, first 16 hex characters)

| file | sha256 |
|---|---|
| `candidate_v3/items.json` | `c6b9757ffda86e3a` (unchanged) |
| `screen_v1/run_manifest.json` | `b0a965c45882b9a2` (unchanged) |
| `screen_v1/primary.json` | `ce8b3e39da2d0237` (unchanged) |
| `screen_v1/system_prompts.json` | `c4e00467dca9cc2f` (unchanged) |
| `goal_screen_analysis.py` | `2c111ef30fcadcca` (= correction 1) |
| `goal_screen.py` | see `LAUNCH_LOCK.json`. Changed only by the preflight cap. |
| `goal_screen_job.py` | see `LAUNCH_LOCK.json` |
| `configs/goal_screen_sonnet.json` | see `LAUNCH_LOCK.json` ($8; 1.1× prices) |
| `configs/goal_screen_qwen.json` | `e0874ef975cb30d1` (unchanged) |

## Credentials

- **API key.** It is read only from the `ANTHROPIC_API_KEY` secret of a GitHub environment
  named `goal-screen-paid`, and only by the step that calls the API. A test checks this, and
  also checks that no workflow input is interpolated into a shell script.
- **Unused local key.** This cloud container has a project key variable set
  (`CS1684_ANTHROPIC_KEY`). It was not read or used, and the runner reads only the standard
  SDK credential sources.
- **Brev token.** The Qwen run uses the existing `BREV_API_TOKEN` repository secret through the
  existing GPU workflow.

## Deployment checklist (each paid step needs your approval; no paid step has run)

**One-time setup (you)**

1. In GitHub, go to Settings → Environments and create `goal-screen-paid`. Add yourself as a
   **required reviewer**, and add the **`ANTHROPIC_API_KEY`** environment secret.
2. In the Claude Console, set a **workspace spend limit**, for example $10. This is the only
   hard cap.
3. Put the workflow on the default branch. `workflow_dispatch` only works for workflows that
   exist on the default branch; the run itself uses the branch you select. Either merge a PR
   with this branch, or add just the workflow file to `main`.

**Sonnet**

4. **Dry run.** Dispatch the workflow with `mode=dry-run` on `research/warranted-revision-v1`.
   Expect the tests to pass and the log to show `[launch] OK … full_calls 1008,
   preflight_calls 30`. No key is read.
5. **Preflight.** Dispatch with `mode=preflight` and `approve_usd=8`, then approve the
   environment gate. It makes 30 calls, with a $1 cap. Read only the "Cost and validity summary"
   step:
   - calls 30/30;
   - errors 0;
   - refusals;
   - stop reasons;
   - the RESPONSE-line counts;
   - the spend;
   - `projected_with_25pct_margin_usd`, which must be at most $8.

   Do **not** read the answers.
6. **Full run (separate approval).** Dispatch with `mode=full`, `approve_usd=8` and
   `preflight_run_id=<run id from step 5>`, then approve the gate. The job refuses unless that
   preflight is accepted. It makes 1,008 calls under an $8 cap, then runs the pre-registered
   analysis on all items and on the primary set.

**Qwen (independent of the Sonnet steps)**

7. **Dry run: done.** Actions run 40372476583 at `0a987ad` passed: tests green; the
   controller planned 1,008 calls, a $3.20 worst case, a 151-minute deadline and no provider
   call. The first attempt (run 40371793274) failed on an existing test that needed gitignored
   raw results; that was fixed in `0a987ad`. Repeat this dry run with the real hourly price.
   The inputs were:
   - `config=configs/goal_screen_qwen.json`;
   - `max_gpu_usd=4`;
   - `est_seconds_per_call=8`;
   - `instance_type=L40S`;
   - `gpu_hourly_usd=<price on the Brev screen>`;
   - `dry_run=true`.
8. **Run (separate approval).** Dispatch the same inputs with `dry_run=false` and
   `commands_verified=true`. The controller refuses a plan that doesn't fit under the cap, and
   deletes the instance on success, failure or cancellation.

**After the runs**

9. Apply `decide()` as written:
   - **stop:** end this research direction;
   - **inconclusive:** report it, with no redesign;
   - **investigate:** exploratory only, and it needs human validation and an independently
     authored follow-up before any claim.

## Deployment fix 2 (before the first paid call): preflight response validation

The preflight summary judged a RESPONSE line valid if it named any lowercase word that appeared
in the reply, so `RESPONSE: recommend boat` counted as valid. The summary now checks each answer
against the option codes actually offered in that call's scenario: the base for first turns
and decisions, and the control scenario for controls. Counts are reported in total and by kind
(first, decision, control). It still prints no model text and does not judge correctness.

- **Regression test:** `test_summary_validates_against_the_offered_option_codes` covers an
  invented code, a real code from a different scenario, and an invented branch in a
  conditional.
- **Lock:** only `goal_screen_job.py` changed in `LAUNCH_LOCK.json`. Items, prompts, gold,
  thresholds and analysis are unchanged.
