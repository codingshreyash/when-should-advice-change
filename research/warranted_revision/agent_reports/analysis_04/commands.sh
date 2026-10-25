#!/usr/bin/env bash
# Reproduce agent 4's analysis. Run from research/warranted_revision. Never writes into results/.
set -euo pipefail
S=${SCRATCH:-$(mktemp -d)}
mkdir -p "$S/runs" "$S/audits"
for r in smoke-003 smoke-004 format-001; do
  rm -rf "$S/runs/$r"; cp -r ../../results/warranted_revision/$r "$S/runs/$r"
  for f in decisions predictions search_traces; do
    [ -f "$S/runs/$r/$f.jsonl" ] || gunzip -k "$S/runs/$r/$f.jsonl.gz"
  done
  python3 -m warranted_revision.evaluate --run "$S/runs/$r" --gold data/v0/dev_gold.jsonl
  python3 agent_reports/analysis_04/compare_metrics.py ../../results/warranted_revision/$r "$S/runs/$r"
  python3 -m warranted_revision.trace_audit --run "$S/runs/$r" --gold data/v0/dev_gold.jsonl --out "$S/audits" > /dev/null
done
python3 agent_reports/analysis_04/analyze.py            # base answers, decomposition, selectors, interpretations, positions, ablation pairing
python3 agent_reports/analysis_04/candidates.py         # per-candidate accuracy, pressure capitulation
python3 agent_reports/analysis_04/interp_vs_decision.py # interpretation match vs decision correctness
python3 agent_reports/analysis_04/cases.py              # discordant turns, selected != vote
python3 agent_reports/analysis_04/stats_audit.py        # exact bootstrap, sign-flip p, design effects
echo "scratch: $S"
