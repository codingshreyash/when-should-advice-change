# Pass 01: independent research verdict

Written 2026-10-28 without reading any other `docs/overnight/` file. No labels exist other
than the scenario author's drafts (`expected`) and the AI-made items of the closed
warranted-revision work. No human labels exist.

**Commands run in this pass, and what they returned:**
- `cd research/warranted_revision && python3 -m pytest -q`: **170 passed**.
- Decision-procedure dry run: 4,800 confirmatory calls (1,200 per arm A/B/C/D) plus a
  64-call preflight; "no model loaded".
- `brev_controller.py plan` (offline): estimated 99 min on the box for 4,864 calls;
  run deadline 105 min; worst case **$2.40** against a $3 cap; "no provider call was made".
- A recount of the legacy 9B rows (`results/career/nimble-and-qwen__career_{pilot,v2}.jsonl`,
  300 rows). Qwen base: pressure TV > relevant-update TV in **23/30** scenarios, two-sided
  sign p = **0.0052**. Nimble @bd792f44: 11/30, p = 0.20. Answer changes: Qwen pressure
  19, relevant 16, reframe 12; Nimble 11, 14, 3. These match `docs/findings.md` §2 and §4.1.

I did not re-derive the Claude ladder or sweep numbers from raw rows; for those I cite the
saved summaries.

## Strongest argument for continuing

The one controlled comparison the project defined has never been run: the four-arm
experiment on fixed Qwen3.5-9B weights. Its code is built, tested and hash-locked, and it
is cheap. The worst-case cost is $2.40, inside the $5 allocation; about $90.78 of the
project budget remains, assuming no unrecorded spending
(`results/warranted_revision/PROJECT_LEDGER.md`).

The experiment would also settle a question the project's own headline leaves open. Its
variants include `mention_target`, and Press_s = P(target | pressure) − P(target | mention)
is exactly the neutral-mention control. `docs/findings.md` §4.1 says that control is needed
to tell Qwen's deference apart from lexical priming. The legacy base-model pull is real in
this data (23/30, p = 0.005, reproduced above), so it is worth that control.

## Strongest argument for stopping

1. **The primary contrast cannot become confirmatory, and there is no evidence that it will.**
   - Preregistration §4 defines the primary scenario set from two labels by people who did
     not write the scenarios. Those labels do not exist: only the unfilled sheets in
     `data/labeling/` are in the repository, and nothing records a labeler.
2. **The design probably cannot return a decisive answer.**
   - §6 assumes a scenario SD of about 0.3. With the minimum 15 eligible scenarios the CI
     half-width is about 0.15 (1.96 × 0.3 / √15); with 30 it is about 0.11.
   - The "equivalent within ±0.10" null needs a CI narrower than 0.20, so it is close to
     unreachable. The most likely verdict is "inconclusive at this precision".
3. **The novelty case is weak by the project's own account.** The negative methods report
   (§4) says BeliefTrack already measures fact-update sensitivity ("Failed Stay" /
   "Failed Update") and that the two-sided estimand is published. I could not verify any of
   this (see below), but the project has not argued otherwise anywhere.
4. **What remains is narrow.**
   - It concerns one niche adapter at a checkpoint (`594dfdcf`) that differs from the one
     behind the legacy finding (`bd792f44`).
   - It uses 30 author-written scenarios.
   - The sister direction has already closed with negative and null results.

## Novelty and measurement threats

**Literature.** No paper could be opened. Every `WebFetch` of arxiv.org, aclanthology.org
and a third-party index failed with "proxy refused the connection", and the shell fetch was
not permitted. Search engines returned index pages for some titles. A search hit is not
verification, so I describe no paper's content.

| work as cited | status | URL found by search only (not opened) |
|---|---|---|
| BeliefTrack (EMNLP 2026) | **unverified**. A search hit gives a May 2026 arXiv preprint; no hit showed an EMNLP 2026 venue | https://arxiv.org/abs/2605.30219 |
| "Sycophancy Suppression Can Impair Rational Updating" (Findings of EMNLP 2026) | **unverified**. A search hit gives an arXiv entry; the venue was not confirmed | https://arxiv.org/pdf/2608.26511 |
| SycoBench-600 (Findings of ACL 2026) | **unverified**. A search hit gives an ACL Anthology entry | https://aclanthology.org/2026.findings-acl.1759/ |
| "Are AI Decision Models Biased? A Case Study of Jev" (arXiv 2610.19619) | **unverified**. No search hit for this title or ID; fetch refused | https://arxiv.org/abs/2610.19619 (fetch refused) |
| "How Reliable Are System-One Decisions in Medicine?" (arXiv 2610.18529) | **unverified**. Only a third-party index page was found; fetch refused | https://arxiv.org/abs/2610.18529 (fetch refused) |

**Novelty consequence.** No novelty claim, for or against, can rest on this pass. The
negative report's statement that "BeliefTrack's full text was verified by the PI" has no
record in the files I read. A human must open these papers before any publication-facing
novelty statement.

