# Overnight runner

This runs a **finite** queue of headless Claude Code passes on a separate branch and
worktree. Each pass is verified before it is kept, and the run ends with
`docs/overnight/MORNING_BRIEF.md`. It does not loop, launch GPUs, call paid APIs, push or
merge.

| pass | writes | turn cap | timeout |
|---|---|---|---|
| 01 research verdict | `docs/overnight/01_RESEARCH_VERDICT.md` (cannot see `00_INITIAL_ASSESSMENT.md`) | 60 | 60 min |
| 02 existing evidence | `02_EXISTING_EVIDENCE.md`, `docs/overnight/analysis/` | 80 | 90 min |
| 03 implementation audit | `03_IMPLEMENTATION_AUDIT.md` (no code changes) | 80 | 90 min |
| 04 safe fixes (requires 03) | `04_IMPLEMENTATION_CHANGES.md`, experiment code and tests, `scripts/data/labeling.py`, `docs/PREREG_AMENDMENT_*.md`, a blank labelling packet | 100 | 120 min |
| 05 morning brief (always runs) | `MORNING_BRIEF.md`, ending in `VERDICT: GO / NO-GO / INCONCLUSIVE` | 30 | 30 min |

## Run it

From your local clone, with Claude Code logged in:

```sh
git fetch origin && git checkout cs1684/overnight-loop
python3 -m pip install -e 'research/warranted_revision[dev,v2]'   # pytest, pydantic, scikit-learn
python3 -m pytest -q scripts/overnight/test_overnight.py           # runner tests (fake CLI)
python3 scripts/overnight/overnight.py run --smoke                 # ~2 min real check, read-only
python3 scripts/overnight/overnight.py run --hours 8               # the overnight queue
```

- **Where it runs.** It creates the worktree `../when-should-advice-change-overnight` on a
  new branch `overnight/<date-time>`. Your checkout is not touched.
- **Resuming.** If the run is interrupted (Ctrl-C, a closed lid, a usage limit), rerun the
  same command. Completed passes are skipped, and the interrupted pass's partial changes are
  stashed.
- **Progress.** `python3 scripts/overnight/overnight.py status --worktree ../when-should-advice-change-overnight`
- **In the morning:**
  - read `docs/overnight/MORNING_BRIEF.md` in the worktree;
  - check `git log` there;
  - push the branch yourself if you want to keep it.
- **Useful options:**
  - `--model` sets the model;
  - `--max-budget-usd` applies only if you use API billing;
  - `--no-session-persistence`;
  - `--keep-api-key`. By default `ANTHROPIC_API_KEY` is removed from the environment, so
    the run uses your Claude Code login.
- **Usage.** The runner uses your Claude Code plan's usage, not the $95 GPU budget. A full
  run is at most about 350 turns. Each attempt's reported cost is in `.overnight/state.json`.

## Safeguards (all tested in `test_overnight.py`)

- **Isolation.** A dedicated worktree and branch, and one runner at a time (pid lock).
- **Least privilege.**
  - `--permission-mode dontAsk` with explicit allow rules: read-only tools, plus `Edit(...)`
    limited to each pass's own paths.
  - Deny rules for git history and branch commands, push, `rm`, Brev, `gh`, `curl`, `pip`,
    `ssh`, nested `claude`, and edits to protected paths.
  - `--strict-mcp-config`, so no connectors are loaded.
  - Brev, Hugging Face, GitHub, AWS and API-key variables are removed from the agent's
    environment.
- **Verification after every pass,** independent of the agent:
  - the output file exists with the required headings;
  - every changed path is inside the pass's scope;
  - no protected path changed (data, results, frozen configs, the preregistration, the
    reports, this runner);
  - pass 04 must pass the test suite and the frozen-file lock check, and a re-lock needs a
    `docs/PREREG_AMENDMENT_*.md`.
- **Failures.**
  - A rejected attempt is saved as a patch, stashed (recoverable) and retried once, with
    the reason given to the agent.
  - A protected-path change stops the queue.
  - A usage or rate limit waits 15 minutes and allows one extra attempt.
- **Bounded.**
  - A wall-clock deadline (`--hours`), with time reserved for the brief.
  - Per-pass turn caps and timeouts that kill the process group.
  - A pass that depends on a failed pass is skipped.
  - If the brief itself fails, the runner writes a plain status brief ending in
    `VERDICT: INCONCLUSIVE`.

**Limit.** Python is allowed, because the reanalysis and tests need it, and Python can write
files anywhere. The post-pass check catches any such write inside the repository. Writes
outside it are not prevented, so only run this on a machine and account you trust it with.
