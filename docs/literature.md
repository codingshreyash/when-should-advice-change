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
(`research/negative_methods/NEGATIVE_METHODS_REPORT.md`). We found no link; find and read it.

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

## Update 2026-11-15: related work for the "second look" and decomposition results

Collected by three research agents. **Read depth is stated per item; most are abstracts or
snippets.** Spot-check numbers before citing; the fetch tool summarises pages and can compress them.

**Read methods and results (most of the page):**
- *Anatomy of LLM Sycophancy: What a Flip Rate Hides* (Huang, arXiv 2610.06522). Stateless replay with a
  matched no-pressure control subtracted, about 760k replays, 11 frontier models, moral vignettes plus
  arithmetic with known truth. Effects are several times larger near the model's own decision boundary.
  **Closest competitor to our boundary result and to part of the second-look design.**
- Big-Big-SycoBench (arXiv 2610.15634): 20 resamples per item set a noise floor; valid vs invalid
  arguments; 10 models. Labels are LLM-made and human-checked; not advice.
- BeliefTrack, "When Should Models Change Their Minds?" (EMNLP 2026, arXiv 2605.30219): oracle belief
  states by construction in closed-world tasks; Qwen2.5-7B and Qwen3.5-9B; not advice.
- SWAY (Bhalla and Gligoric, arXiv 2604.02423): counterfactual log-ratio of positive vs negative nudges;
  AITA, LFQA, DebateQA; temperature 0, no resample control, no ground truth.
- Shapira et al., sycophancy as in-context updating (arXiv 2610.28325): MMLU-Pro with a wrong endorsed
  option; models also defer to non-user sources.

**Abstract only:** Resist and Update (arXiv 2607.12985; Bayesian witnesses with known posteriors),
SycoBench-600, BeliefShift (arXiv 2603.23848), BASIL (arXiv 2508.16846), Beacon (arXiv 2510.16727).
**Snippet only:** FRAGILE (Hwang et al., ICML 2026; framing changes on moral, medical, legal decisions;
not a sycophancy paper; the midterm cited it, so check the wording), Huang et al. 2023 (self-correction,
arXiv 2310.01798), FlipFlop (arXiv 2311.08596: "Are you sure?" about -17% accuracy on average),
Firm or Fickle (arXiv 2503.22353), Kamoi et al. survey (arXiv 2406.01297), Sharma et al. (arXiv 2310.13548).
Abstract only: He et al., multi-turn answer instability (arXiv 2511.10688); Li, accuracy-correction
paradox (arXiv 2601.00828). User and real-world data: WildChat-1M (opened; ODC-By), a 2026 taxonomy
(arXiv 2605.21778, opened) reporting Claude's sycophancy at 18% under pushback vs 9% without.

**Already known, so do not claim as new:** follow-ups and "Are you sure?" can lower accuracy;
intrinsic self-correction does not reliably help; pressure induces sycophancy; flips concentrate near the
model's decision boundary (Anatomy); separating warranted from unwarranted updates with a noise control
(Big-Big-SycoBench, BeliefTrack, SycoBench-600, BASIL); truth by construction (BeliefTrack, Resist and
Update).

**Claims that still stand (no read paper supports them):**
1. In advice decisions with truth by construction and a controlled margin, flips concentrate near the
   boundary, and part of the apparent pressure effect is option-order noise and priming by naming the
   option. Frame it as advice-specific and as a decomposition, citing Anatomy.
2. A **neutral** plain re-ask, against a resample control, does not reliably improve answers and sharply
   hurts some mid-size models (Gemma 2 9B). Modest novelty: prior work mostly used challenge wording.
3. Close calls scored as "either option acceptable" change how flip rates read.

**Open next experiments suggested by the agents:** a wording sweep of the re-ask ("Are you sure?",
"double check", "review your answer", "take another look", a neutral restate); a size sweep inside one
model family; and **seeding turn 1 with a wrong answer** to measure recovery against loss, which removes
the ceiling problem.

