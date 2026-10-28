# Current state (orchestrator snapshot)

Analysis commit: `06c8fc72559438906a76f069b1cbe1a299f8bed1` on `research/warranted-revision-v1`
(PR #8, draft, base `shreyash/generational-report`). Snapshot taken 2026-10-25.

## Completed runs (`results/warranted_revision/runs.json`, `RUN_LOG.md`)

| run | what | instrument version | usable data |
|---|---|---|---|
| synthetic-20261025-bd0e95d | fake backends, controls | v0 | pipeline checks only |
| smoke-001 | `brev create` rejected type | – | none |
| smoke-002 | on-box test failure | – | none |
| smoke-003 | 5 dev cases x 4 arms, 900 calls | pre-format-fix prompts, ledger `value` bug | raw outputs; mostly format failures |
| smoke-004 | 5 dev cases x 4 arms, 900 calls | format-fixed prompts, bullet-list ledger spec, fixed-order beam tie-break, ambiguous `satisfied` | raw outputs; main real-model data |
| format-001 | 2 dev cases x (structured, best-of-N, search, ablation), 504 calls + kernel benchmark | JSON ledger template, fixed-order tie-break, ambiguous `satisfied`, ablation named `premise_search_noprov` | raw outputs |
| format-002 | 2 challenge cases, pilot arms | current code | none: on-box test failure, no model calls |

Model throughout: Qwen/Qwen3.5-9B @ c202236235762e1c871ad0ccb60c8ee5ba337b9a, bf16, thinking off,
one L40S. All labels are rule-generated; no human labels exist.

## Approved but not run

- Challenge pilot (`PILOT_PROPOSAL.md`, `configs/pilot_challenge.json`): 20 challenge_v1 cases,
  direct / best-of-N / premise search / format-only ablation, 1 replicate, 6,160 calls, 4 shards.
  On hold for this review. No real-model output exists yet for the current instrument
  (seeded tie-break, strict `satisfied`, challenge set).

## Known stale or contradictory documentation

- `README.md` status line still says no language model has been run.
- `PILOT_PROPOSAL.md` still mentions `premise_search_noprov` in the design section (renamed
  `premise_search_formatonly`; legacy name kept for old runs).
- `PROTOCOL.md` (frozen v0.1) requires two blinded reviewers for ambiguous follow-ups (not done),
  defines co-primary axes on v0 classes (the pilot adds a challenge-pressure axis), and asks for
  three repetitions at Stage 2 (pilot uses one replicate with order rotated across cases).
- Holdout split (`data/v0/holdout_*`) is frozen and has never been run or inspected for tuning.
