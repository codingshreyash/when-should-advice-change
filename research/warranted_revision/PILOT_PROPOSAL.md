# Pilot proposal: does premise search beat best-of-N? (not launched)

Status: proposal only, waiting for approval. Everything here is exploratory: the data are
synthetic, rule-labelled dev scenarios from five families, and no human has reviewed the
labels. The holdout split stays untouched.

## Question

On scenarios where pressure can actually move the model, does premise search pick better
final answers than best-of-N with the same nine calls per turn? "Better" means the two
existing measures:

- **Warranted updates:** base correct and follow-up correct after a relevant fact or an
  explicit priority change.
- **Pressure stability (challenge v1):** base correct and follow-up still correct under the
  six pressure messages (three styles, both directions).

Both are paired by case and option order. Majority vote over the best-of-N candidates is
reported as a free extra comparison (it needs no extra calls), since the trace audit
suggests voting does most of the work.

## Design (smallest that can answer it)

- Data: `data/challenge_v1`, all 20 cases (5 dev families x 4), 11 turns each (base +
  10 follow-ups). Not the v0 set: its pressure items move nothing.
- Arms: `direct` (1 call per turn, a reference), `best_of_n` (9), `premise_search` (9).
- One replicate, with option order rotated across cases (`rotate_order_across_cases`), so
  each option takes each position about equally often.
- Model, decoding and token limits as in format-001 (Qwen3.5-9B @ c2022362, 1024 new
  tokens for ledger calls, 200 for direct, temperature 0.7 for sampled calls).
- Config: `configs/pilot_challenge.json`. Run as 3 shards, one instance each.

| | calls | of which direct / best-of-N / search |
|---|---|---|
| total | 4,180 | 220 / 1,980 / 1,980 |
| shards | 1,463 / 1,463 / 1,254 | |

Optional add-on: the `premise_search_noprov` ablation (+1,980 calls, 6,160 total). It is
what would tell us whether any search advantage comes from provenance scoring rather than
from search structure or voting. I'd include it if the budget allows; without it, a
positive result can't be attributed.

## Tokens and cost

Per-call token means from format-001 (prompt + completion): best-of-N 1,334 + 240; search
hypothesis 1,431 + 264; search decision 1,757 + 308; direct about 460 + 82.

| | tokens (prompt + completion) | completion only |
|---|---|---|
| minimal pilot | about 6.9M | about 1.05M |
| with ablation | about 10.6M | about 1.6M |

Speed: 3.9 s per call measured in format-001 (fast kernels unavailable; see its notes).
L40S at $1.06/h, about 0.5 h setup per instance.

| | inference | instances | expected cost | worst case (controller caps) |
|---|---|---|---|---|
| minimal pilot | about 4.5 h | 3 | about $6.40 | 3 x $3.20 = $9.60 (`max_gpu_usd` 4 per shard) |
| with ablation | about 6.7 h | 4 | about $9.20 | 4 x $4.00 = $16.00 (`max_gpu_usd` 5 per shard) |

Each shard stays under the existing $15 per-run cap and the 4-hour instance limit. The
ablation option's total worst case is above $15 across four instances, so it needs your
explicit OK even though no single run exceeds the cap.

## Stop and failure conditions (decided now)

Don't analyse, and say so, if any of these happen:

- Any arm below 95% strictly valid decisions, or below 90% parsed ledgers (best-of-N,
  search); more than 1% missing outputs; more than 2% token-limit stops; more than 2%
  refusals.
- Planned and made calls differ in any shard, or `aggregate.py` refuses the shards.
- No movement: if `direct` and `best_of_n` both move to the pushed option in under 5% of
  correct-base pressure turns, the challenge set doesn't discriminate either; report that
  and stop.

Stop launching further shards if a shard's instance deletion isn't confirmed, a shard runs
into its deadline, or Brev's actual charge for a shard is more than 25% above its estimate.

## What it can and can't show

There are only five scenario families, and intervals resample families. The pilot can show
direction and rough size. Only a large difference will have an interval that excludes zero,
and a null result won't rule out a modest effect. Positive or negative, it's exploratory and
justifies at most a properly sized, pre-registered follow-up with new families.

## Decisions needed before launch

These change the instrument, so I haven't made them on my own:

1. **Beam tie-break (search algorithm).** Hypothesis scores usually tie, and ties currently
   keep the first readings in a fixed order that favours "new fact" and "changed goal"
   (`results/warranted_revision/audits/FINDINGS.md`). Running the pilot as is tests a
   search that is biased toward changing its answer. Options: (a) break ties with a seeded,
   label-free random order per turn; (b) leave it and report it as a known limitation.
   I recommend (a).
2. **`rule_check.satisfied` wording.** The model reads it as "the user's requirement is met";
   the scorer reads it as "the written comparison is true" (format-001 notes). Options:
   (a) define it in the template as "true if the comparison as written holds"; (b) drop the
   arithmetic component from the score. I recommend (a). It affects both search arms the
   same way.

If you choose (a) for either, I'd run one more small format check (about $0.50) before
the pilot, since both change the prompts or search behaviour.
