# Overlap audit: career scenarios vs Bespoke-Nimble's published training data

**Status.** Done before any GPU spending on the Nimble-vs-Qwen comparison, and before any
new model output. Nothing in the scenarios was changed because of it.

**Inputs.**
- **Ours:** all 330 prompts the experiment would show. That is the 30 career scenarios ×
  7 variants, plus 4 control phrasings from `data/derived/pressure_controls.jsonl`
  (`mention_target`, `pref_target`, `pref_target_1p`, `filler`). Each prompt includes the
  question text.
- **Nimble:** `bespokelabsai/nimble` at `4edb0703`. That covers `data/train.jsonl` (2,676)
  and `data/eval.jsonl` (324). For each record we compared the state text, the
  instructions and the criteria.

**Reproduce.** `python3 -I scripts/analysis/nimble_overlap.py <nimble clone> results/nimble_overlap/summary.json`.
The clone is read as data only, and none of its code is imported. All numbers below come from
`results/nimble_overlap/summary.json`.

## Findings

| check | result | reading |
|---|---|---|
| **Lexical similarity** (TF-IDF word 1–2-grams, cosine with the nearest Nimble record) | max **0.082**, median 0.032, 95th percentile 0.052 | Very low. For scale, every career prompt is more similar to some *other* career scenario (min 0.068, median 0.120) than to its nearest Nimble record; **0 of 330** prompts are closer to Nimble. |
| **Option texts** (cosine with the nearest Nimble record) | max 0.066 | Very low |
| **Verbatim overlap** (longest word n-gram shared with any Nimble record) | max **4 words**, e.g. "and the hiring manager", "at the same", "a 15 minute" | Only stock phrases; nothing copied |
| **Nearest domain** | 150/330 prompts have a workplace record as nearest neighbour, at cosine ≤ 0.08 | The nearest topic is workplace, but the similarity is negligible |
| **Topic.** What Nimble's workplace domain contains (300 records, 4 source families, all in train) | Operational compliance and routing: shift-handoff completeness (`workplace-01`), **interview-loop scheduling** under an approval policy (`workplace-02`), change-request review (`workplace-03`), work-package acceptance (`workplace-05`) | No personal career-advice decisions. The closest family, `workplace-02`, schedules a hiring loop from the organizer's side; it is not a candidate deciding about a job. |
| **Topic keywords** in any Nimble record | "promotion" 100 (mostly `promotional_credit` in commerce), "interview" 94, "startup" 46, "hiring manager" 30; "salary", "resign", "quit", "job offer", "relocat", "severance", "layoff", "equity" **0** | Career-decision vocabulary is absent |
| **Pressure-like text** (preference / reassurance requests). The detector catches **30/30** of our pressure sentences and flags 0/30 base prompts. | **0** Nimble records | Nimble never saw a person asking to be told a particular answer |
| **Abstention-like options** (hold / request / clarify / missing codes) | a loose keyword match finds such a code offered in 402 records and as the reference answer in 95. That match over-counts: it also catches codes like `promotional_credit_missing`. Reading the reference answers, about 50 training examples are clearly "hold the decision or obtain the missing evidence", e.g. `pipeline_integrity_hold` (22) and the service-desk route to obtain missing evidence (15) | Nimble *is* trained to hold or request evidence when it is missing, through domain-specific options rather than a generic ask (correction of 2026-10-28) |
| **Task shape** | Every Nimble example comes from a base/counterfactual pair in which one changed fact flips the answer (1,500 + 1,500). Each applies an explicit rule to verified facts. | The same *structure* as our `relevant_update` contrast, in a different genre |

## Conclusion

- **No content leakage.** There are no near-duplicates, no shared passages and no career-advice topic.
  Our scenarios are out of domain for Nimble's published training data. This holds even for
  the workplace category.
- **Two task-shape similarities are confounds to name, not leakage.**
  1. Nimble was trained on minimal pairs in which one fact flips the answer. A
     Nimble advantage on relevant vs irrelevant updates would therefore be the trained
     skill transferring to a new genre. It would not come from having seen these items.
  2. Nimble was trained to pick hold or request codes when evidence is missing. A Nimble
     advantage on omission asks has the same reading.
- **No pressure training.** Nimble's published data has no examples of a preference
  request. Any pressure resistance it shows is not trained on similar text.

## Limit: which checkpoint the audit covers

The published 2,676 examples are the training set of the **original release**
(`original-2676` tag, HF revision `594dfdcf`). The current `main` checkpoint is
`bd792f44`. It replaced the original on 2026-09-24 and was used in the legacy runs, but the
Nimble README says its methodology section "documents the original release's data and
recipe". It does not describe the training data of the latest checkpoint. (The training notes
also mention a separate v2 model trained on 150 unpublished extra examples.)
**This audit therefore cannot certify `bd792f44`.** The preregistration
(`docs/PREREGISTRATION_DECISION_PROCEDURES.md`) uses `594dfdcf`, the checkpoint whose
training data this audit covers.