**Measurement threats** (all from the project's own files):
- **Labels.**
  - Every "correct", "base correct" and eligibility figure uses the scenario author's draft
    labels.
  - The threshold-sweep labels are rule-derived, and one sweep (`thr_commute`) was relabeled
    after the run (`docs/findings.md` §1.3).
- **Surface cues** (`docs/findings.md` §6).
  - Omission prompts are always shorter (length AUROC 0.91).
  - `irrelevant_update` always appends a sentence: "change iff 3+ words changed" scores
    d′ −2.47 against it, but +1.81 against subthreshold edits.
  - The factual negatives therefore differ in surface form from the relevant updates.
- **Procedure confounded with model.**
  - Every Qwen/Nimble number is a scorer read-out; every Claude number comes from chat
    generation (`docs/PROPOSAL_GAP.md`, "The format comparison").
  - Cross-family behaviour labels compare procedures as well as models.
- **Option order.** Ladder and sweep runs shuffled option order per variant. Haiku changed
  18% of should-not-change answers when the order differed and 5% when it matched
  (`docs/findings.md` §8).
- **Sample size.** One sample everywhere; 30 scenarios; 8 sweep scenarios.
- **Claude refusals.** These are deterministic and variant-dependent (first-person pressure
  34/58 vs base 0/58, `docs/findings.md` §5.2), so its pressure rates are computed on
  filtered sets.
- **Checkpoints.** The preregistered D arm (`594dfdcf`) is not the legacy Nimble
  (`bd792f44`). D − A therefore does not replicate the legacy adapter result.

## Overstated or unsupported claims

1. **Qwen "deference"**
   - **Where:** `README.md` l. 40–42, "The Qwen3.5-9B base model shows *deference*: it
     moves more for a stated preference than for a relevant fact." `report/midterm.tex`
     l. 24–26 says the same.
   - **Why it is overstated:** the movement measurement holds (reproduced above). Calling it
     *deference* does not: `docs/findings.md` §4.1 says "whether Qwen's shifts are deference
     or lexical priming waits on the neutral-mention control", and that control has never
     been run on the 9B models.
2. **Haiku "opposition"**
   - **Where:** `README.md` l. 42–44, "pushed toward one option, it picks the other one more
     often". `report/midterm.tex` l. 52–53: "picks the option the user did *not* ask for".
   - **Why it is overstated:** by the counts in `docs/findings.md` §7, written advice pushed
     toward the high-side option moves high-side answers 26 → 9. The other option only goes
     22 → 26, while `need_more_information` goes 16 → 29. In code-only, the low side gains
     5 and asks gain 5.
   - Most displaced answers become requests for information, not the other option.
   - The conversational sweep shift is positive in 3/8 sweeps
     (`results/summaries/threshold_sweep_ladder.txt` l. 23).
   - The data are one sample, 8 scenarios, pooled counts with no scenario bootstrap, no
     neutral-mention control, and the option-order confound.
3. **Exact decision boundaries for Sonnet**
   - **Where:** `report/midterm.tex` l. 27–29, Sonnet 5.5 and Opus 5 "place decision
     boundaries exactly where the stated rules put them".
   - **Why it is unsupported:** Sonnet's sweep is partial (4 sweeps in
     `threshold_sweep_ladder.txt`). Its `thr_buyout` constrained switch is 0.79, and its
     conversational switches are 0.79–1.04 (l. 49–63). Opus alone supports "exactly".
4. **Novelty of the two-sided measure**
   - **Where:** `report/midterm.tex` l. 48–49, "Most sycophancy benchmarks count unwanted
     change only, which rewards a model that never moves."
   - **Why it is unsupported:** the project's own negative methods report (§4) says the
     two-sided estimand is published (SycoBench-600, Belief-R, SycEval). Whichever is
     right, the midterm cites no support for "most".
5. **Novelty closed by BeliefTrack**
   - **Where:** the negative methods report §4, "Sensitivity to whether a *fact* update
     changes the decision is already measured by BeliefTrack", and §7, "BeliefTrack's full
     text was verified by the PI".
   - **Why it is unsupported:** the claim rests on AI literature audits, and no record of
     the PI's verification is cited. It may be true, but it is unverified here.
6. **"Pressure is not a single sycophancy dial"**
   - **Where:** `report/midterm.tex` l. 30, "Pressure therefore is not a single sycophancy
     dial: deference and opposition are both failures of warranted updating."
   - **Why it is unsupported:** the conclusion compares a scorer read-out (Qwen) with chat
     generation (Haiku). It inherits threats 1 and 2 and is not supported as a general
     statement.
7. **Minor and stale statements**
   - `docs/PROPOSAL_GAP.md` l. 33 says findings §1.1 "still says 'no model has been run'".
     That was corrected on the same day (`docs/findings.md` l. 69).
   - `docs/PROPOSAL_GAP.md` l. 83–84 says "roughly an hour … about $2". The offline plan
     estimates 99 min, with $2.40 worst case.

## Ranked recommendation

1. **(C) Course report only; stop publication work.** Report the legacy and exploratory
   results with their stated status, and correct claims 1–6 above in the report text. This
   needs no compute.
2. **(A) The four-arm Qwen/Nimble experiment, only if two non-author labelers finish the
   sheets first.** It is cheap ($2.40 worst case), ready, and resolves claim 1 through
   `mention_target`. Without the labels it can only be exploratory. Its likely outcome is
   "inconclusive", so it should serve the course report, not a publication.
3. **(B) Investigate one observed failure.**
   - The Qwen deference-vs-priming question is already covered by (A).
   - The Haiku pattern needs API credit the project no longer has, and a matched-order
     rerun before it is worth explaining.
   - Not justified as a separate line.
4. **(D) A different direction: not eligible.** No literature gap was verified in this
   pass, so the rule's condition is not met.

**Stop condition.**
- **If the labels are not collected:** if two independent non-author labels for all seven
  prompts are not complete before the course report draft is due, spend nothing and do (C)
  only.
- **If (A) runs:** apply preregistration §8 exactly once. If it reports NULL or "not
  evaluable" (fewer than 15 primary scenarios), write it up and stop. Do not add
  follow-ups, new variants, new items or new prompts.
- **In all cases:** stop if any validity gate fails or spending would exceed the $5
  allocation.
