# CS 1684 proposal vs completed work

**Status:** 2026-10-28. Nothing has been launched; this document compares plan against record.

**Source caveat.** The original course proposal is not in this repository. The questions
below are reconstructed from the earliest committed statements of the project's aims:
- `README.md`;
- `PROTOCOL.md`, the confirmatory protocol of 2026-10-19;
- the midterm report (`report/midterm.tex`);
- `docs/findings.md`.

Please check them against the proposal itself.

**What is closed and what is not.** The premise-search and goal-autonomy work
(`research/warranted_revision/`) is closed by its negative methods report. That report does
not close the questions below.

## Status by research question

The headings are:
- **completed:** done as planned, at the planned standard;
- **partial:** some runs exist, but are exploratory or legacy, incomplete, or confounded;
- **not tested:** no model output exists.

**No result in the project is confirmatory yet.** The protocol requires two blind human
labels on all seven prompts before confirmatory runs, and those labels have not been
collected.

| # | question (reconstructed) | status | what exists | what is missing |
|---|---|---|---|---|
| 1 | **Primary.** Does a model change its answer for a relevant fact (`relevant_update`) but not for an irrelevant one (`irrelevant_update`)? d′ and AUROC | **partial** | Claude size ladder, exploratory, both formats: Haiku and Sonnet on 30 scenarios, Opus rerun on 18/30. d′ ≈ 1.0 (Haiku), 2.36–2.65 (Sonnet), 2.27–2.47 (Opus, partial) | Bespoke-Nimble and Qwen never run on this variant. Option order was shuffled per variant in these runs, which confounds Haiku's numbers. No blind labels, no 5-replicate confirmatory run. *`docs/findings.md` §1.1 still says "no model has been run"; that is out of date.* |
| 2 | Magnitude: does a too-small edit (`subthreshold_update`) leave the answer unchanged? | **partial** | Claude Opus 5 (`results/subthreshold/`), plus the size ladder, exploratory | Bespoke-Nimble and Qwen not run; no blind labels |
| 3 | Correct updates and base accuracy | **partial** | Legacy runs, all four arms (draft labels, one sample, fixed option order) | Blind labels; confirmatory run |
| 4 | Missing information: does the model ask when the deciding fact is omitted? | **partial** | Legacy runs, all four arms. Omission prompts are shorter, and length alone flags them (AUROC 0.91) | Length-matched omissions not built; blind labels |
| 5 | Pressure and reframe (secondary): does a stated wish move the answer? | **partial** | Legacy, all arms. Claude: templated controls, multi-turn pushback, refusal ablation | Neutral-mention controls on the 9B models. Paired pressure-direction test (Haiku pilot planned) not run |
| 6 | Decision boundaries (threshold sweep) | **partial** | Opus complete; Haiku complete; Sonnet 77/192 prompts (option-order caveat) | 9B models not run |
| 7 | Model scale (Claude Haiku → Sonnet → Opus) | **partial** | Haiku and Sonnet career sets complete; Opus rerun 130/210 (API credits ran out) | Opus rerun, Sonnet sweep, Haiku rerun with fixed option order |
| 8 | **Output format: conversational vs constrained vs decision-only** | **partial → controlled comparison not tested** | Conversational vs constrained within Claude (Opus legacy d′ 2.36 vs 2.22; ladder at every size). Decision-only only for Bespoke-Nimble and Qwen | No model has been run in all three formats. The format effect is therefore confounded with the model (see below) |
| 9 | **Decision-only adapter: Bespoke-Nimble vs base Qwen** (same weights, prompt, scorer and output space) | **partial** | Legacy runs only, five variants, one sample, draft labels, fixed order. Nimble discriminates better (movement AUROC 0.71 vs 0.46; d′ 0.63 vs 0.04) but is not significantly more pressure-resistant (11 vs 15 shifts to target, McNemar p = 0.22) | Never run on `irrelevant_update`, `subthreshold_update`, the pressure controls or the sweep; no replicates or option permutations. Nimble's checkpoint changed on 2026-09-24 (`594dfdcf` → `bd792f44`) |
| 10 | Representation steering: does removing a "user wants X" direction reduce pressure flips without lowering relevant-update hits? | **not tested** | `scripts/run/run_steering.py` exists | Never run |
| 11 | Refusals | **completed (exploratory, Claude)** | Legacy rates, pressure-controls refusals, first-person ablation | Confirmatory-run denominators |
| 12 | AITA: does pressure move judgements of posts? | **partial** | 50 YTA posts, all arms (models already side with the poster at baseline) | NTA posts |

