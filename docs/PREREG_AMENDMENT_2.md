# Preregistration amendment 2: decision-procedure experiment

**Date.** 2026-10-28.

**Status.** Made before any model run of this experiment. No labels, no pilot and no
confirmatory run exist, so no change below responds to model output.

**Authority.** The PI delegated these decisions ("figure everything out yourself").
`docs/overnight/03_IMPLEMENTATION_AUDIT.md` left them open as amendments A2–A6. Amendment 1
(the NOT EVALUABLE outcome and label provenance) is accepted as written.

**Unchanged:**
- the **primary contrast** (D − A on Δ), the arms, stimuli, prompts and option orders;
- the eligibility rules, the 15-scenario threshold, the SESOI and the §8 decision rule;
- the parse gates.

## Decisions

1. **The primary contrast stays D − A.**
   - It isolates the adapter on fixed weights and scorer, which is the question the
     preregistration asks.
   - It is likely to favour Nimble, because arm A uses the base model through an interface it
     was not trained for (`docs/overnight/00_INITIAL_ASSESSMENT.md`). The write-up must say so.
2. **D − B on Δ is added as a secondary contrast** (Nimble scorer vs the base model prompted
   for one code).
   - It is the practical question: does decision fine-tuning beat asking the base model?
   - It confounds the adapter with the procedure, so it is reported as a comparison of
     decision procedures.
   - It joins the procedure family, which is now **7** contrasts.
3. **Holm families have fixed sizes:** 4 (adapter) and 7 (procedure). A contrast that is not
   evaluable, or has no p-value, enters its family with p = 1. *(Audit A4.)*
4. **Labels before any run, the technical pilot included.** *(Audit A2; this enforces §9.)*
   - `run()` and the controller's `launch` refuse unless both blind label files exist, carry
     the provenance `labeling.py score` writes, and match the hashes in the lock's `labels`
     section.
   - `lock --write` records those hashes, and refuses label files without provenance.
   - The analysis refuses label files that differ from those locked before the run.
5. **Completeness is a validity condition.** A run whose rows differ from the planned calls
   is UNINTERPRETABLE. Duplicate rows were already an error (amendment 1). *(Audit A3.)*
6. **Spending caps are preregistered per config:** the pilot `max_usd_cap` is **$1.60** and
   the full run's is **$3.40**, for $5.00 in total. The controller refuses a larger
   `--max-usd`. *(Audit A5.)*
   - The audit (finding 9) showed that at $3 the full run would fail its own on-box timing
     gate, by the code's deliberately pessimistic estimates. $3.40 is the most the $5
     allocation allows after the pilot cap.
   - The pilot measures the real timing. If it projects that the full run cannot pass the
     gate within $3.40, the run is not launched. Any increase above the $5 allocation needs a
     documented reason recorded in `results/warranted_revision/PROJECT_LEDGER.md` before
     launch, and stays within the project's remaining budget.
7. **Lock coverage.** The launch path is now locked as well: `decision_procedure_job.sh`,
   `remote_job.sh`, `brev_controller.py`, `gpu_guard.py` and `scripts/data/labeling.py`.
   `labeling.py` is bundled to the GPU box so the on-box lock check can verify it.
   *(Audit A6. The lock file itself is versioned in git; a separate self-hash was not added.)*

## Not changed (recorded)

- **Audit findings 14–17** are minor and diagnostic: the scope of the sensitivity rule,
  batch composition, the `finish_reason` heuristic, and the fail-open deletion check.
  - The sensitivity rule ("unparsed counts as a change") applies to H, F and Fsub only.
    That is how this amendment reads §5.
  - The deletion check depends on Brev's real `brev ls` output for an empty account. That
    output was not available offline, so the check was not changed. The controller still
    confirms by name, and the workflow's `if: always()` cleanup step remains.
- **The midterm report** is left as submitted. Its overstated wordings are corrected in
  `README.md` only.

## Re-lock

`PYTHONPATH=research/warranted_revision/src python3 -m warranted_revision.decision_procedure lock --write`
was run after these changes. The lock records no labels yet. After the two blind sheets are
scored, the same command must be run again to lock them before the pilot.
