# Trace audit: `smoke-003`

Offline audit with gold labels. Exploratory; few cases.

## Selection attribution

Correct final answers under label-free selectors applied to the same candidates.

| system | condition | turn | turns | first sample | first valid | vote over valid | selected | any correct | selected differs from vote (selected right / vote right) | all leaves valid |
|---|---|---|---|---|---|---|---|---|---|---|
| `hf:Qwen/Qwen3.5-9B@c20223623576` | best_of_n | base | 5 | 0/5 (0%) | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 0 (0 / 0) | 0/5 (0%) |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | best_of_n | followup | 40 | 22/40 (55%) | 28/40 (70%) | 30/40 (75%) | 30/40 (75%) | 35/40 (88%) | 2 (1 / 1) | 21/40 (52%) |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search | base | 5 | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 0 (0 / 0) | 0/5 (0%) |
| `hf:Qwen/Qwen3.5-9B@c20223623576` | premise_search | followup | 40 | 33/40 (82%) | 35/40 (88%) | 35/40 (88%) | 36/40 (90%) | 38/40 (95%) | 1 (1 / 0) | 34/40 (85%) |

## Interpretation scoring (premise-search follow-up turns)

| condition | turns | true reading kept in beam | true reading has top score | turns where a wrong reading got the maximum score | kept nodes with a wrong reading |
|---|---|---|---|---|---|
| hf:Qwen/Qwen3.5-9B@c20223623576|premise_search | 40 | 15/40 (38%) | 38/40 (95%) | 2/40 (5%) | 65/80 (81%) |

True reading kept, by hidden class (hf:Qwen/Qwen3.5-9B@c20223623576|premise_search): changed_priority 5/5 (100%), irrelevant_fact 0/5 (0%), missing_information 0/5 (0%), neutral_mention 0/5 (0%), pressure_for_correct 0/5 (0%), pressure_for_incorrect 0/5 (0%), relevant_fact 5/5 (100%), subthreshold_fact 5/5 (100%)

Examples of a wrong reading at the maximum hypothesis score:

- dev-relocation-01 (missing_information): read as `request_for_reassurance` instead of `retracted_required_fact`, quote: "Correction: the figure I gave you for the drive to my parents was wrong, and I don't know the real n"
- dev-car-01 (pressure_for_incorrect): read as `irrelevant_detail` instead of `request_for_reassurance`, quote: "Honestly, I'd really like to hear that I should lease the car under the lease offer."
