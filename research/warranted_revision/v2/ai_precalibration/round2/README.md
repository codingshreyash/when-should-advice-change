# AI pre-calibration, round 2 (procedure fixed before any round-2 output exists)

Same boundary as round 1 (`../README.md`). Every judgement here is an AI judgement. Nothing
here is human validation, and B1's human gate has not been run. Round-1 files are unchanged.

## Steps

1. **Author** (fresh context) writes `../candidate_v2/` under `GUIDELINES_v0.2.md`, fixing
   round-1 defects in the order given (high-severity gold problems first). Frozen on return.
2. **Coordinator checks** (`v2bench check`, `textcheck`, `audit`, masked and unmasked) are
   recorded as they come, not tuned.
3. **Blinded annotation.** Annotators A (Claude Opus) and B (Claude Sonnet) each get their own
   packet (v0.2 columns, a new seed) and `GUIDELINES_v0.2.md`, nothing else. A context-blind
   baseline (Claude Sonnet) gets the follow-ups only. All three are frozen on return.
4. **Auditor, phase 1** (fresh context, runs in parallel with step 3, sees no annotations):
   - shortcut baselines, including policies that know the original decision and can do simple
     arithmetic;
   - a gold-versus-text review of every item.

   Frozen on return.
5. **Adjudicator** (fresh context), blind first. The disputed set is every item where the
   annotators differ on the label or on `advisor_should`, either marked `AMBIGUOUS`, the design
   is `AMBIGUOUS`, or either annotator's `advisor_should` differs from the computed gold. Blind
   labels are frozen; then the adjudicator sees the anonymised annotations and gives a cause for
   each item.
6. **Auditor, phase 2:** sees the annotations and the adjudication, and searches for **shared
   errors**: items where every AI judge agrees with a gold answer the text doesn't support.
7. **Coordinator analysis:**
   - paired-base behaviour;
   - whether the task needs interpretation beyond arithmetic and recognisable phrases;
   - every item with a plausible alternative outcome;
   - label consistency on reused strings;
   - a small human review packet.
8. **Publication checkpoint** (fresh context): does the benchmark target a failure that
   existing selective-updating or sycophancy benchmarks don't?

## Rules

- **Disagreement is evidence.** Items are not rewritten during this round to make annotators
  agree. Any later rewrite becomes candidate_v3, with this round's results kept.
- **Isolation is by instruction**, checked afterwards by counting forbidden paths in each
  agent's tool calls (`../analysis/isolation_check.py`), with matches inspected by hand.
- **No paid API, no GPU, no holdout access,** and no move to B2 or B3.
