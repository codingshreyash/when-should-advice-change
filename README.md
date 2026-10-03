# When Should AI Advice Change?

Course project for CS 1684 at Pitt. We're measuring **decision-level sycophancy**:
does a model's recommendation move toward what the user wants to hear when
nothing decision-relevant has changed? And the flip side: does it actually update
when a relevant fact *does* change, and ask for more when a key fact is missing?

Every scenario has a base prompt and four variants:

| Variant | What changes | What a good advisor does |
|---|---|---|
| pressure | user says which option they want | stays put |
| reframe | wording / order only | stays put |
| relevant_update | one fact that should change the answer | updates |
| omission | the fact the decision hinges on is removed | asks for more info |

We score four setups on the same prompts:

- **Bespoke-Nimble-9B**: a LoRA adapter on Qwen3.5-9B that picks an option directly and writes no text
- **Qwen3.5-9B base**: same weights and the same Nimble scorer, just without the adapter
- **Claude Opus 5, constrained**: answers with an option code only
- **Claude Opus 5, conversational**: writes a short paragraph of advice, and we pull the option out of it

The Nimble vs. base comparison is the controlled one: same prompt, same scorer, same
output space, only the adapter differs.

## Results so far

30 career scenarios, scored against our draft labels (blind relabeling is in progress,
so treat these as provisional):

| | Pressure shift | Reframe change | Asks when a fact is missing |
|---|---|---|---|
| Qwen3.5-9B base | 18/29 | 12/30 | 10/30 (but also abstains on 7 complete prompts) |
| Bespoke-Nimble-9B | 11/27 | 3/30 | 0/30 |
| Claude Opus 5, constrained | 0/27 | 1/28 | 9/29 |
| Claude Opus 5, conversational | 0/26 | 0/26 | 8/29 |

On 50 r/AmItheAsshole posts the community judged YTA, the models sided with the poster
86% (Qwen base), 70% (Nimble), and about 50% (Claude) of the time.

Short version: the model that generates no text still caves to pressure, the chat model
doesn't, and Nimble never says "need more information." Details are in our midterm report.

Two things worth knowing if you look at the raw results:

- **Nimble's public checkpoint changed on 2026-09-24.** `results/nimble.jsonl` is the
  original checkpoint (`@594dfdcf`); every other Nimble file is the newer one
  (`@bd792f44`). The model name in each row says which. `scripts/brev_setup.sh` pins
  both the checkpoint and the scoring code now.
- **Claude sometimes refuses ordinary career prompts** under its cyber-safety category
  (16 of 300 career calls). Those rows have `stop_reason: "refusal"` and are excluded
  from rates and counted separately. `results/refusal_recheck.jsonl` shows they repeat.

### Discrimination reanalysis

Putting all four variants on one axis (how far did the answer move?) and asking whether
that movement separates relevant updates from pressure/reframe: the Qwen3.5-9B base model
moves *more* for a stated preference than for a decision-relevant fact (23 of 30
scenarios, sign test p = 0.005; d′ ≈ 0). Nimble separates them better (AUROC 0.71 vs 0.46),
mostly by becoming reframe-stable, but still caves to pressure. Claude reaches d′ ≈ 2.3 in
both conditions. Details and next experiments: `results/discrimination_notes.md`.

Claude stays put under the templated controls too (0 flips toward the target), and in a
second turn it never gives in to "are you sure?" or 3 rounds of pushback (0/29) while
still updating on 25/29 fact corrections (d′ ≈ 3.6). What does change under pressure is
the refusal rate: a first-person "I really want you to tell me …" sentence gets 59% of
otherwise ordinary career prompts refused (cyber category), vs 0% for the base prompt,
and those refusals repeat on every resample (108/108). The biggest single trigger is
the clause "I'm the one deciding here": alone, with no preference stated, it still gets 8
of 29 prompts refused (`results/discrimination_notes.md`).

## Layout

    data/
      pilot_scenarios.jsonl     10 career scenarios (the pilot)
      career_v2.jsonl           20 more, built by scripts/build_career_v2.py
      SCHEMA.md                 scenario record format + rules for writing variants
      LABELING_INSTRUCTIONS.md  how blind relabeling works
      labeling/                 shuffled labeling sheets (answer keys are kept out of the repo)
    scripts/
      build_prompts.py          turns a record into the text each model sees
      build_career_v2.py        source for career_v2.jsonl
      build_aita.py             builds the AITA pressure set from ELEPHANT's data
      validate_scenarios.py     checks the variant-writing rules
      analyze_discrimination.py relevant-vs-irrelevant movement: d', AUROC, bootstrap CIs
      build_pressure_controls.py  templated preference / neutral mention / agreeing pressure / filler controls
      run_steering.py           "user wants X" direction in the 9B models + cross-validated ablation (GPU)
      run_gpu_experiments.sh    all GPU work for the controls + steering study in one go
      run_pushback.py           multi-turn pushback / correction / escalation for Claude
      analyze_steering.py, analyze_pushback.py   tables for the two above
      brev_setup.sh             one-shot GPU box setup (deps, model download, adapter merge)
      run_nimble.py             Nimble + base model, same scorer
      run_chat.py               Claude, conversational + constrained
      analyze.py                the metrics table
      labeling.py               make labeling sheets / score two labelers
    results/                    raw outputs, one JSON line per model x scenario x variant
    COST.md                     rules for not blowing the GPU budget

## Running it

**Nimble and the base model** need one 24 GB GPU (we used an L4). On a fresh Linux box:

    bash scripts/brev_setup.sh                         # ~10 min, mostly the model download
    python scripts/run_nimble.py                       # pilot set, under a minute
    SCENARIOS=data/career_v2.jsonl python scripts/run_nimble.py

Then shut the machine down. Results for any file other than the pilot get the file's name
as a suffix (e.g. `results/nimble_career_v2.jsonl`), so runs never overwrite each other.

**Claude** runs anywhere:

    pip install anthropic
    ANTHROPIC_API_KEY=... python scripts/run_chat.py     # or set CS1684_ANTHROPIC_KEY
    SCENARIOS=data/career_v2.jsonl ANTHROPIC_API_KEY=... python scripts/run_chat.py

If your key isn't scoped to a workspace, also set `ANTHROPIC_WORKSPACE_ID`.

**Analysis**:

    python scripts/analyze.py --labels data/career_v2.jsonl results/nimble_career_v2.jsonl results/chat_claude-opus-5_career_v2.jsonl

## AITA data

The AITA posts come from [ELEPHANT](https://github.com/myracheng/elephant) (Cheng et al.,
2025). We don't redistribute them. To rebuild `data/aita_pressure.jsonl`, download
`datasets.zip` from the OSF link in their README, unzip it into `data/elephant/`, and run:

    python scripts/build_aita.py        # 50 posts, fixed seed

## Team

Shreyash Ranjan, Insiah Kizilbash, Haiden Hunter, Greg Betron
