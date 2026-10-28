# Cross-review 04: scaffold-probe anatomy and the v2bench audit/behaviour code

Code is at `eea4aeb`. I ran everything on CPU with fake backends, writing only into temp directories under the scratchpad. I made no GPU or API calls, read nothing from the holdout, and edited nothing outside this file and `v2_reports/offline_04/cross/`. Each finding below gives the evidence first, then a proposed fix.

Scripts (from the repo root, run as `PYTHONPATH=research/warranted_revision/src python3 -B <script> [tmpdir]`):
- `offline_04/cross/probe_anatomy.py`: all six cells, rounds and samples, fake backend `stubborn`.
- `offline_04/cross/probe_edge.py`: base answer invalid or NMI; the stage-1 config exactly as written.
- `offline_04/cross/audit_check.py`: `audit()` baselines, a permutation null, the leakage check, and `behavior()` under every label.

## Most important issues

**1. The probe crashes mid-run if any greedy base answer is invalid or need_more_information.** (Blocker for launch.)
- **Evidence:** with a fake backend whose base reply is invalid, `run()` raises `AssertionError`. With a base reply of `DECISION: need_more_information`, it raises `KeyError: 'need_more_information'`.
- **Cause:** `item_text("toward_insist", base, …)` asserts `base is not None` and indexes `items["insist"][base]` (`scaffold_probe.py:308-310`). It is called for every base before any item call (`:456`).
- **Consequences:**
  - One non-actionable base out of 20 aborts the run after the base batch. The calls already made are lost, and no manifest is written.
  - Gate V4 tolerates up to 10% non-actionable bases, so the runner and the gate disagree.
  - smoke-004 had 0/5 NMI bases, but challenge_v1 bases are new and the order swap is new.
- **Fix:** for non-actionable bases, skip `toward_insist` and log those calls as not planned, or substitute the `acts[0]` reference already used for `away`. Make `expected_calls` match either choice, and add a CPU test with an NMI or invalid base.

**2. The sampled readout re-draws different decision steps in S0 and S3, which confounds branch (b).** (Major.)
- **Evidence:** this is the stage-1 config exactly as written (`probe_edge.py`, 80 samples per row).

  | cell / item | step that is re-drawn |
  |---|---|
  | S0 / away_insist, away_emotional, neutral_other | `decision` (first decision) |
  | S3 / away_emotional | `decision` |
  | S3 / away_insist | **`r2_decision`** (after two "Are you sure?" rounds) |
  | S3 / neutral_other | **`r2_decision`** (after two re-asks) |

- **Cause:** `_advance` overwrites `c.final_request` on every round (`:572, :602`). The readout uses whatever the last value is (`:503`). SCAFFOLD_PROBE.md says "the final decision call", which is technically true, but `probe_analysis` pools these rows as if they were the same item turn (`probe_analysis.py:200-209`).
- **Consequences:**
  - S3's sampled "away" pool mixes first-turn emotional pressure with post-pushback insist pressure.
  - S3's sampled neutral is post-reask, while S0's is first-turn.
  - Branch (b) requires excess in both S0 and S3, so the gate compares unlike things.
- **Fix:** store `item_request` (the first decision) separately and sample from it in every cell. If post-round sampling is wanted, add it as its own `sample_step` and report it separately.

**3. The intended one-factor contrasts are correct.** (No action needed except 3d.)
- **(a) S0 is byte-identical to the main runner.**
  - Base messages equal `prompts.conversation(case, order, DIRECT_FORMAT)`.
  - The S0 follow-up equals `conversation(...)` with the same text and base reply.
  - Its skeleton (roles, options present, 3 options, format text) and system prompt match a saved smoke-004 direct follow-up.
- **(b) Each cell's follow-up differs from S0 only in the intended element.**
  - S1: options dropped, `DIRECT_FORMAT` kept.
  - S3: options and `DECISION_RULE` dropped, length cap kept.
  - S4: `DECISION_RULE` dropped, options and cap kept.
  - S5/S6: same message as S0/S1, plus the fixed decision turn.
- **(c) The other elements are constant across all six cells.**
  - The length cap is present everywhere: `LENGTH_CAP` is the exact prefix of `DIRECT_FORMAT`.
  - History messages 0–2 (system, base question, base reply with its `DECISION:` line) are identical across all cells.
  - The decision turn is the same text, options and `DIRECT_FORMAT` in S3–S6.
  - Option order is shared within a conversation group.
- **(d) A free batch-invariance check is being discarded.** S5's free-reply prompt is byte-identical to S0's decision prompt (100/100), and S6's to S1's (100/100). Under greedy decoding these pairs should produce identical text. But free steps are written with `parsed=False` (`:585`), so S5's and S6's first decisions are never parsed.
  - **Fix:** parse free steps as well, without counting them toward V2. Report S5-free vs S0 and S6-free vs S1 text identity as an extra reproducibility gate alongside V5. Also note that S5 and S6 measure re-asking after a decision has already been given, not an unscaffolded first answer.

**4. `behavior()` silently returns KEEP when the adjudicated label has no authored reading.** (Major for B1/B2 gold.)
- **Evidence:** `audit_check.py` §5. For every item and every substantive label it lacks, the fallback `[…][:1] or [base_act]` (`v2bench.py:115-125`) yields KEEP in all 110 combinations.
- **This covers the most likely disagreement:** FACT_SUPPORTED vs FACT_UNSUPPORTED is exactly the confusion pair the gate watches.
  - In 10 items, an authored FACT reading changes the action, but adjudicating to the other FACT label returns KEEP.
  - The correct answer would be REVISE (if adjudicated supported) or HEDGE (if adjudicated unsupported).
  - Example: `eld-01` (GOAL_CHANGE) adjudicated FACT_SUPPORTED becomes KEEP `move_to_maple_court`, even though its only reading changes the action.
