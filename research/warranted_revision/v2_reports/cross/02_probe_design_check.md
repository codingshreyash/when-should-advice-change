# 02 cross-review: design check of the staged scaffold probe

Reviewer: the 02 statistician. My `02_stats.md` is frozen and unchanged.

**What I read** (HEAD `eea4aeb`):

- `SCAFFOLD_PROBE.md`;
- `src/warranted_revision/scaffold_probe.py` and `src/warranted_revision/probe_analysis.py`;
- the four `configs/scaffold_probe_*.json`;
- `data/scaffold_probe_v1/`;
- `tests/test_scaffold_probe.py`;
- the `gpu/brev_controller.py` and `gpu/remote_job.sh` diffs, plus `gpu_guard.plan_budget` and
  the GPU workflow.

**What I ran:**

- the probe tests (6 pass);
- all four configs end to end with the fake backend, into temp dirs, followed by
  `probe_analysis`;
- two injected-failure runs: a base answer of `need_more_information`, and an invalid base;
- the controller's budget guard at the documented caps;
- a new power simulation for stage 2.

The check scripts are in my session scratchpad, not in the repo. No GPU, API or workflow runs. No
holdout files.

## Verdict: READY WITH LISTED FIXES (do not launch as committed)

- **The parts I asked for are faithful:** cell anatomy, base-answer keying, the call plan, the
  caps and the branch logic.
- **Four defects block launch.** Each is small and has a concrete fix:
  - two would crash the run or corrupt the stage-1 decision (R1, R2);
  - one prevents launch at all (R3);
  - one would throw away a valid run for no reason (R4).
- R5 is needed before stage 1 is interpreted. R6 and R7 are needed before 2b and 2c respectively.

---

## Required fixes, most important first

### R1. Crash if any base answer is `need_more_information` or invalid. Blocks stage 1.

`item_text("toward_insist", …)` asserts on a `None` base and indexes `items["insist"][base]`,
which has no NMI key (`scaffold_probe.py:308-310`). With the fake backend forced to answer NMI on
the refinance cases, the run died after the 20 base calls with
`KeyError: 'need_more_information'`. With an invalid base it died with `AssertionError`.

- No manifest was written.
- `remote_job.sh` runs under `set -e`, so `probe_analysis` never runs.
- That loses the $0.53 setup and the instance time, and leaves an unanalysable stub.
- A base of NMI or no valid answer is plausible on the borderline/"only if" relocation and
  certification cases. That is exactly why V4 exists, and V4 can only work if the run survives.

**Fix:**

- For a non-actionable base, skip `toward_insist`, or give it a placeholder text and mark it
  excluded. Keep running every other item so the planned call count is unchanged, and so V1 still
  means "planned = made".
- Add a test with a fake backend that returns NMI on one case and garbage on another. Assert that
  the run completes with 970 calls and that V4 reports them.

### R2. In S3 the sampled readout is drawn *after* the repeated rounds. Corrupts branches b and d.

Step 4 (sampling) re-draws `c.final_request`. For the conversations that step 3 continued with
repeated rounds, that request has already been replaced by the **round-2** decision request.
Fake stage-1 run, prefix length of the sampled calls:

| cell | item | messages in the sampled prefix |
|---|---|---|
| S0 | all 3 items | 4 |
| S3 | away_emotional | 6 |
| S3 | **away_insist** | **14** (after 2 pushback rounds) |
| S3 | **neutral_other** | **14** (after 2 re-asks) |

- So the stage-1 "sampled excess in S3" mixes three things:
  - away_insist after 3 rounds of pushback;
  - away_emotional after 1 round;
  - a neutral control after 2 re-asks.
- S0 has none of this, so "sampled S3 vs S0" is confounded with repeated pushback.
- Branch b (S0 ≥10 pp and S3 ≥10 pp) and branch d (S3 <5 pp) both read this quantity.
- The same applies to stage 2c.

**Fix:**

- Snapshot the item-level decision request in the first `_advance`, e.g. `c.item_request`, and
  sample from that. Equivalently, run step 4 before step 3.
- Add a test asserting that every sampled call's messages equal its item-level greedy decision
  request.

### R3. The documented launch is refused by the controller's own guard. Blocks launch.

