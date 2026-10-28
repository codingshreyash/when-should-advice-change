# Amendment 2: open-weights subjects replace Claude Sonnet 5.5 (pre-run)

**Status.** Recorded on 2026-10-26, before any subject-model output exists. No API call and
no GPU job for this screen has run.

**Unchanged:**
- `PREREGISTRATION.md` (`297db52`), `MEASUREMENT_CORRECTIONS_1.md` (`7928dea`) and
  `LAUNCH_PREP.md` are kept as written, for provenance.
- candidate_v3 items and gold, the three system prompts and the response format.
- The scoring and analysis code (`goal_screen_analysis.py`), the eligibility gate and every
  threshold in `RULE`.

## 1. What changed and why

The PI has no Claude API key. The screen therefore moves to an entirely open-weights,
GPU-based setup:

| | before | after |
|---|---|---|
| subject 1 | Qwen3.5-9B @ `c2022362` | unchanged |
| subject 2 | Claude Sonnet 5.5 (API) | **Mistral-Nemo-Instruct-2407** @ `04d8a905` (12.2B, Apache-2.0, not gated) |
| where | GitHub Actions (API) + Brev (GPU) | Brev L40S 48 GB for both, one run per model, run separately |

- **Sonnet launch path cancelled.** `goal_screen_job.CANCELLED` refuses the Sonnet config. No
  Anthropic key is requested or used. The API workflow on `main` stays, inert.
- **Second-model choice.** Mistral-Nemo was the PI's first preference. It comes from a
  different model family and lab than Qwen, fits an L40S in bf16, and needs no Hugging Face
  token. Gemma 3 12B IT was not used because it is gated and no token is configured.
- **What the change means for the question.** Sonnet was the "strong model" arm. The screen
  is now two small open-weights models, so it can no longer speak to frontier-model
  behaviour. A null result on both justifies stopping *this* screen. It does not show that
  stronger models never suppress legitimate goal changes. A positive result in one model is
  exploratory, as before, and needs human validation and an independently authored
  follow-up.

## 2. Protocol: same for both models

- **Protocol.** The same three-turn protocol (first turn, free follow-up, decision request in
  wordings A and B, 3 sampled repeats of A) and the same single-turn controls.
- **Calls.** 1,008 per model, plus the 30-call preflight.
- **Prompt rendering.** Each model gets its own chat template from its pinned tokenizer. The
  system prompt is sent as a `system` message. Where the template puts it is recorded, not
  forced:
  - Qwen renders it at the start of every conversation;
  - Mistral-Nemo's template places it immediately before the last user turn;
  - for single-turn calls (first turns, controls), both place it at the start.

  Comparisons are within-model, between conditions, so this difference is part of each
  model's native setup. It is not a confound between N, S and F.
- **Decoding.** Greedy for wordings A and B and for controls. The 3 repeats use T = 0.7 and
  top-p 0.95, as preregistered for the open model. Mistral's model card suggests T = 0.3;
  the preregistered 0.7 is kept for both models.
- **Output limits.** At most 400 new tokens per call. Qwen's thinking mode is off via its
  template; Mistral-Nemo has none.
- **Parsing.** The same strict RESPONSE-line parser, checked against the option codes offered
  in each scenario.

## 3. Deployment changes (execution only)

1. **Batched phases.** Each condition's independent calls (first turns, free turns,
   decisions A and B, sampled repeats, controls) run as phases, batched up to 9 sequences:
   - 9 is the batch size already used on this box;
   - prompts, decoding and call counts are unchanged;
   - batched and per-call execution give identical rows on the fake backend
     (`test_batched_execution_matches_per_call`).

   Two caveats:
   - A batch seeds sampling with its first request's seed, so sampled draws are reproducible
     for a fixed batch composition, not per call.
   - Left-padded batches can differ numerically from unbatched greedy decoding.

   Batching is needed to fit the budget. Unbatched, the measured single-stream rate puts
   Qwen's worst case near 5.6 h, beyond the $4 cap.
2. **Tokenizer fix.** transformers 5.20.2 warns that Mistral-Nemo's shipped tokenizer regex
   "will lead to incorrect tokenization". The config loads it with `fix_mistral_regex: true`,
   and `model_check` fails if any such warning remains.
3. **Pinned stack.** `transformers==5.20.2` (the version recorded on this box) and
   `torch==2.8.0`, so the CPU template check and the GPU run render prompts identically.
4. **On-box preflight gate.** The box runs the 30-call preflight first. The full run starts
   only if:
   - every planned call was made;
   - there were no errors;
   - at most 10% of answers are unparseable;
   - the projected runtime, from the preflight's measured time per batch × 1.5, fits in the
     minutes left before the deadline.

   Otherwise the job stops and the gate result is copied back. An over-long run is reported,
   never shortened.
5. **Hub and template check** (`model_check.py`, CPU, on the Actions runner). It checks:
   - the pinned revision;
   - the gated flag and licence;
   - every call shape rendered under N, S and F, with the system prompt exactly once and all
     turns in order;
   - context length;
   - a memory estimate.

## 4. Pre-launch checks completed (no GPU used)

| check | Qwen3.5-9B | Mistral-Nemo-Instruct-2407 |
|---|---|---|
| Hub `main` = pinned revision | yes (`c2022362…`) | yes (`04d8a905…`) |
| gated / licence | no / Apache-2.0 | no / Apache-2.0 |
| template renders all shapes × N/S/F | yes | yes |
| system prompt position (multi-turn) | before first user | before last user |
| longest prompt (tokens) | 1,828 | 1,808 |
| weights bf16 + KV at batch 9 | 19.3 + 2.6 GB | 24.5 + 3.3 GB |
| controller plan (dry run) | 1,038 calls, 151-min deadline | 1,038 calls, 151-min deadline |

## 5. Decision rule

`decide()` is unchanged and is applied **separately to each model**:
- **stop:** both models stop; end this screen;
- **inconclusive:** report it, with no redesign;
- **investigate:** in either model, exploratory only. It needs independent human validation
  and a larger, independently authored replication.

Small-model failures to apply a stated rule show up as control-accuracy failures, which
make the result uninterpretable, not a null.
