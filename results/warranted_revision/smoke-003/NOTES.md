# smoke-003 notes

First real-model run (Stage 1 smoke), 2026-10-25. Qwen/Qwen3.5-9B @ c2022362 on one L40S
via Brev, 5 dev cases x 4 conditions, 900 calls. Instance up ~68 min (~$1.20), deleted
and confirmed gone by the controller.

**Don't read the condition comparison as a result.** The run did what a smoke test is
for: it showed the answer format is broken.

- `direct`: 27/45 outputs were rejected, and every one of them had a single clear
  `DECISION: <code>`. The model put it at the end of its last sentence instead of on its own
  line.
- `structured`: 45/45 rejected. 33 had a clear decision but put it inside the `<ledger>`
  block, before `</ledger>`; 12 ran out of tokens (512) before deciding. Several ledgers used
  `"less_than"` instead of `<`, which fails validation.
- `best_of_n` and `premise_search` look much better, but mostly because they pick one of 9
  attempts and the scorer prefers well-formatted ones. Best-of-N samples also hit the token
  limit far more often (86 of 405 calls vs 12 of 180 decision calls in search), so the two
  9-call arms weren't equally constrained.

The parser stays strict (that's the protocol). The fix is in the prompts and limits; see
the commit after this run. Inference was also slower than it needs to be: the optional
`flash-linear-attention` and `causal-conv1d` kernels weren't installed.

Raw outputs are in `predictions.jsonl.gz` and `search_traces.jsonl.gz`.

## Addendum: premise-ledger validity (added before smoke-004)

A separate per-call ledger diagnostic, added after this run, shows that **no ledger parsed
in any decision call** (0/405 best-of-N, 0/180 search, 0/45 structured) and 2/225 search
hypothesis ledgers parsed, even where the DECISION line was valid. So the search scorer's
grounding and arithmetic checks did not function in this run; selection in both 9-call
arms rested on decision validity and the edit/abstention checks alone.

Causes, from the raw text: the ledger schema required each fact's `value` to be text while
the prompt never said so, so the model's `"value": 8600` failed validation (2,029 field
errors; a schema bug, now fixed). Besides that, best-of-N samples often dropped the
`<ledger>` tags, some put the DECISION line inside the block, and some ran out of tokens.
Re-parsing this run's raw text with the fixed schema (diagnostic only; scores above are
as recorded) parses 326/405 search, 64/405 best-of-N and 0/45 structured ledgers.
