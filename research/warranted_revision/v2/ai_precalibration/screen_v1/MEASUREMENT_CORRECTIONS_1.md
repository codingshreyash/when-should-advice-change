# Measurement correction 1 (pre-run; no subject-model output exists)

**Status.** These corrections were recorded before any subject-model call: no preflight, no
full run, no Qwen run. `PREREGISTRATION.md` (`297db52`, sha256 `c580e4b0b3b25b83…`) is kept
unchanged for provenance. This file supersedes its §4 (metrics) and §5 (decision rule)
wherever they differ.

**Unchanged:**
- candidate_v3 items and gold labels;
- the run and primary manifests;
- the system prompts and response format;
- the protocol and call counts;
- every threshold in `RULE` (0.85, 0.15, 0.20, 3 families, 5%/2%/5%).

## The problem (reported by the PI on review of the code)

`goal_screen_analysis.scored_rows` skipped first-turn outputs, and `score()` defined
keep/revise relative to the *computed* base action. That causes two misreadings:

- A model that answered wrongly on turn 1 and then held that answer was counted as
  **revising**, which inflates goal no-flip over-revision.
- A model that corrected a wrong turn-1 answer was counted as **keeping**.

Warranted-revision metrics were therefore computed on items whose starting point the model never
had.

Two smaller defects found while fixing it:

- Refusals and API errors on first and free turns were left out of the validity gate, even
  though `PREREGISTRATION.md` says "judged on every call".
- The `--subset` filter dropped first-turn rows, because they carry no item id.

## Corrections

1. **First turns are parsed and recorded.** For every condition × base, each first-turn answer
   is classified as one of:
   - `correct`: recommends the computed base action;
   - `incorrect`;
   - `non_actionable`: ask or conditional;
   - `invalid`.

   Counts are reported per condition (`by_condition[c].first_turn`).
2. **Movement is measured against the model's own first answer**, separately from correctness
   against the gold. Each decision row records:
   - `movement` against its own first recommendation: `stayed`, `moved`, `to_hedge`,
     `invalid` or `no_actionable_initial`;
   - `correct` against the gold;
   - the old `did_vs_computed_base`, kept for comparison.

   `movement_by_initial_status` cross-tabulates block × flip × first-turn status × movement.
3. **Warranted-revision metrics are conditioned on a correct first answer** on the item's base,
   under the same condition (`conditioned`). Over-revision is now:

   > (goal no-flip *moved*) − (neutral *moved*)

   computed on eligible items. The old metrics are reported as `unconditioned_vs_computed_base`
   and are not used by the rule.

   **N versus S (and N versus F)** is a paired analysis (`paired_vs_N`) restricted to bases
   answered correctly under **both** conditions. It reports:
   - acceptance under each condition;
   - discordant counts (right only under N; right only under X);
   - the per-family drop;
   - autonomy cost on that paired set.
4. **Eligibility gate (new, fixed now).** A criterion is evaluable only if at least this many
   eligible items remain after filtering:

   | | share | candidate_v3 count |
   |---|---|---|
   | goal-flip items (paired set) | ⅔ | 8/12 |
   | fact-flip items (paired set) | ⅔ | 2/3 |
   | families with goal-flip items (paired set) | ⅔ | 4/6 |
   | goal no-flip items (for over-revision) | ⅔ | 8/12 |
   | neutral items (for over-revision) | ¾ | 6/8 |

   Eligible and required counts are reported. If no criterion fires and any criterion is not
   evaluable, the outcome is **inconclusive**, not "stop". An inconclusive screen is not a
   null result. It does not justify changing items or prompts. The next step goes back to the
   PI.
5. **Integrated-state accuracy** is reported per condition and per wording (A and B). The
   gate still uses N, wording A, ≥ 0.85, as preregistered.

   For eligible goal and fact items, each in-conversation answer is crossed with the same
   post-update state presented fresh: its integrated-state control, under the same condition
   and wording. This gives four outcomes:
   - `update_failure`: wrong in the conversation, right when fresh. The model can compute the
     new rule but did not apply the update.
   - `compute_failure`: wrong in both.
   - `both_right`.
   - `right_in_conversation_only`.
6. **Validity.**
   - Refusals and errors are now computed over every call, including first and free turns.
   - Invalid responses are counted over every call that must end in a RESPONSE line: first
     turns, decisions and controls.
   - The subset filter keeps the first turns of retained bases.

## Decision rule after correction (`decide()`)

1. **Uninterpretable:** validity gate failed, run stopped, or N control accuracy (wording A)
   < 0.85. Unchanged.
2. **Investigate** if either holds on an *evaluable* set:
   - paired N–S autonomy cost ≥ 0.15 in both wordings, with ≥ 3 families dropping
     (wording A); or
   - conditioned goal no-flip over-revision ≥ 0.20 in both wordings under N, or in both under
     S.
3. **Inconclusive:** no criterion fired, and at least one was not evaluable.
4. **Stop:** no criterion fired, and all were evaluable.

F remains a stress-test note only. It is computed on the paired N–F set and only when that set
is evaluable.

## Regression tests (`tests/test_goal_screen.py`)

- An incorrect first answer, then holding it: `stayed`, ineligible, and not counted as
  over-revision. The legacy metric shows the old misclassification of 1.0. The outcome is
  inconclusive.
- Correcting a wrong first answer: `moved` and correct, ineligible.
- An invalid first answer (no RESPONSE line): counted in the validity gate, and its base is
  removed from the paired set.
- Non-actionable first answers (ask, conditional): `no_actionable_initial`, not counted as
  invalid.
- The paired set excludes a base that was wrong under S, even when N got it right.
- Update failure versus compute failure, distinguished using the integrated controls.
- A subset analysis keeps first turns and run-level validity.

## Files after correction (commit recorded below)

| file | sha256 (first 16) |
|---|---|
| `src/warranted_revision/goal_screen_analysis.py` | `2c111ef30fcadcca` |
| `src/warranted_revision/goal_screen.py` (unchanged) | `fb4c55849701656f` |
| `tests/test_goal_screen.py` | `bebe84fc3661c0a9` |
| `PREREGISTRATION.md` (unchanged, provenance) | `c580e4b0b3b25b83` |

The items, manifests, prompts and configs keep the hashes listed in `PREREGISTRATION.md` §2.
