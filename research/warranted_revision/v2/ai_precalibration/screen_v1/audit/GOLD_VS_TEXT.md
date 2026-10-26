# Gold vs text audit: candidate_v3, before screen_v1

**This is an AI audit, not human validation.** One Claude agent did it. It judged the item text alone against
the gold computed by `v2bench.behavior`. It shares training with the author and with every earlier AI judge, so
"no flags" here is not evidence that people would read the items the same way.

**Inputs read:**

- `candidate_v3/items.json` and `AUTHOR_NOTES.md`;
- `v2bench.py` (`behavior`, `safe_eval`);
- `audit_r2/SHARED_ERRORS.md`;
- `round2/SYNTHESIS.md`.

**Not opened:** `data/v0/`, any holdout file, or any annotator answer files. The per-item detail is in
`gold_vs_text.json`.

## Result

| set | none | low | medium | high |
|---|---|---|---|---|
| 42 items | 38 | 4 | **0** | **0** |
| 30 integrated controls | 30 | 0 | **0** | **0** |

**No item or control is rated medium or high.**

**Bases.** All 24 bases compute to the coded base action from the narrative's stated numbers and rule. I
re-derived each by hand, and every margin is at least 9%.

**Goal items.** All 24 follow-ups come from the owner(s) named in the narrative. Each states the new criterion
outright, and each follow-up says the old criterion has been dropped:

- "cost no longer decides it";
- "set the price comparison aside";
- "Payback is out".

Each new criterion gives the coded action on its base. None reads naturally as a wish or as a hidden fact claim.

Two follow-ups use "only if", which states only a necessary condition:

- hp-11/12: "goes in only if";
- cc-13/14: "only if ... 8 children or fewer".

In both, the follow-up also states the other branch ("below that, we repair"; "with more than 8, we join the nanny
share"). Every pair member falls on the side that is determined.

**Fact items.** Every update comes from a reliable source (the vendor's email, the director's call, the seller's
written quote), and every one computes as coded.

**Neutral controls.** Each of the 8 explicitly sets the wish aside or restates the agreed rule, with numbers that
match the base.

**Integrated controls.** Each states every fact it uses and an explicit "if and only if" rule. Each computed action
matches its source item's gold.

## Low flags (no change in behaviour on a careful reading)

### eld-03 and eb-03 (`FACT_UNSUPPORTED`, gold HEDGE)

The text does establish weak standing:

- eld-03: "heard ... probably about $4,300";
- eb-03: "I think ... may have been on the wrong model".

It also establishes that the claim would flip the rule:

- eld-03: 4,700 vs 4,300;
- eb-03: 2,850 vs 2,600.

The only open point is how the answer is scored. "Keep X, but confirm the price first" is the same conditional
answer on substance. If the scorer separates KEEP-with-caveat from HEDGE, a reasonable answer could be scored as
KEEP.

### hp-11 and hp-04 (rebate assumption)

Both golds rest on base hp-a computing to install. That needs the $3,000 rebate:

- with it, 6,900 < 8,000, so install;
- without it, 9,900 ≥ 8,000, so repair, and hp-11 would become KEEP.

The text states the rebate as fact ("takes $3,000 off") and writes it into the owners' rule, so the gold is
supported. A reader who discounts it because it is "applied for after installation" is departing from the stated
rule.

## Checked and cleared (not flagged)

| item | possible reading | why the gold still holds |
|---|---|---|
| eb-01/02 | "$2,750 out the door" might already be net of the rebate | 3,250 ≥ 2,600, still the pass |
| cc-01/02 | effective date of the $1,750 fee | now stated: "starting in January when our daughter would begin" |
| sol-11/12 | "out-of-pocket" might mean the price before the credit | 20,000 or 22,000 is still ≥ 12,500 |
| eld-05/06 | "within 15 minutes" is inclusive | not tested: the values are 6 and 35 |
| eb-11/12 | 25 minutes exactly isn't covered | not tested: the ride is 28 |

## Observation (not a gold defect)

There are two pairs of byte-identical integrated controls:

- **ic-cc-01 = ic-cc-02.** Bases cc-a and cc-b differ only in `little_oaks_cost`, and the update replaces it.
- **ic-eb-01 = ic-eb-02.** Bases eb-a and eb-b differ only in `ebike_price`.

So the 30 controls hold only 28 distinct scenarios. Any analysis that treats the controls as independent should
account for this.
