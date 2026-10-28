# goal-screen-qwen35-9b-v1

- **GitHub Actions run:** [40412442979](https://github.com/codingshreyash/when-should-advice-change/actions/runs/40412442979), commit `26c7fcb`.
- **Model and box:** Qwen3.5-9B @ `c2022362`, bf16, transformers 5.20.2, torch 2.8.0, one
  NVIDIA L40S (`massedcompute_L40S`, listed at $1.06/h).
- **Files here.** These four JSON files were recovered from the job log. Each prints counts
  and pre-registered metrics only:
  - `analysis.json`, `analysis_primary.json`: pre-registered analysis (all items, primary set);
  - `summary.json`: counts for the full run;
  - `gate.json`: the on-box preflight gate.

  The raw per-call outputs (`calls.jsonl`) and the run manifest are in the run's artifact
  (`warranted-revision-goal-screen-qwen35-9b-v1`, kept 90 days). This session can't download
  artifacts.
- **Preflight gate:** passed. 30/30 calls, 0 errors, 24/24 valid answers, 7.8 s per batch.
- **Full run:** 1,008/1,008 calls, 0 errors, 0 refusals, 7/882 unparseable, 4 truncated at
  400 tokens.
- **Instance:** deleted and confirmed not listed.
- **Pre-registered outcome:** **stop**, with every criterion evaluable.
