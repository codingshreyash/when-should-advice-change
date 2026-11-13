# Literature notes for the instability thesis

Collected by research agents in November 2026. **Most entries were read only as
abstracts or search snippets. Nothing here is verified.** Open each link and read the
paper before you cite it. Rows marked "opened" mean the agent fetched the page; that
still means an abstract in most cases.

## Closest work. Read these first.

| Paper | Id / link | Why it matters | Read? |
|---|---|---|---|
| Big-Big-SycoBench | arXiv 2610.15634 | Reports responsiveness to valid arguments and compliance with invalid ones. Uses a 20-run noise floor. Names stubbornness. Closest to our two-axis design. | agent read most of it |
| Resist and Update (Yang and Yeung) | arXiv 2607.12985 | Reports resist and update as a pair. Has a two-pass fix. Possible overlap with H4. | snippet only |
| SycoBench-600 | aclanthology.org/2026.findings-acl.1759 | Pressure robustness and selective updating together. | snippet only |
| BeliefShift | arXiv 2603.23848 | Trade-off between resisting drift and legitimate updates. | snippet only |
| Counterfactual sycophancy metric | arXiv 2604.02423 | Defines sycophancy as a shift toward the user's stance. Says revising on evidence is rational. | snippet only |
| BASIL (Atwell et al.) | arXiv 2508.16846 | Bayesian view of sycophancy. Closest formal "warranted update". | abstract |
| Shapira, sycophancy as in-context updating | arXiv 2610.28325 | Bears on the preference versus fact split. | snippet only |

BeliefTrack (EMNLP 2026) already measures fact-update sensitivity, so the two-sided
"stay vs update" estimand is published. The team's negative-methods report says this
(`research/warranted_revision/NEGATIVE_METHODS_REPORT.md` on branch
`research/warranted-revision-v1`). We found no link; find and read it.

The midterm report cites FRAGILE (hwang2026framing). An agent searched and could not
find it. Check that reference before the final paper.

## Established results (do not claim as new)

- Prompt format changes accuracy by up to 76 points (Sclar et al., arXiv 2310.11324,
  opened).
- Option order changes results by 13 to 75 percent. The authors guess this happens
  when the model is torn between its top two or three options (Pezeshkpour and
  Hruschka, arXiv 2308.11483, opened). This supports H1.
- "Are you sure?" changes answers about 46 percent of the time and costs about 17
  percent accuracy. Fine-tuning cuts the drop by about 60 percent (Laban et al., arXiv
  2311.08596, opened).
- Sycophancy appears in five assistants and human preference data rewards agreement
  (Sharma et al., arXiv 2310.13548, opened).
- Irrelevant context distracts models (Shi et al., arXiv 2302.00093, opened).
- Moral-judgment surface edits flip 7.5 percent of cases, inside the model's own noise
  of 4 to 13 percent. Point-of-view shifts flip 24.3 percent (van Nuenen and Sachdeva,
  arXiv 2603.05651, opened). Supports the need for a noise floor.
- Stability as a second goal next to accuracy, in clinical abstraction (arXiv
  2601.22373, opened).
- Self-consistency (Wang et al., arXiv 2203.11171) and semantic entropy treat variation
  as noise to vote away or as an uncertainty signal. Our link to abstention must be
  shown to differ from semantic entropy.

## Fix methods

- Counterfactual invariance (Veitch et al., arXiv 2106.00545, abstract only).
- Bias-augmented consistency training (Chua et al., arXiv 2403.05518, snippet). Reports
  an 86 percent drop in biased reasoning on held-out tasks. Did not improve positional
  bias.
- Activation and bias-augmented consistency training (Irpan et al., arXiv 2510.27062,
  opened). Small capability cost. One method cut benign answers from 98.1 to 73.1
  percent in a jailbreak test. Stubbornness and transfer to new perturbation types
  were not tested.
- Training on synthetic data reduces sycophancy (Wei et al., arXiv 2308.03958).
- Voting over paraphrases: TATRA (arXiv 2603.03298) and PPCV (alphaxiv 2602.11361),
  snippets only. No study found of rewriting the input to a normal form before
  answering.

## Why it matters in practice

- A Nature Medicine trial with 1,298 UK participants found chatbots gave inconsistent
  medical advice. Small wording changes shifted advice
  (nature.com/articles/s41591-025-04074-y). Snippet only. The page needs a login.
- EU AI Act Article 15 asks high-risk systems to perform consistently. Application
  dates differ between sources. Check them.
- tau-bench proposes pass^k, the chance that all k trials succeed (arXiv 2406.12045).
  Possible model for a worst-case flip metric.
- The agents found no documented court, hiring, or finance case caused by flipping
  answers. Do not claim one.
- The agents found no study of "answer shopping" (users re-ask until the answer fits).
  Small search. Treat as unconfirmed.

## Gaps the agents report

Medium confidence. The searches were not exhaustive.

1. No consistency benchmark for advice decisions with an "ask for more information"
   option.
2. No comparison of fix families on one benchmark with tests of transfer to unseen
   kinds of change.
3. No agreed definition of "warranted change" for advice.
4. Few stability studies use a resampling noise floor.