## Update 2026-11-19: mechanism leads for the second-look results

Found by a search agent. **Read depth for every item: abstract only or search snippet only. No full text was read.** Treat each as a lead to check before citing. A teammate should read the first four in full.

**No paper tests our exact findings.** We found no mechanistic study of "look again" on a model's own answer versus a planted one. Nothing covers the revise-on-challenge reflex of Gemma 2 9B specifically. The work below gives hypotheses, not an explanation.

| Our finding | Lead | Read depth | What it offers |
|---|---|---|---|
| Naming an option moves the answer | Wang et al. 2025, "When Truth Is Overridden: Uncovering the Internal Origins of Sycophancy in Large Language Models", arXiv 2508.02087 | abstract only | A user's stated opinion shifts the output in late layers (logit lens, activation patching). Closest match. |
| Naming an option moves the answer | Panickssery et al., "Steering Llama 2 via Contrastive Activation Addition", arXiv 2312.06681 | snippet only | A steering vector raises or lowers sycophancy. A causal direction exists. |
| Models change right answers when challenged | Genadi et al. 2026, "Sycophancy Hides Linearly in the Attention Heads", arXiv 2601.16644 | abstract only | A few middle-layer heads attend to expressions of user doubt. A challenge turn is user doubt. |
| Models change right answers when challenged | Pandey 2026, "LLMs Know They're Wrong and Agree Anyway: The Shared Sycophancy-Lying Circuit", arXiv 2604.19117 | abstract only | Heads detect a wrong claim. Silencing them changes sycophancy. Effect sizes not checked. |
| Own mistakes are hard to fix | Yang and Jia 2025, "When Do LLMs Admit Their Mistakes? Understanding The Role Of Model Belief In Retraction", arXiv 2505.16170 | abstract only | A probe-measured belief predicts whether a model retracts its own answer. |
| Revision after a challenge | Chen et al. 2025, "Persona Vectors", arXiv 2507.21509 | abstract only | Sycophancy is a linear direction that can be monitored and steered. |
| Revision after a challenge | Sharma et al. 2023, "Towards Understanding Sycophancy in Language Models", arXiv 2310.13548 | snippet only | Human preference data sometimes favors agreeable answers. A training-data explanation. |
| Self-correction hurts | Huang et al. 2023, "Large Language Models Cannot Self-Correct Reasoning Yet", arXiv 2310.01798 | snippet only | Without oracle labels, self-correction can turn right answers wrong. |
| Challenge flips answers | Laban et al. 2023, "Are You Sure? Challenging LLMs Leads to Performance Drops in The FlipFlop Experiment", arXiv 2311.08596 | snippet only | About 46% of answers flip under challenge. The two versions give different numbers. Check which one to cite. |
| Self-correction wavering | Zhang et al., "Understanding the Dark Side of LLMs' Intrinsic Self-Correction", arXiv 2412.14959 | abstract only | Self-correction makes models waver on correct answers. |
| Self-correction as steering | Lee et al. 2025, "Explaining Intrinsic Moral Self-Correction with Mechanistic Interpretability", arXiv 2505.11924 | abstract only | Self-correction prompts shift hidden states. Moral tasks only. |

**Two untitled leads (could not get title or authors; do not cite):** arXiv 2603.04582 (a self-attribution bias: models rate their own actions as better) and arXiv 2604.22193 (models prefer self-attributed assertions). Both would support a hypothesis for our planted-versus-own gap: a model may treat its own earlier answer as more credible. We have not tested this. "Prefill Awareness in Large Language Models" (arXiv 2606.12747, snippet only) is related.

**How to write it in the paper:** "Prior work suggests X, and our results are consistent with it." Do not write "mechanistic interpretability shows X."

**Correction to claim 2 above.** The neutral wording turned out to be the safe one. The harm comes from "look again" and "review for mistakes", not from the neutral re-ask. See `docs/real_world_check.md` (Arm A results).