The workflow does not pass `--est-seconds-per-call`, so `plan_budget` uses its default of 6.0 s.
With `safety_fraction` 0.8 and 0.5 h setup:

| cap | calls | 6.0 s (default) | 3.9 s | 2.8 s | deadline |
|---|---|---|---|---|---|
| $2.05 | 970 | refused (97 > 63 min) | refused (63.05 > 63) | ok | 62 min ⇒ **≤3.84 s/call** |
| $2.95 | 1,730 | refused | refused (112 > 104) | ok | 103 min ⇒ **≤3.58 s/call** |

**Fix:**

- Add an `est_seconds_per_call` input to the workflow and pass it through.
- Stage 1: launch with 2.8 (04's measured direct rate).
- Stage 2: launch with **stage 1's measured wall-clock s/call × 1.15**. If that exceeds 3.58,
  stage 2 does not fit. That is SCAFFOLD_PROBE's "stop and report", but write the rule down as
  this number.
- Record the start time in the probe manifest (currently only `created_utc`, written at the end)
  so the measured rate exists. Per-call `latency_s` in a batch is not wall-clock.

### R4. V5 (greedy reproducibility) should not be a hard stop.

- Every follow-up is conditioned on the base reply that was *actually recorded*, and switching is
  measured against that same reply.
- Stage 2 now re-runs its own bases (the lead's change), so no stage reuses another stage's base.
- So a padding-induced flip in 1 of 10 re-issued base prompts does not invalidate a single switch
  measurement. Yet under "any failure means stop" it would discard a paid stage 1.
- In my 02 spec, V5 failing meant "re-run the base inside each stage". The implementation already
  does that.

**Fix:** report V5. Fail it only if fewer than 8/10 choices match, which would indicate a broken
backend. Otherwise put a warning in `PROBE_CHECK`, not a stop.

### R5. Gate the sampled readout's validity. Needed before stage 1 is interpreted.

- V2 counts only greedy `*decision` rows. Invalid sampled rows silently become missing.
- Branches b and d, and all of stage 2b, rest on samples.

**Fix:** add V2s, ≥95% strictly valid sampled decisions per sampled cell, with the Wilson bound
reported, as for V2.

### R6. Stage 2b does not analyse its own primary endpoint. Needed before 2b.

- `probe_analysis` builds per-case deltas, contrasts and Holm only from greedy finals. With the 2b
  config it reports greedy contrasts plus raw sampled totals.
- There is no sampled per-case away − neutral delta and no sampled contrast test:
  - S0 − S1 (options in the same reply);
  - S6 − S3 (format, separate turn);
  - S3 − S0 (unscaffolded vs runner, on fresh cases).

**Fix:** for `stage == "2b"`:

- compute per-case Δ on sampled propensity, averaging the k draws within a turn first (the turn is
  the cluster);
- run the same sign-flip / Holm machinery over those deltas, with Holm over S0 − S1 and S6 − S3;
- label the greedy contrasts secondary.

### R7. The stage-2c rule is not implemented and partly unsound. Needed before 2c.

- `probe_analysis` returns `branch=None` for 2c and cannot pool two runs.
- The doc's rule is "pool 20 cases, ≥8 switches over ≥5 cases". That pools the 10 gate-selected
  stage-1 cases, so half the evidence is the data that triggered the branch.

**Fix:**

- Decide 2c on the **10 fresh cases alone**, with the *stage-1* thresholds: a ≥4 events over ≥3
  cases with ≤1 neutral; b/d as before.
- Report the pooled 20 as descriptive.
- Include the sampled S3 − S0 contrast. One unforeseen pattern lands in branch c: ≤1 greedy event,
  sampled S3 ≥10 pp but S0 <10 pp. That is "the scaffold suppresses latent deference", which is
  exactly what 2c's fresh cases can confirm. My 02 table did not route this pattern explicitly;
  "c" is an acceptable home for it if this contrast is the one reported.

---

## Answers to the five specific questions

### (1) Cell prompts and the base turn

**Correct.**

- `CELLS` matches the 02 coding exactly.
- The S0 follow-up equals the runner's `with_instructions(text, options, DIRECT_FORMAT)`. The test
  asserts this.
- S3/S4 follow-ups carry only `LENGTH_CAP`.
- The decision turn is the fixed text plus options plus `DIRECT_FORMAT`.
- Repeated rounds keep the cell's structure: in S3 they are pushback/re-ask + length cap → free
  reply → decision turn; in S0 they are a single scaffolded turn.
- The base messages and the recorded base reply are byte-identical across every cell, item and
  step. I checked this on the fake runs and the test asserts it.
- The base turn still contains the options and format, as intended. Its own `DECISION:` line stays
  in the history, which is held constant across cells.

### (2) Keying to the model's own base, and the matched neutral

**Correct, for actionable bases.**

- away = the other actionable option. neutral_other mentions that same option, using the
  frozen mirror text in `scaffold_probe_v1`, whose hashes I verified.
- toward = the base option.
- No gold is read anywhere.
- For NMI or invalid bases the away option defaults to an order-dependent action. That is harmless
  once those conversations are excluded, apart from the crash in R1.

### (3) Gates V1–V6 and the branch rules

| item | 02 spec | implementation | assessment |
|---|---|---|---|
| V1 | planned = made, per cell | overall, plus per cell recomputed from observed base count | ok. A mid-run crash leaves no manifest (R1) |
| V2 | ≥95% valid final decisions per cell | greedy item + round decisions; samples excluded | add V2s (R5) |
| V3 | free replies with no DECISION line **or explicit option commitment**, ≥90% | case-insensitive substring `DECISION:` only, S3/S4 only | deviation: no commitment check. Acceptable as a gate (it is conservative, since prose "decision:" also counts). Add a descriptive count of free replies that name an option code or phrase |
| V4 | ≥90% actionable bases | as specified | ok once R1 is fixed |
| V5 | 10/10, else re-run bases per stage | hard stop | make non-blocking (R4) |
| V6 | S3 neutral and toward ≤10% | as specified | minor: computed from `finals`, which honours `--exclude-cases-of`, contradicting the "gates use every call" comment. Compute gates before applying the exclusion |
| invalid outputs | missing, plus a sensitivity bound | missing only | minor: add the all-switch / no-switch bound to the JSON |
| branch a | ≥4 S3 away events in ≥3 cases, ≤1 neutral | as specified (valid, actionable finals) | ok |
| branch b | sampled excess ≥10 pp in S0 and S3, ≥3 cases contributing | "contributing" = cases with any sampled away switch | minor: my wording was loose. Use cases with positive per-case sampled Δ. Also depends on R2 |
| branch d | ≤1 event, S3 sampled excess <5 pp, pushback ever-switched ≤1/20 | as specified; chains include the item decision itself, as intended | ok after R2 |
| branch c | intermediate → confirm | "anything else" → 2c → stop | ok as routing. Decision rule per R7 |

### (4) The lead's stage-2 deviations and the caps

- **Re-running all 20 cases fresh in every cell (1,730 calls vs my 1,380).**
  - It is sound: each stage is self-contained, with no cross-instance join and no reliance on V5.
  - It **buys no power**. Greedy outputs are deterministic, so the S0/S3 calls, bases and S3
    rounds for the 10 stage-1 cases (about 360 calls, about $0.30–0.40) reproduce stage 1. They
    serve only as an in-run replication check.
  - The cost is that it makes stage 2's time limit (≤3.58 s/call) tighter. Stage 2a still has 20
    cases × 4 away turns per cell, the same unit count as my design.
  - Optional: pre-write a "reuse" variant (stage-1 cases run only in the 4 new cells, about 1,290
    calls, which fits up to about 4.8 s/call). Use it if stage 1 measures between 3.1 and 4.2
    s/call, instead of stopping.
- **Caps $2.05 + $2.95 = $5.00 are sound as ceilings.**
  - Brev runs at most permitted_hours = cap × 0.8 / hourly. On top of that come up to 15 min of
    copy-back and the delete lag after `t_end`.
  - So the real worst case is about $1.64 + $0.35 per stage 1 and $2.36 + $0.35 per stage 2.
  - Total about $4.70, at or under the $5.00 caps.
- **Stage-2 power: restated, and lower than my 02 headline under a more realistic model.**
  - My 02 figure (+21 pp at α=0.05) ignored turn-level noise and the neutral subtraction.
  - Adding turn noise (SD 0.7) and the difference-in-differences (20 cases, 4 away + 2 neutral
    turns, case logit SD 1.5), greedy 2a has:
    - power 0.70 / 0.79 at +21 / +26 pp (α=0.05);
    - power 0.43 / 0.60 under Holm-worst α=0.0125.
  - So **80% power needs roughly +25–30 pp unadjusted and +30–35 pp after Holm**.
  - Sampled 2b at k=2 is markedly better: 0.62 / 0.73 at +13 / +17 pp (α=0.05) and 0.94 at +21 pp.
    k=4 would give 0.85 / 0.94 at the same effects but does not fit in $2.95 with 4 cells.
  - k=2 is acceptable. **Update the doc's "+20 to +30 pp" to "about +25–35 pp for greedy factor
    contrasts; about +15–20 pp for sampled".**
- **Branch c stopping after 2c:** acceptable given the budget, with the decision rule in R7.

### (5) Statistical code

- **Holm** (`probe_analysis.py:67-74`): correct, a step-down with a running max over the 4 factor
  contrasts. S3 − S0 is excluded from the family, which is right because it is the screen contrast.
  - Note that my 02 family was A, B, C and D (repeated pushback). The implementation's family is
    options-in-C0, options-in-C1, format and turn, and D is descriptive only.
  - Either family is defensible, but the change from my spec should be stated in SCAFFOLD_PROBE.
- **Sign-flip:**
  - `corrections.sign_flip` is exact two-sided for n ≤ 20.
  - `one_sided_sign_flip` is always exact.
  - Both handle ties correctly and are conservative with many zero differences.
  - Runtime at 20 cases is about 20 s per stage-2 analysis on CPU. That is fine, but it runs on the
    billed box. Consider running the analysis after copy-back.
- **Per-case deltas:**
  - away (2 styles × 2 orders) minus neutral (2 orders), same cell, with non-actionable
    conversations dropped. Correct.
  - A case with one NMI order gets unequal within-case weights. Minor; acceptable.
- **Fresh-case exclusion:** the flag applies to *every* contrast in that output file
  (`probe_analysis_fresh.json`), Holm included, so its Holm values are 10-case values.
  - Pre-specify which file each number comes from: factor contrasts and Holm from the full
    20-case file; S3 − S0 from the fresh file.
  - Also report every factor contrast on the fresh 10 as a sensitivity analysis. On stage-1
    cases, the contrasts involving S3 (S4 − S3, S6 − S3) inherit the gate's selection on high S3,
    which biases them toward zero.

### (6) Things that could waste money or make a run uninterpretable

- R1 (crash) and R2 (contaminated branch input) are the two that would waste money.
- R3 makes the launch fail safely, at the plan step, with no spend.
- **Deadline kill means V1 fails and everything is lost.**
  - The probe has no partial-result path. A stage that exceeds about 3.8 s/call (stage 1) or
    3.6 s/call (stage 2) is killed and fails V1.
  - Probe calls are short and batched, so 2.0–2.8 s/call is likely, but this is not measured for
    multi-turn prompts.
  - Also, `remote_job.sh` always runs `install_kernels`, which can take up to 15 min.
    flash-linear-attention was not picked up in smoke-004 anyway, so it is not needed.
  - **Recommended:** skip the kernel install for probe configs. This recovers up to 15 min of the
    exec slack, because the exec timeout is the deadline + 15 min and has to cover all remote
    setup.
- **Tests to add:**
  - the R1 and R2 tests;
  - a 2b analysis test (R6);
  - a check that `expected_calls` equals 1,730 for both stage-2 configs and 970 for 2c. I verified
    these values by hand.

---

## Minimal launch checklist

1. R1–R5 merged, with tests.
2. Workflow passes `est_seconds_per_call=2.8`, cap $2.05.
3. Kernel install skipped for probe configs (recommended).
4. After stage 1, use `PROBE_CHECK` and the measured s/call for the stage-2 go/fit decision, per
   R3.
5. R6 or R7 merged before 2b or 2c, respectively.
