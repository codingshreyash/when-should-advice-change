# goal-screen-mistral-nemo-v1

- **GitHub Actions run:** [40416847278](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40416847278), commit `c892e03`.
- **Model and box:** Mistral-NeMo-Instruct-2407 @ `04d8a905`, bf16, tokenizer loaded with
  `fix_mistral_regex`, one NVIDIA L40S (listed at $1.06/h).
- **Preflight gate: FAILED.** 4 of 24 answers were unparseable (16.7%), above the
  pre-registered 10% limit:
  - 3 of 12 decision answers;
  - 1 of 6 first answers;
  - 0 of 6 controls.

  There were no errors, refusals or truncations. Output averaged about 18 tokens per call
  (554 for 30 calls), so the replies were very terse.
- **Full run:** not started, as the gate requires. The instance was deleted and confirmed not
  listed.
- **What was not done.** The parser and prompts were not changed after this result. Loosening
  them now would be scoring tuned on observed output.
- **Files.** `gate.json` was recovered from the job log (counts only). The 30 preflight
  outputs are in the run artifact; this session can't download artifacts.