## The format comparison (questions 8 and 9)

**What was planned.** A comparison of three ways of getting advice from a model:
- conversational: written advice ending in an option code;
- constrained: one option code;
- decision-only: an option distribution from a scorer, with no text.

The plan also included a controlled adapter test: Bespoke-Nimble against its own base,
Qwen3.5-9B, differing only by the adapter.

**What the data can and can't say.**
- *Conversational vs constrained* was compared only inside Claude. There the two formats are
  indistinguishable for Opus: d′ 2.36 vs 2.22, legacy runs, overlapping intervals.
- *Decision-only* exists only for Bespoke-Nimble and Qwen, which were never run in a written
  format. Any difference between the decision-only arms and the Claude arms mixes format with
  model family, size and training. **The three-way format effect has not been measured for
  any model.**
- *Nimble vs base* is a real controlled comparison, but it exists only as a single-sample
  legacy run on five variants. It shows better discrimination and no significant difference
  in pressure resistance, on 30 scenarios with draft labels.

## Smallest scientifically credible next experiment (recommended; not implemented or launched)

**One model, all three formats, plus the adapter.** Hold the weights fixed so that output
format is the only thing that changes.

| arm | model | output |
|---|---|---|
| A | Qwen3.5-9B (the pinned base of Nimble) | decision-only: Nimble scorer, no adapter (as in the legacy runs) |
| B | Qwen3.5-9B | constrained: generate one option code (the same instruction `run_chat.py` gives Claude) |
| C | Qwen3.5-9B | conversational: short written advice ending in a code (the same instruction `run_chat.py` gives Claude) |
| D | Bespoke-Nimble-9B @ `bd792f44` | decision-only (the adapter contrast against A) |

- **Stimuli.** The existing 30 career scenarios, all seven prompts, frozen. No new items.
- **Replicates.** Five deterministic option permutations, as `PROTOCOL.md` specifies. One
  option order is kept per scenario across its variants, following the fix of the
  option-order bug. Generation is greedy.
- **Scale.** 30 × 7 × 5 = 1,050 prompts per arm, 4,200 in total. That is roughly an hour on one
  L40S, about $2 at the current listed rate, with a $5 cap. This is an estimate, to be
  confirmed by a dry run.

**Primary contrasts.** Each uses the protocol's label-free measure: d′ for "answer changed",
relevant vs irrelevant update, with a scenario bootstrap.
- B − A and C − B: the format effect within the same weights.
- D − A: the adapter effect, extended to the variants it has never seen.

**Secondary measures:**
- pressure shift to the target;
- omission asks;
- parse and refusal rates.

**Gates, fixed before running:**
- at least 95% of B/C answers parse strictly overall (last line exactly one option code), and
  at least 90% in every variant;
- planned calls equal made calls.

As in the goal screen, a format failure ends that arm and is reported. It is never fixed
after looking.

**Prerequisite.** Collect the two blind human labels the protocol requires (sheets exist in
`data/labeling/`).
- Without them, run this only as an exploratory study and report only the label-free movement
  metrics.
- With them, it becomes the protocol's confirmatory run for these four arms.

**What it would settle:**
- whether this project's central measurement depends on how the answer is extracted;
- whether the adapter's discrimination gain holds on the factual negatives it has never been
  tested on.

With 30 scenarios, only differences of roughly one d′ unit or more are likely to be
distinguishable. Smaller format effects would be reported as unresolved, not as absent.

**Why this and not something larger.** It reuses frozen stimuli, existing runners and pinned
weights, and costs a few dollars. It also fills the one controlled comparison the project
defined but never ran, without new item authoring or a second model family.
