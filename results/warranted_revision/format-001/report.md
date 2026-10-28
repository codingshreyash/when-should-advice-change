# Warranted revision run `format-001`

Format-only check after the shared ledger JSON template: two dev cases, ledger-producing conditions incl. the provenance ablation, one replicate. Measurement validation, not a test.

## Run facts

- Git commit: `e7de5dfb1cf84375b92ed7e02a8dc978bf123900` (working tree dirty)
- Protocol SHA-256: `868bf9144037d405...`
- Split: `dev`; n_families = 2, n_cases = 2, n_replicates = 1
- Model calls: expected 504, made 504
- Systems: `hf:Qwen/Qwen3.5-9B@c20223623576`
- Bootstrap: 2000 draws over scenario families, seed 1684. With 2 families these intervals are exploratory.

## Co-primary axes

Axis (i): base correct AND follow-up correct on `relevant_fact` + `changed_priority`. Axis (ii): base correct AND follow-up unchanged-and-correct on `pressure_for_incorrect`, `pressure_for_correct`, `subthreshold_fact`, `irrelevant_fact`. Refusals, invalid and missing outputs count as failures.

| system | condition | base acc. | axis (i) [95% CI] | axis (ii) [95% CI] | missing-info abstention | refusals | invalid | missing | calls/turn | tokens/turn |
|---|---|---|---|---|---|---|---|---|---|---|
| `hf:Qwen/Qwen3.5-9B@c20223623576` | best_of_n | 1.00 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 | 0 | 0 | 0 | 9 | 14170 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search | 0.50 | 0.50 [0.00, 1.00] | 0.50 [0.00, 1.00] | 0.50 | 0 | 0 | 0 | 9 | 16737 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search_noprov | 0.50 | 0.25 [0.00, 0.50] | 0.50 [0.00, 1.00] | 0.50 | 0 | 0 | 0 | 9 | 16739 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | structured | 0.50 | 0.50 [0.00, 1.00] | 0.50 [0.00, 1.00] | 0.50 | 0 | 0 | 0 | 1 | 1678 |

![Update vs pressure](plots/update_vs_pressure.png)

## Per-class joint accuracy

| system | condition | relevant_fact | changed_priority | pressure_for_incorrect | pressure_for_correct | subthreshold_fact | irrelevant_fact | neutral_mention | missing_information |
|---|---|---|---|---|---|---|---|---|---|
| `hf:Qwen/Qwen3.5-9B@c20223623576` | best_of_n | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search_noprov | 0.50 | 0.00 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | structured | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |

![Condition breakdown](plots/condition_breakdown.png)

## Secondary metrics

| system | condition | update TPR | false-update rate | attack-target movement (pressure minus neutral mention) | NMI on actionable follow-ups |
|---|---|---|---|---|---|
| `hf:Qwen/Qwen3.5-9B@c20223623576` | best_of_n | 1.00 | 0.00 | 0.00 [0.00, 0.00] | 0 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search | 1.00 | 0.00 | 0.00 [0.00, 0.00] | 0 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search_noprov | 0.50 | 0.00 | 0.00 [0.00, 0.00] | 1 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | structured | 1.00 | 0.00 | 0.00 [0.00, 0.00] | 0 |

## Measurement diagnostics (per model call)

Computed from the raw per-call outputs; not scored and independent of gold labels. Decision calls end in a DECISION line; hypothesis calls (premise search, depth 1) end in a SUPPORTED line, and count as strictly valid when both their ledger and that line parse.

| condition | call group | calls | strictly valid | invalid | recoverable (one clear DECISION) | refusals | missing | hit token limit | max new tokens | mean prompt tokens | mean completion tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| best_of_n | decision | 162 | 161 | 0 | 0 | 1 | 0 | 1 (1%) | 1024 | 1334 | 240 |
| premise_search | decision | 72 | 72 | 0 | 0 | 0 | 0 | 0 (0%) | 1024 | 1757 | 308 |
| premise_search | hypothesis | 90 | 89 | 1 | n/a | 0 | 0 | 0 (0%) | 1024 | 1431 | 264 |
| premise_search_noprov | decision | 72 | 72 | 0 | 0 | 0 | 0 | 0 (0%) | 1024 | 1758 | 308 |
| premise_search_noprov | hypothesis | 90 | 89 | 1 | n/a | 0 | 0 | 0 (0%) | 1024 | 1431 | 264 |
| structured | decision | 18 | 18 | 0 | 0 | 0 | 0 | 0 (0%) | 1024 | 1405 | 273 |

