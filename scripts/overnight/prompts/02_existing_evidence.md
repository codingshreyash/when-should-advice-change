# Pass 02: reanalysis of existing results (no new model calls)

**Task.** Reproduce the legacy Qwen-vs-Nimble numbers from the raw rows in
`results/career/nimble-and-qwen__career_pilot.jsonl` and
`results/career/nimble-and-qwen__career_v2.jsonl`. Do not copy them from summary tables.
Then compare your numbers with the table in `docs/findings.md` §2 and report any mismatch.

**Analysis scripts** go in `docs/overnight/analysis/` (Python standard library, plus numpy
if installed). The report must give the exact command that produced each number.

**Write `docs/overnight/02_EXISTING_EVIDENCE.md`** with these headings:
- `## Reproduced legacy numbers`
- `## Pressure versus neutral mention`: say which models actually have `mention_target`
  rows (check the files under `results/`). Where a model has none, say the comparison is
  impossible for that model. Do not substitute another contrast.
- `## Relevant versus irrelevant updates`: which models were run on `irrelevant_update`
  at all?
- `## Option order`: the legacy 9B runs used a fixed order. Say what that does and does
  not allow you to conclude.
- `## Abstention and refusals`: include `need_more_information` rates on omission prompts
  *and* on complete base prompts, per model.
- `## Choice changes versus probability changes`: for the scorer rows, how often the
  probability of the pressure target rises when the chosen answer does not change.
- `## Comparisons the existing data cannot support`

**Labelling.** Every number is exploratory: one sample, draft labels, legacy checkpoint
`bd792f44`.
