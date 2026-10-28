# Results index

Raw model outputs, one JSON line per model × scenario × variant (× condition, × sample
where present). Files are named `<model>__<scenario set>.jsonl` and sit in one folder per
study. Findings and numbers: [`docs/findings.md`](../docs/findings.md).

**Status** uses the terms from [`PROTOCOL.md`](../PROTOCOL.md):

- **legacy**: five-variant career runs and the AITA run, fixed option order, one sample,
  draft labels;
- **exploratory**: run before blind labels exist, or a secondary analysis;
- **confirmatory-pending**: none yet. Confirmatory runs need blind labels, five samples
  and randomized option order.

**Settings** are read from the files. "Fixed order" means the rows have no
`option_order` field and the options were shown in the scenario file's order. Claude
rows have `sample: 0` unless noted; the Nimble/Qwen rows have no `sample` field (one
pass). All Claude refusals have `stop_reason: "refusal"` and category `cyber`.

Model names in the `model` field: `claude-opus-5`; `bespoke-nimble-9b@bd792f44` (current
checkpoint); `bespoke-nimble-9b@594dfdcf` (original checkpoint, one file only);
`qwen3.5-9b-base-same-scorer` (the base model through Nimble's scorer).

Runner scripts are in [`scripts/run/`](../scripts/run), analysis scripts in
[`scripts/analysis/`](../scripts/analysis). Dates are run dates where known, otherwise
the date the file was first committed.

## career/

Legacy single-turn runs on the 30 career scenarios: base, pressure, reframe,
relevant_update, omission (no factual negatives).

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__career_pilot.jsonl` | claude-opus-5, constrained + conversational | `career_pilot` (10 scenarios × 5 variants; 100 rows) | fixed order, sample 0; 3 refusals; rows have no `refusal` field | committed 2026-09-28 | `run_chat.py` | `metrics.py`, `discrimination.py`, `report_tables.py` | legacy |
| `claude-opus-5__career_v2.jsonl` | claude-opus-5, both conditions | `career_v2` (20 × 5; 200 rows) | fixed order, sample 0; 13 refusals | committed 2026-09-28 | `run_chat.py` | same | legacy |
| `nimble-and-qwen__career_pilot.jsonl` | Nimble @bd792f44, Qwen base | `career_pilot` (10 × 5 per model; 100 rows) | fixed order, one pass, full option probabilities | 2026-09-26 | `run_nimble.py` | `metrics.py`, `discrimination.py`, `report_tables.py`, `artifact_probe.py` (part D) | legacy |
| `nimble-and-qwen__career_v2.jsonl` | Nimble @bd792f44, Qwen base | `career_v2` (20 × 5 per model; 200 rows) | same | 2026-09-26 | `run_nimble.py` | same | legacy |
| `nimble-and-qwen__career_pilot__checkpoint-594dfdcf.jsonl` | Nimble @594dfdcf, Qwen base | `career_pilot` (100 rows) | same | 2026-09-22 (pilot) | `run_nimble.py` with the original checkpoint | not used in any current table | legacy; superseded checkpoint |

## aita/

Base and pressure on 50 r/AmItheAsshole posts judged YTA (built from ELEPHANT's data by
`scripts/data/build_aita.py`; the scenario file is not checked in).

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__aita_pressure.jsonl` | claude-opus-5, both conditions | `aita_pressure` (50 posts × base, pressure; 200 rows) | fixed order, sample 0; no refusals | committed 2026-09-28 | `run_chat.py` | `metrics.py --labels data/derived/aita_pressure.jsonl` | legacy |
| `nimble-and-qwen__aita_pressure.jsonl` | Nimble @bd792f44, Qwen base | `aita_pressure` (200 rows) | fixed order, one pass, probabilities | committed 2026-09-28 | `run_nimble.py` | same | legacy |

## pressure_controls/

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__pressure_controls.jsonl` | claude-opus-5, both conditions | `data/derived/pressure_controls.jsonl`, 30 scenarios: base, pressure, reframe, relevant_update, omission, pref_target, pref_target_1p, mention_target, pref_base (29 scenarios), filler; 598 rows | fixed order, sample 0; 81 refusals | 2026-10-03 | `run_chat.py` | `steering.py` (part 1) → `summaries/pressure_controls_claude.txt` | exploratory |

The Nimble/Qwen run on the controls (`nimble-and-qwen__pressure_controls.jsonl`) and the
steering outputs (`results/steering/`) do not exist yet; `scripts/run/run_gpu_experiments.sh`
produces both.

## pushback/

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__pressure_controls.jsonl` | claude-opus-5, constrained only | 30 scenarios of `data/derived/pressure_controls.jsonl`; branches `first`, `pushback_pref`, `pushback_plain`, `correction_fact`, `correction_reframe`, `escalate` (233 rows) | multi-turn; rows have `branch`, `turn`, `first`, `target` instead of `variant`/`condition`/`sample`; fixed order; 1 refusal (`career_15`, turn 1) | 2026-10-03 | `run_pushback.py` | `pushback.py` → `summaries/pushback_claude.txt` | exploratory |

## refusals/

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__career_recheck.jsonl` | Claude Opus 5 (rows have no `model` or `condition` field) | 3 refused legacy career cells: `career_01` reframe, `career_07` reframe, `career_04` relevant_update (conversational in the legacy run) | 3 tries each (`try` 0–2); 9 rows, all refused | committed 2026-09-28 | no script in the repo | read directly | legacy |
| `claude-opus-5__pref1p_recheck.jsonl` | claude-opus-5 | the 36 refused `pref_target_1p` calls from the pressure-controls run (22 conversational, 14 constrained) | 3 samples each (`sample` 0–2); 108 rows, all refused | 2026-10-03 | `recheck_refusals.py` | read directly | exploratory |
| `claude-opus-5__refusal_ablation.jsonl` | claude-opus-5, both conditions | `data/derived/refusal_ablation.jsonl`: 29 scenarios (no `career_15`) × base + 8 one-change lines; 522 rows | fixed order, sample 0; 161 refusals | 2026-10-03 | `run_chat.py` (`SCENARIOS=data/derived/refusal_ablation.jsonl`) | read directly (counts in `docs/findings.md`) | exploratory |

## subthreshold/

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__career30.jsonl` | claude-opus-5, both conditions | all 30 career scenarios, base + subthreshold_update; 120 rows | fixed order, sample 0; 4 refusals (`career_15`) | 2026-10-14 | `run_chat.py` (run when the variant was still called `irrelevant_update`; rows relabeled on 2026-10-21) | `discrimination.py` together with the two Claude career files | exploratory |

## threshold_sweep/

| file | models | scenario set | settings | date | produced by | analyzed by | status |
|---|---|---|---|---|---|---|---|
| `claude-opus-5__threshold_sweep.jsonl` | claude-opus-5, both conditions | `data/derived/threshold_sweep.jsonl`: 8 sweeps × 8 levels × {none, `_pl`, `_ph`}; 384 rows | randomized option order (`option_order` on every row, seed 1684), sample 0; 2 refusals | 2026-10-21 | `run_chat.py` | `threshold.py` → `summaries/threshold_sweep_opus.txt` | exploratory |

`thr_commute` result rows were renamed (`_pl` ↔ `_ph`) after the run, when its option
labels were found inverted; no prompt changed. See
[`docs/findings.md`](../docs/findings.md#13-threshold-sweep-exploratory).

## summaries/

Saved stdout of the analysis scripts.

| file | what | inputs | produced by | date | status |
|---|---|---|---|---|---|
| `report_tables.txt` | every number in the midterm report's main table, plus per-variant AUROCs, paired bootstrap, McNemar and sign tests | the four `career/` files at checkpoint @bd792f44 and Claude's | `report_tables.py` (no arguments) | 2026-10-14 | legacy |
| `discrimination_career30.txt` | relevant update vs. pressure/reframe: hit, false alarms, d′, AUROC, TV, movement ratio, pressure flips by base margin | the four `career/` files | an **older version** of `discrimination.py`; the current script prints different columns (`d_soc`, `auc_s`, no ratio) with the same values where they overlap | 2026-10-03 | legacy |
| `pressure_controls_claude.txt` | per-control change and to-target rates | `pressure_controls/claude-opus-5__pressure_controls.jsonl` | `steering.py` | 2026-10-03 | exploratory |
| `pushback_claude.txt` | per-branch change rates, escalation, turn-2 d′ | `pushback/claude-opus-5__pressure_controls.jsonl` | `pushback.py` | 2026-10-03 | exploratory |
| `artifact_probe.txt` | surface-cue probe, parts A–D | the scenario files, plus the two Nimble `career/` files for part D | `artifact_probe.py results/career/nimble-and-qwen__career_pilot.jsonl results/career/nimble-and-qwen__career_v2.jsonl` | 2026-10-14; regenerated 2026-10-21 with both factual negatives | exploratory |
| `threshold_sweep_opus.txt` | accuracy, NMI rate, switch point, pressure shift per sweep | `threshold_sweep/claude-opus-5__threshold_sweep.jsonl` | `threshold.py` | 2026-10-21 | exploratory |

## logs/

Progress logs from the Claude runners: one line per scenario and variant (or per
scenario for pushback), `ok` when written. They hold no results. There are no logs for
the Nimble runs or for the career refusal recheck.

| file | run |
|---|---|
| `claude-opus-5__career_pilot.log` | `career/claude-opus-5__career_pilot.jsonl` |
| `claude-opus-5__career_v2.log` | `career/claude-opus-5__career_v2.jsonl` |
| `claude-opus-5__aita_pressure.log` | `aita/claude-opus-5__aita_pressure.jsonl` |
| `claude-opus-5__pressure_controls.log` | `pressure_controls/claude-opus-5__pressure_controls.jsonl` |
| `claude-opus-5__pushback.log` | `pushback/claude-opus-5__pressure_controls.jsonl` |
| `claude-opus-5__pref1p_recheck.log` | `refusals/claude-opus-5__pref1p_recheck.jsonl` |
| `claude-opus-5__refusal_ablation.log` | `refusals/claude-opus-5__refusal_ablation.jsonl` |
| `claude-opus-5__career30_subthreshold.log` | `subthreshold/claude-opus-5__career30.jsonl` (still uses the old variant name `irrelevant_update`) |
| `claude-opus-5__threshold_sweep.log` | `threshold_sweep/claude-opus-5__threshold_sweep.jsonl` |

## nimble_overlap/

| file | contents | produced by | date | status |
|---|---|---|---|---|
| `summary.json` | Overlap audit of the 330 career prompts against Bespoke-Nimble's published train/eval data: lexical similarity, shared n-grams, topic, pressure-like and abstention-like records. It contains no model output. | `scripts/analysis/nimble_overlap.py` | 2026-10-28 | audit; read in [`docs/NIMBLE_OVERLAP_AUDIT.md`](../docs/NIMBLE_OVERLAP_AUDIT.md) |

## Model-size ladder (partial)

[`scripts/run/run_model_ladder.sh`](../scripts/run/run_model_ladder.sh) runs Claude
Haiku 4.5, Sonnet 5.5 and Opus 5 with randomized option order (seed 1684) and one
sample, on 2026-10-21. Exploratory until blind labels exist. The runs stopped when the
API account ran out of credits. They also shuffled option order per variant, which
confounds answer changes (see [`docs/findings.md`](../docs/findings.md#8-corrections)), so rerun the whole
ladder with the current runner (`OVERWRITE=1 bash scripts/run/run_model_ladder.sh`)
rather than resuming.

| File | Status |
|---|---|
| `career/claude-haiku-4-5-20251001__career30.jsonl` | complete: 210/210 prompts × 2 conditions |
| `career/claude-sonnet-5-5__career30.jsonl` | complete: 210/210 |
| `career/claude-opus-5__career30.jsonl` | **partial: 130/210** (Opus rerun; its legacy career runs used fixed option order) |
| `threshold_sweep/claude-haiku-4-5-20251001__threshold_sweep.jsonl` | complete: 192/192 |
| `threshold_sweep/claude-sonnet-5-5__threshold_sweep.jsonl` | **partial: 77/192** |
| `logs/<model>__ladder.log` | one per model; they include the container restart and the credit error |

Summaries: [`summaries/model_ladder_career30.txt`](summaries/model_ladder_career30.txt)
(`replicates.py`) and [`summaries/threshold_sweep_ladder.txt`](summaries/threshold_sweep_ladder.txt)
(`threshold.py`). `career30` concatenates the pilot and v2 scenario files, which keeps
these files apart from the legacy ones.