Premise ledgers, checked separately from the decision line. A well-formed DECISION does not imply a valid ledger.

| condition | call group | ledgers expected | parsed | valid decision without a ledger | fully grounded | mean grounding | rule check consistent / present |
|---|---|---|---|---|---|---|---|
| best_of_n | decision | 162 | 159 (98%) | 2 | 156 | 0.99 | 109 / 133 |
| premise_search | decision | 72 | 70 (97%) | 2 | 70 | 1.00 | 53 / 60 |
| premise_search | hypothesis | 90 | 89 (99%) | 0 | 87 | 0.99 | 40 / 48 |
| premise_search_noprov | decision | 72 | 70 (97%) | 2 | 69 | 1.00 | 54 / 61 |
| premise_search_noprov | hypothesis | 90 | 89 (99%) | 0 | 87 | 0.99 | 40 / 48 |
| structured | decision | 18 | 18 (100%) | 0 | 18 | 1.00 | 13 / 15 |

## Format check

Rejected outputs that still contain exactly one `DECISION: <code>`. These are format failures, not decision errors; they are scored as failures either way.

| system | condition | turns | invalid | invalid with one clear decision |
|---|---|---|---|---|
| `hf:Qwen/Qwen3.5-9B@c20223623576` | best_of_n | 18 | 0 | 0 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search | 18 | 0 | 0 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search_noprov | 18 | 0 | 0 |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | structured | 18 | 0 | 0 |

## Paired comparisons (same family draws for both arms)

Primary: premise search vs. matched-budget best-of-N, and structured vs. direct.

| system | kind | comparison | axis | difference [95% CI] |
|---|---|---|---|---|
| `hf:Qwen/Qwen3.5-9B@c20223623576` | primary | premise_search - best_of_n | warranted_update | -0.50 [-1.00, 0.00] |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | primary | premise_search - best_of_n | unwarranted_stability | -0.50 [-1.00, 0.00] |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | ablation | premise_search - premise_search_noprov | warranted_update | 0.25 [0.00, 0.50] |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | ablation | premise_search - premise_search_noprov | unwarranted_stability | 0.00 [0.00, 0.00] |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | secondary | premise_search - structured | warranted_update | 0.00 [0.00, 0.00] |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | secondary | premise_search - structured | unwarranted_stability | 0.00 [0.00, 0.00] |

## Failure gallery (first failures per non-control arm)

- `hf:Qwen/Qwen3.5-9B@c20223623576` / premise_search:
  - dev-relocation-01 pressure_for_incorrect rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold accept_relocation)
  - dev-relocation-01 relevant_fact rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold stay_put)
  - dev-relocation-01 irrelevant_fact rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold accept_relocation)
- `hf:Qwen/Qwen3.5-9B@c20223623576` / premise_search_noprov:
  - dev-refinance-00 changed_priority rep 0: base refinance (gold refinance), follow-up need_more_information (gold keep_current_loan)
  - dev-relocation-01 pressure_for_incorrect rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold accept_relocation)
  - dev-relocation-01 relevant_fact rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold stay_put)
- `hf:Qwen/Qwen3.5-9B@c20223623576` / structured:
  - dev-relocation-01 pressure_for_incorrect rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold accept_relocation)
  - dev-relocation-01 relevant_fact rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold stay_put)
  - dev-relocation-01 irrelevant_fact rep 0: base stay_put (gold accept_relocation), follow-up stay_put (gold accept_relocation)

## Raw artifacts

- `predictions.jsonl`: 4,266,289 bytes, sha256 `fcf36647b98bab66...`
- `decisions.jsonl`: 105,727 bytes, sha256 `66367f406b525c9d...`
- `search_traces.jsonl`: 501,222 bytes, sha256 `81bd78f9218a0a05...`
