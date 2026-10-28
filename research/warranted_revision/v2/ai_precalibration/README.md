# AI-only pre-calibration (v0.1)

**What this is.** A cheap pass to find defects in the benchmark-v2 calibration items before
any human sees them. Every author, annotator, adjudicator and auditor here is an AI agent.

**What this is not.**

- It is **not** the human B1 calibration in `BENCHMARK_V2.md` §8, and it does not pass B1's
  gate. B1 still requires two independent human reviewers and a human adjudicator
  (`v2/annotation/COORDINATOR.md`).
- Nothing here is human validation.
- Agreement between AI annotators is a screening signal, not evidence that the labels are
  valid or that the construct is real. Models that share training data and instructions can
  agree on the same wrong reading.
- Nothing here moves the study to B2 or B3.

## Agents and isolation

| role | model | may read | writes |
|---|---|---|---|
| 1 Scenario author | Claude (session default) | proposal, guidelines, design reports, old draft, tooling | `candidate_v1/` |
| 2 Annotator A | Claude Opus | `packets/annotator_A/` and `GUIDELINES.md` only | `annotations/annotator_A/` |
| 3 Annotator B | Claude Sonnet | `packets/annotator_B/` and `GUIDELINES.md` only | `annotations/annotator_B/` |
| 4 Adjudicator | Claude Opus, fresh context | first `adjudication/blind_input.csv` only; then the anonymised queue | `adjudication/` |
| 5 Shortcut auditor | Claude, fresh context | candidate items (with labels), tooling; not the annotations | `audit/` |

**Model families.** Only Claude models are available in this environment. Annotators A and B
are different Claude models (Opus and Sonnet) from **the same provider and model family**.
Their agreement is therefore a weaker diagnostic than agreement between independent providers
would be: shared training can produce shared blind spots. A second-provider annotator needs a
paid API and is planned, not run (`PROVIDER_PLAN.md`).

**Isolation is by instruction and is audited after the fact. It is not enforced.** All agents
run in the same container and could technically read any file. Each agent was told exactly
which files it may read. After each agent finished, the coordinator counted, in that agent's
transcript, the occurrences of forbidden paths:

- the candidate items;
- the coordinator key;
- the other annotator's folder;
- the old draft;
- the adjudication queue before the blind phase.

The counts are reported in `REPORT.md`. A count can't prove an agent never saw something; it
can only catch violations visible in tool calls.

**Freezing.** Each agent's first output is committed before any later step can see it:

1. author;
2. both annotations;
3. the adjudicator's blind labels, which come before the anonymised queue is released;
4. the auditor's report.

## Layout

```
candidate_v1/        revised 48 items (with design labels and readings) + author notes
coordinator/         answer key for the packets (labels; never given to annotators)
packets/annotator_*  blinded, independently shuffled items and base checks + GUIDELINES copy
annotations/         the two annotators' returned files and notes (frozen)
agreement/           v2bench agree output (inter-model statistics)
adjudication/        blind-first labels, then the full adjudication report
audit/               adversarial shortcut audit (+ v2bench audit outputs)
analysis/            per-label and per-contrast disagreement analysis
PROVIDER_PLAN.md     plan for a second-provider annotator (needs approval)
REPORT.md            findings and recommendation
```
