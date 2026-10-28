# smoke-004 notes

Measurement validation run, 2026-10-25. Same setup as smoke-003: Qwen/Qwen3.5-9B @ c2022362,
five dev cases, four conditions, one replicate, 900 calls, one L40S via Brev. Changes since
smoke-003: answer-format prompts, token limits (1024 structured, 200 direct), ledger `value`
accepts numbers, and new per-call diagnostics. Dataset, scoring rules and search algorithm
unchanged.

Instance `wrev-smoke-smoke-004-be91c9` ran about 56 minutes (~$1.00 at $1.06/h, estimate)
and was deleted at 19:16 UTC; the controller confirmed it no longer appears in `brev ls`.

## Did the measurement work?

Mostly yes.

- Decisions: 720/720 decision calls strictly valid across all conditions; no refusals, no
  missing outputs, no token-limit stops. 219/225 search hypothesis calls valid.
- Ledgers: parsed in 96% of best-of-N, 98% of search decision, 98% of search hypothesis and
  80% of structured calls. Parsed ledgers are well grounded (mean 0.96-0.99) and their rule
  checks are mostly arithmetically consistent.
- Main remaining problem: 22 of the 26 invalid-JSON ledgers copy the prompt's bullet-list
  layout (`- "facts": [...]`) instead of writing a JSON object. This hits `structured`
  hardest (9/45). A JSON skeleton in the prompt, the same for all ledger conditions, should
  fix it.
- Speed: inference still used transformers' slow fallback. `flash-linear-attention` 0.6.0
  installed but wasn't picked up; `causal-conv1d` didn't install.

## Outcomes

Five cases and one replicate: every interval is wide, and nothing here is evidence for or
against any hypothesis. For the record, point estimates on the two co-primary axes were
best-of-N 0.90 / 1.00, premise search 0.80 / 0.95, direct 0.80 / 0.80, structured
0.60 / 0.80. Nothing will be changed because of these numbers.

Raw outputs, including every failed attempt, are in `predictions.jsonl.gz` and
`search_traces.jsonl.gz`.
