# format-001 notes

Format-only check, 2026-10-25, after the shared ledger JSON template. Two dev cases
(`dev-refinance-00`, `dev-relocation-01`), structured, best-of-N, premise search and the new
`premise_search_noprov` ablation, one replicate, 504 calls. Same model, instance type and
code otherwise as smoke-004. Instance up ~45 min (~$0.80, estimate), deleted and confirmed
gone. The job was marked failed because `report.py` crashed on the new condition name after
all calls and metrics were done; the report here was regenerated locally from the raw
outputs with the fixed code (commit ce37df1).

## Format: passed

- Decisions: every decision call strictly valid except one best-of-N sample.
- Ledgers: parsed in 98% best-of-N, 97% search and ablation decision calls, 99% hypothesis
  calls and 18/18 structured calls (80% in smoke-004). No bullet-list ledgers.
- Token limit: 1 call of 504.
- The one "refusal" is a false positive: a sample wrote "I cannot recommend a losing
  financial strategy" while reasoning, then hit the token limit before deciding.

## Found while checking

`rule_check.satisfied` is ambiguous. In 56 of 365 rule checks the model wrote a true
comparison (e.g. `6 > 4`) with `"satisfied": false`, meaning "the user's requirement is not
met". The scorer's arithmetic check reads `satisfied` as "the comparison as written is
true", so it marks these inconsistent. This affects both search arms equally but adds
noise to selection. Needs a wording decision before the pilot.

## Benchmark (fast kernels): no speedup available

Same 9 prompts, greedy, batch of 9, before and after installing the kernels:
2.02 vs 1.99 s/call (153 vs 155 tokens/s), identical outputs 9/9. Neither kernel loaded:
`flash-linear-attention` 0.6.0 needs a newer Triton than the one that ships with
torch 2.8 (`cannot import name 'extra' from triton.experimental.gluon.language`), and
`causal-conv1d` has no prebuilt wheel. Not pursued further.

Throughput for planning: 504 calls took 33 min of inference (3.9 s/call; structured calls
run unbatched and search prompts are longer than best-of-N prompts).
