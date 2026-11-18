# Are You Sure About That?

**When should an AI change its answer? And does asking "look again" help?**

University of Pittsburgh, CS 1684. Status: research in progress. All results are exploratory.

## The problem

You ask an AI for advice. It gives an answer. You ask it to look again. It gives a different answer.

Was the change good or bad? It depends on the reason.

- New facts can make a change right.
- A request to agree with you should not.
- Plain doubt ("are you sure?") should not.

A good advisor changes its answer for good reasons only. We test if AI models do this.

## Our questions

1. **Instability.** How often does an answer change when the facts do not change? How often is it just noise?
2. **Pressure.** Does a user's wish push the answer toward that wish?
3. **Second look.** Does "please look again" fix a wrong answer? Or does it break a right one?
4. **Real questions.** Do these results hold on questions that people wrote?

## What we found

Most results come from generated scenarios. The last two bullets also use 1,200 public questions (MedQA and CommonsenseQA). See the cautions below.

- **Noise is large.** If we only change the order of the options, 6% to 14% of answers change in the 9B models.
- **Changes happen near the boundary.** For the Nimble model, answers flip more when the two options are almost equal.
- **Pressure works, but so does naming an option.** Naming an option with no stated wish also moves the answer.
- **A planted wrong answer is easy to fix.** Capable models fix it 98% to 99% of the time.
- **A model's own wrong answer is harder to fix.** It depends on the model.
  - Weaker models (Llama 3.1 8B, Mistral 7B) stay anchored. A fresh try in a new chat fixes more than a re-ask in the same chat.
  - Stronger models (Haiku 5.5, GPT-5.4 Mini) fix more with "look again" than with a fresh try. They also break some right answers. Overall, accuracy goes down a little.
  - Gemma 2 9B fixes 38% of its errors and breaks 51% of its right answers. Asking it to double-check is a clear net loss.
- **The plain wording is safe.** "Give me your final recommendation" changes almost nothing.

**Practical advice:** do not tell a model to "look again" when it is probably right. If you want a second try from a weak model, start a new chat.

Details: [`docs/second_look.md`](docs/second_look.md) and [`docs/instability_thesis.md`](docs/instability_thesis.md).

## Cautions

- The scenarios are templates. The correct answer comes from a formula. No person has checked them.
- Most runs use one prompt wording per test.
- Models with few own errors have wide error bars.
- The related-work notes in [`docs/literature.md`](docs/literature.md) are not fully verified.
- We have not yet run blind human labels.

## Real-world check

We tested the second-look results on two public question sets (MedQA and CommonsenseQA). Five models finished. The weak-model result held. The strong-model result changed, as the bullets above show. Details: [`docs/real_world_check.md`](docs/real_world_check.md).

Still open: 60 advice questions are drafted, but two people must label them blind. We cannot call them a human check before that. Gemma 4 31B did not finish.

## How we test

Each scenario is a choice between options. Some facts have weights. The best option is known.

We change the prompt in one way at a time:

| Change | What changes | Right behavior |
| --- | --- | --- |
| Relevant update | A fact that matters | Change the answer |
| Irrelevant update | A fact that does not matter | Keep the answer |
| Pressure | A request for one option | Keep the answer |
| Reframe | The wording only | Keep the answer |
| Omission | A key fact is removed | Ask for more information |
| Second look | "Please look again" | Keep a right answer. Fix a wrong one. |

We also reorder the options. This gives a noise floor: the change rate with no real change.

Two data sets exist:

- 30 hand-written career scenarios.
- 400 generated scenarios in four areas: career, housing, medical choice, purchase. See [`docs/procedural_scenarios.md`](docs/procedural_scenarios.md).

## Models

- Bespoke-Nimble-9B and Qwen3.5-9B (run on a GPU).
- Chat models through an OpenAI-compatible API: Mistral 7B, Gemma 2 9B, Gemma 4 31B, Llama 3.1 8B, GPT-5.4 Mini, Haiku 5.5.

## Repository guide

| Path | Contents |
| --- | --- |
| [`docs/second_look.md`](docs/second_look.md) | Second-look experiments: designs, results, cautions |
| [`docs/instability_thesis.md`](docs/instability_thesis.md) | Instability thesis and first results |
| [`docs/real_world_check.md`](docs/real_world_check.md) | Plan and log for the real-world check |
| [`docs/literature.md`](docs/literature.md) | Related work |
| [`docs/findings.md`](docs/findings.md) | Earlier career results and corrections |
| [`PROTOCOL.md`](PROTOCOL.md) | Evaluation plan and reporting rules |
| [`data/scenarios/`](data/scenarios/) | Scenarios (career, generated, real-world) |
| [`scripts/data/`](scripts/data/) | Scenario builders and validators |
| [`scripts/run/`](scripts/run/) | Model runners and GPU setup |
| [`scripts/analysis/`](scripts/analysis/) | Metrics and analysis |
| [`results/`](results/) | Raw outputs and summaries. See [`results/README.md`](results/README.md). |
| [`report/`](report/) | Project report |

## Getting started

Use Python 3.11. Run commands from the repository root.

Check the generated scenarios:

```bash
python3 scripts/data/validate_procedural.py
```

Run the second-look test on one model. It makes API calls and costs money.

```bash
CHAT_BACKEND=openai CHAT_BASE_URL=<url up to /v1> CHAT_API_KEY=<key> \
CHAT_MODEL=<model id> \
python3 scripts/run/run_second_look.py --n 200 --yes
```

Without `--yes`, the script makes no calls. Use `--dry-run` to see the prompts.

Run a model's own-error test on the real-world sets:

```bash
CHAT_BACKEND=openai CHAT_BASE_URL=<url> CHAT_API_KEY=<key> CHAT_MODEL=<model id> \
python3 scripts/run/run_own_error_reask.py \
  --scen-dir data/scenarios/realworld --pools medqa=medqa.jsonl,csqa=csqa.jsonl --yes
```

The 9B GPU models need a GPU. See [`scripts/run/brev_setup.sh`](scripts/run/brev_setup.sh) and [`docs/gpu_budget.md`](docs/gpu_budget.md).

Never put an API key in the repository.

For a formal comparison, follow [`PROTOCOL.md`](PROTOCOL.md). Do not mix exploratory and confirmatory results.

## Planned work

We plan to test if a model decides better when it first states its facts and assumptions. We will compare this with best-of-N sampling as a control. Nothing from this plan is a result yet.

## Team

Shreyash Ranjan, Insiah Kizilbash, Haiden Hunter, Greg Betron  
University of Pittsburgh
