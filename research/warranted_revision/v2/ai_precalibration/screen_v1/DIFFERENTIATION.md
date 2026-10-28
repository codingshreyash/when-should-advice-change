# What finding would differentiate this work from prior work

This was written before any model output exists. The claims about prior work rest on
`novelty_belieftrack/NOVELTY_AUDIT.md` and `agent_reports/01_novelty.md`; the verification
level of each source is given there.

## Already known (not ours)

- **Two-sided selectivity:** resisting unsupported pressure while keeping warranted updates is
  measured by SycoBench-600 (`Sel`), Belief-R and SycEval.
- **The mitigation trade-off:** Ma et al. 2026 ("Sycophancy Suppression Can Impair Rational
  Updating") show that DPO, SFT and steering against sycophancy reduce updating on **evidence**.
- **Consequence sensitivity to fact updates against computed gold**, including Failed Stay,
  Failed Update and pressure isolation, is in BeliefTrack (Xu et al., EMNLP 2026), with a
  belief-tracking prompt and training methods.

Our v2 fact pairs are a domain adaptation of these, and so is our F condition.

## The one finding that would be new

> Under a prompt that **explicitly licenses** owner-authorized changes of decision criteria
> (condition S), a model still declines a clear, legitimate change of the user's goals more
> often than it declines an equally clear fact update. The autonomy cost appears in both
> wordings and across several families.

Or, for the other side of the same construct:

> The model over-revises on goal changes that, applied correctly, leave the answer unchanged.

**Why this goes beyond prior work.** Ma et al. and BeliefTrack concern evidence about the world.
In their settings no legitimate update comes from the user's own preferences, so they cannot
see this failure. BeliefTrack's own prompt classes "preference-oriented" content as
non-evidence. The S condition also removes the trivial explanation: the instruction told the
model to accept such changes. If suppression appears anyway, it lies in how the model
represents the user's authority, not in the instruction.

## What would **not** differentiate us

- Suppression only under F. That is expected, because F tells the model to ignore preferences.
  It shows the prompt is unsuitable in a new domain, not a new behaviour.
- Fact-update results of any kind (BeliefTrack, Ma et al.).
- Raw difficulty, low accuracy, or prompt and wording sensitivity on their own.
- Agreement among AI annotators or auditors. That is not construct validation.

## If the screen is null

If S shows no autonomy cost and there is no over-revision, the remaining contribution is a
small methods note: a pre-calibration showing the labels are defined by wording, the novelty
audit, and a negative screen. The recommendation in that case is to **stop**, not to redesign
items or prompts until an effect appears.