- **Spec:** BENCHMARK_V2 §2 says gold is computed from the reading the humans endorse. A missing reading should not mean "no change".
- **Fix:**
  - For FACT_SUPPORTED and FACT_UNSUPPORTED, use any authored FACT reading's `facts_update`: same claim, different stance.
  - Otherwise return `{"behavior": None, "unresolved": "no authored reading for <label>"}` and make `check`/`agree` list these items for the author to add a reading.
  - Do not default to KEEP.

**5. AMBIGUOUS ignores the hedge that an unsupported reading would require.** (Moderate; latent in the current draft.)
- **Cause:** `behavior()` maps FACT_UNSUPPORTED readings to the base action ("no change", `:129`).
- **Evidence:** an item that is AMBIGUOUS between {PREFERENCE, a decision-relevant FACT_UNSUPPORTED claim} gets KEEP with `decision_invariant: True`. The same claim labelled FACT_UNSUPPORTED alone gets HEDGE (synthetic test on `eld-10`).
- The table in §2 implies an ambiguous item should be at least as cautious as its readings. None of the 8 draft AMBIGUOUS items hits this case: `hp-08` already HEDGEs because its other reading is FACT_SUPPORTED.
- **Fix:** combine each reading's own `behavior(base, r.label, [r])`. The result is decision-invariant only if all of them are KEEP or REVISE with the same action. Otherwise HEDGE over the union of their actions and `if_true` branches.

**6. `audit()` itself is leak-free, but it is not yet the audit §6 specifies, and its behaviour metric is uninformative.** (Moderate.)
- **Correct:**
  - The vectorizer is fit on training families only and only transforms the held-out family.
  - Leave-one-family-out is by `family_id`.
  - No follow-up string appears in more than one family.
  - `audit.json` reproduces byte-for-byte.
- **Chance baselines:**
  - The 6-way label baseline (0.167) is fair as a reference.
  - The leave-one-family-out training-majority policy scores 0.083: labels are balanced overall, so a held-out family's labels are under-represented in training.
  - A within-family label-permutation null gives mean 0.112 and 95th percentile 0.188.
  - TF-IDF label accuracy of 0.542 therefore has p ≈ 0.005 (200 permutations). The shortcut is real even at n=48. This confirms §10's "fails".
- **Behaviour:** `tfidf_followup_behavior_accuracy` (0.604) predicts KEEP for 48/48 items. It equals the constant rate by construction and cannot detect a behaviour shortcut. The same applies to base+follow-up.
- **Not implemented yet:** acceptance checks 1, 2 and 4 of §6 (balanced accuracy per binary contrast with an upper bound, within-family permutation test, per-class recall). The v0 opening-words policy, the option-mention policy and the currency/question surface features are also missing.
- **Lexicon:** the keyword lexicon is scored without cross-validation, and a zero-hit default counts as AMBIGUOUS. That gives 2 free correct answers: 0.54 vs 0.50 without the default credit.
- **Fix:**
  - Report balanced accuracy, macro-F1 and predicted-class counts.
  - Add `class_weight="balanced"`.
  - Add per-binary-contrast runs, the within-family permutation p (the code is in `audit_check.py`) and per-class recall.
  - Label the lexicon "tuned, not cross-validated".

## Smaller points

- **Base rows record `base_choice=null` and `away_option=null`** (20/20). They are written before parsing assigns them (`:389, :441-446`). `probe_analysis` reads `choice` from the base row, so results are unaffected, but the field is misleading. Fill it in after parsing, or drop it from base rows.
- **When the base answer is non-actionable, `away` defaults to `order[1]`**, which flips with the ab/ba order (`:445-446`). Those conversations are excluded from switching counts, but they still feed V2. Document this or skip their items.
- **`max_new_tokens_free = 200` is adequate** where the 3-sentence cap is kept (S3/S4). In saved direct outputs the capped replies maxed at 133 tokens, and 0/90 hit the limit. However, `finish_reason == "length"` is gated nowhere. Add "≤2% length stops among free and decision steps" to V2/V3.
- **The item file is consistent.** Rebuilding `data/scaffold_probe_v1` from challenge_v1 reproduces `items.jsonl` byte-identically (sha `a49129bd…`). Every challenge insist, emotional, neutral and pushback text equals the item text keyed by its target or mentioned option (0 mismatches against challenge gold). The only new text per case is the neutral mention of the other option. `tests/test_scaffold_probe.py` passes (6/6).
- **Batching differs from smoke-004.** The probe sends base turns and items as large batches (HF `max_batch` 9, left-padded), while smoke-004's direct arm ran at batch size 1. So S0 is prompt-identical to smoke-004 but not compute-identical. V5 (re-issue in a different batch) and the S5/S6 identity check in 3(d) are the right guards. Do not compare S0 rates numerically with smoke-004.
- **`v2bench.check()` can mispair items and rows** in its reused-string statistic. It zips `items` with `rows` using `strict=False`, so if any item is skipped for a problem, the pairing shifts. This doesn't matter today (0 problems). Key rows by `item_id` instead.
