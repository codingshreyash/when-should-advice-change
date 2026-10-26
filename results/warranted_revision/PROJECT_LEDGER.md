# Project cost ledger (whole research project, $95 total)

**Rule (PI, 2026-10-26).** The remaining project budget is $95 minus all prior project
spending. That remainder is an absolute limit. The initial goal screen may use up to $8 for
Qwen3.5-9B and up to $8 for Mistral-NeMo, on Brev, run one after the other. Nothing else is
approved.

**How costs are recorded.**
- **Brev:** billed time × the hourly rate verified against Brev's listing at launch. Time
  runs from creation to the confirmed deletion recorded by the controller. These are
  estimates until Brev's invoice amount is entered in the "actual" column.
- **API:** cost from logged token usage where usage was logged.

## Prior spending

| item | date | basis | cost |
|---|---|---|---|
| Brev GPU runs smoke-001…format-002 (8 runs, `runs.json`) | 2026-10-25 | launch minutes × $1.06/h | **≈ $3.32** (estimate; Brev invoice amounts not yet entered) |
| Earlier Claude API runs: `results/{career,aita,pressure_controls,refusals,subthreshold,threshold_sweep}`, about 4,100 calls on Opus 5, Sonnet 5.5 and Haiku 4.5 | before 2026-10-25 | no token usage was logged, so cost can't be reconstructed | **unknown**: made with `CS1684_ANTHROPIC_KEY` (apparently a course key); PI to confirm whether this counts against the $95 |
| Earlier open-model runs (`bespoke-nimble-9b`, `qwen3.5-9b-base-same-scorer`) | before 2026-10-25 | not in `runs.json` | **unknown**: PI to confirm |
| Goal-screen preparation (CPU, GitHub Actions dry runs, no API calls) | 2026-10-26 | no provider spend | $0.00 |

**Known prior spend: ≈ $3.32. Remaining, if nothing else counts: ≈ $91.68.** Spend on this screen so far: ≈ $0.14, leaving ≈ $91.54. The screen's
$16 allocation fits unless unrecorded prior spending charged to the $95 exceeds about $75.

## This screen

| run | model | verified rate | cap | billed minutes | cost | deleted and confirmed | outcome |
|---|---|---|---|---|---|---|---|
| goal-screen-qwen35-9b-v1, attempt 1 ([run 40409456269](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40409456269)) | Qwen3.5-9B @ `c2022362` | $1.06 (Brev listing, 21:59 UTC) | $8 | ≈ 7.6 (launch step 22:04:41–22:12:16, including ~6.5 min boot) | **≈ $0.14** | yes, 22:12:14 | failed before any model call: the launch bundle left out `v2/` (items and manifests), so the on-box tests failed; fixed and covered by a bundle test |
| goal-screen-qwen35-9b-v1, attempt 2 | Qwen3.5-9B @ `c2022362` | – | $8 minus attempt 1 | – | – | – | not started |
| goal-screen-mistral-nemo-v1 | Mistral-NeMo-Instruct-2407 @ `04d8a905` | – | $8 | – | – | – | not started |
