# Pass 02: existing evidence, recomputed from raw rows

**Every number here is exploratory.** Each comes from one sample, scored against draft labels
(the scenario author's `expected` field), with the legacy Nimble checkpoint `bd792f44`. No human
labels exist.

**Source of every number.** Unless a line names another file, every number below was printed by
this one command, run from the repo root:

```
python3 docs/overnight/analysis/legacy_9b_reanalysis.py
```

The script reads only the raw rows in `results/career/nimble-and-qwen__career_pilot.jsonl` and
`results/career/nimble-and-qwen__career_v2.jsonl`, plus the scenario files. It does not import
`scripts/lib` or any project analysis code. Two sections also use other raw files: the scan of
variants reads `results/**/*.jsonl`, and the Opus abstention rates read
`results/career/claude-opus-5__career_{pilot,v2}.jsonl`.

**Integrity checks.** There are 300 rows: 2 models × 30 scenarios × 5 variants. No
(model, id, variant) key appears twice. No choice is null. Every row is `decision_only`, sample 0.

## Reproduced legacy numbers

The 30-scenario numbers, with `docs/findings.md` §2 in brackets where it reports the same quantity:

| | Qwen3.5-9B base | Bespoke-Nimble-9B |
|---|---|---|
| relevant update: any change | 16/30 [16/30] | 14/30 [14/30] |
| relevant update: correct (draft label) | 8/30 [8/30] | 13/30 [13/30] |
| base correct (draft label) | 22/30 [22/30] | 27/30 [27/30] |
| omission asks | 10/30 [10/30] | 0/30 [0/30] |
| unneeded asks on base | 7/30 [7/30] | 0/30 [0/30] |
| pressure: shift to target, exact 95% CI | 18/29 [.42, .79] [same] | 11/27 [.22, .61] [same] |
| pressure: any change | 19/30 [19/30] | 11/30 [11/30] |
| reframe: any change | 12/30 [12/30] | 3/30 [3/30] |
| d′, pressure + reframe; bootstrap seed 1684, 2,000 resamples | +0.04 [−0.49, +0.54] [same] | +0.63 [+0.06, +1.19] [same] |

**Mismatches with §2.** None. Every cell of the two 9B rows in §2 reproduces exactly.

I also checked the 9B numbers in §4.1, and all of them reproduce:
- AUROC of movement: Qwen 0.46, Nimble 0.71.
- AUROC split by contrast: Qwen 0.35 against pressure and 0.56 against reframe; Nimble 0.61 and 0.81.
- Mean TV shift for Qwen: 0.54 under pressure, 0.36 under the relevant update.
- Pressure moves Qwen more than the relevant fact in 23/30 scenarios (sign test p = 0.0052).
- Paired McNemar over 26 scenarios: Nimble 11, base 15; discordant 1 and 5; p = 0.219.

**Provenance problems** (these are not numeric mismatches):
- §2 says every number is printed by `scripts/analysis/report_tables.py`. That script does not
  compute "base correct", and its saved output `results/summaries/report_tables.txt` does not
  contain that number. The d′ intervals are also absent from that output; §4.1 attributes them to
  `discrimination.py`. My independent computation agrees with both values, so the gap is in where
  §2 says the numbers come from, not in the numbers.
- In the career_v2-only subset (20 scenarios), which the protocol says should be reported
  separately:

  | | Qwen | Nimble |
  |---|---|---|
  | relevant update: any change | 10/20 | 10/20 |
  | relevant update: correct | 5/20 | 11/20 |
  | base correct | 14/20 | 19/20 |
  | omission asks | 9/20 | 0/20 |
  | pressure: shift to target | 12/20 | 8/19 |
  | d′ (bootstrap 95% CI) | −0.06 [−0.70, +0.55] | +0.66 [+0.02, +1.35] |

  §2 does not give this split.

## Pressure versus neutral mention

These are the only `mention_target` rows in `results/**/*.jsonl`: Claude Opus 5, in
`results/pressure_controls/claude-opus-5__pressure_controls.jsonl`.

The other result files have none:
- Qwen3.5-9B base and both Nimble checkpoints (`bd792f44` and `594dfdcf`).
- Claude Haiku 4.5 and Claude Sonnet 5.5.

For Qwen base, Nimble, Haiku and Sonnet, the pressure-versus-neutral-mention comparison is
**impossible**. In particular, the existing data cannot tell whether Qwen's 18/29 shifts toward
the target come from deference or from naming the option. `docs/findings.md` §4.1 already says
this question waits on that control.

## Relevant versus irrelevant updates

Which models were run on `irrelevant_update`:

| model | file | coverage |
|---|---|---|
| Claude Haiku 4.5 | `results/career/claude-haiku-4-5-20251001__career30.jsonl` | complete |
| Claude Sonnet 5.5 | `results/career/claude-sonnet-5-5__career30.jsonl` | complete |
| Claude Opus 5 | `results/career/claude-opus-5__career30.jsonl` | partial (36 matching lines in that file, by grep) |

Qwen base and Nimble were not run on `irrelevant_update`, so the primary contrast does not exist
for the 9B models. The Claude runs shuffled option order per variant (`docs/findings.md` §8), so
an answer change in them can be an order effect. I did not recompute the Claude d′ values in
this pass.

## Option order

**What the rows contain.** The 9B rows have only these fields: `model`, `condition`, `id`,
`variant`, `choice`, `probs`. They do not record the order shown. According to
`docs/findings.md`, the order was fixed: the scenario file's `options` list, the same for every
variant.

**What a fixed order allows.**
- Base and variant used the same order, so a base-to-variant change cannot be caused by a change
  of order. The "any change", d′ and TV comparisons within a model are free of the per-variant
  shuffle artifact that affects the Claude ladder.

**What it does not allow.**
- *Position bias.* With one order, position is confounded with option identity. The draft base
  label is the first option in 20 of 30 scenarios. Nimble's base choice is the first option in
  19 of 30; Qwen's is in 16 of 30.
- *Separating pressure from position.* The pressure target is the second option in 19 scenarios,
  the first in 10 and the third in 1. A pressure shift therefore usually means moving off the
  first option, and position preference could add to it or subtract from it in ways these data
  cannot separate.
- *Generalizing to other orders.* No conclusion holds under a different order.
- *Comparing with the Claude ladder runs.* Those used shuffled orders, so they are not
  like-for-like with these runs.

## Abstention and refusals

`need_more_information` (NMI) chosen, with the mean probability the scorer put on NMI:

| model | omission prompts | complete base prompts |
|---|---|---|
| Qwen3.5-9B base | 10/30 (mean P 0.340) | 8/30 (mean P 0.217) |
| Bespoke-Nimble-9B | 0/30 (mean P 0.080) | 0/30 (mean P 0.026) |
| Claude Opus 5, constrained | 9/29 | 0/29 |
| Claude Opus 5, conversational | 8/29 | 0/29 |

The Opus denominators count non-refused rows only.

**Qwen's 8 base asks versus the 7 in §2.** The draft labels expect NMI on the base prompt of
`career_10`, so §2 counts Qwen's ask there as correct and reports 7 unneeded asks. Qwen actually
asked on 8 base prompts: `career_08`, `10`, `12`, `13`, `16`, `19`, `21` and `28`. §3 calls
the 7 "complete base prompts". That is accurate only under the author's label for `career_10`.

**Qwen's asks are not specific to omission.** Qwen also chose NMI on:
- 12/30 reframe prompts (mean P 0.400);
- 8/30 relevant-update prompts;
- 1/30 pressure prompts.

**Nimble never chooses NMI** on any variant (0/150). Its NMI probability is somewhat higher on
omission prompts (median 0.035) than on base prompts (median 0.009). This is descriptive only.

**Refusals.** The 9B scorer cannot refuse, and there are no null choices. For Claude refusals,
see `docs/findings.md` §5; this pass did not recompute them.

## Choice changes versus probability changes

These are scorer rows only (the 9B models). Each count is over the scenarios where the variant's
choice equals the base choice; it counts how often P(pressure target) under the variant was
higher than under base.

| model | variant | choice unchanged | P(target) rose | median Δ | rose by > 0.05 |
|---|---|---|---|---|---|
| Nimble | pressure | 19 | 19/19 | +0.104 | 12/19 |
| Nimble | pressure, base ≠ target | 16 | 16/16 | +0.073 | 9/16 |
| Qwen | pressure | 11 | 9/11 | +0.055 | 6/11 |
| Qwen | pressure, base ≠ target | 10 | 8/10 | +0.049 | 5/10 |
| Nimble | reframe (reference) | 27 | 18/27 | +0.002 | 7/27 |
| Qwen | reframe (reference) | 18 | 10/18 | +0.001 | 2/18 |

The reframe rows are a reference for how often P(target) rises with no request in the prompt.
They are not the neutral-mention control and do not replace it.

**Reading the pressure rows.** For both models, choice-level counts understate the effect of
pressure: when the answer does not flip, the distribution still moves toward the target almost
every time. That includes Nimble in all 16 cases where its base answer was not the target. This
is one sample with no neutral-mention control, so these rows cannot separate deference from the
target option simply being named.

## Comparisons the existing data cannot support

- **Relevant versus irrelevant updates for Qwen or Nimble.** They were never run on
  `irrelevant_update`. No confirmatory comparison exists for any model, because blind labels do
  not exist.
- **Pressure versus neutral mention for Qwen, Nimble, Haiku or Sonnet.** None of them has
  `mention_target` rows, so deference cannot be separated from lexical priming in the 9B models.
- **Option-order effects on the 9B models.** There is one fixed order, and position is
  confounded with option identity.
- **Run-to-run noise for the 9B models.** There is one sample and no repeat.
  `results/career/nimble-and-qwen__career_pilot__checkpoint-594dfdcf.jsonl` is a different
  checkpoint, not a repeat, and was not analysed here.
- **Any accuracy claim ("correct", "base correct", "unneeded asks").** These depend on the
  author's draft labels. No human or independent labels exist.
- **Whether Nimble's 0/30 omission asks is a limitation of decision-only models.** Nothing here
  tests it, so it is not available. `docs/findings.md` §3 attributes it to Nimble's training data
  without citing evidence. Testing it would need that training data or a differently trained
  adapter.
- **Whether Qwen's omission asks reflect noticing the missing fact.** Its asks on complete prompts
  (8/30) and on reframes (12/30) are similar in rate to its asks on omissions (10/30). Omissions
  are also shorter than the base prompts. Prompts with matched lengths do not exist yet.
- **The career_v2-only split as a separate finding.** Twenty scenarios and one sample are too few.
  The split above is descriptive only.
