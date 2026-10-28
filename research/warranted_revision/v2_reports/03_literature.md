# 03 — Literature review for the Warranted Revision benchmark v2

Branch `research/warranted-revision-v1`, commit `1e5d8b8`, 2026-10-25. Builds on
`agent_reports/01_novelty.md` and `SYNTHESIS.md`; 01's verdicts are not repeated.
No other v2 report was read. No runs.

**Access.** WebFetch fails DNS for every host. curl through the proxy gets a 403 for arXiv,
the ACL Anthology, Semantic Scholar and Hugging Face. `raw.githubusercontent.com` and shallow
`git clone` work. Each citation carries one of three verification tags:
- **[repo]**: I read the authors' own GitHub README or paper source.
- **[snippet]**: search-result abstract or metadata only. Venue and numbers are as the snippet
  gave them and should be checked before citing.
- **[unverified]**: name seen, content not checked. Do not cite.

## Top 3 findings

1. **No one has published the full v2 design, but every part of it exists somewhere.**
   - **(4) Supported vs unsupported correction:**
     - Big-Big-SycoBench has 5,400 human-reviewed valid/invalid arguments [snippet].
     - Ma et al. 2026 has evidence vs bare pressure [repo].
     - AssertBench has bare "I know F is true/false" assertions [repo].
   - **(3) Validation-seeking:** ELEPHANT [repo]; Val-Obj, 48 human-written pairs [snippet].
   - **(1)/(2) Legitimate change vs drift:**
     - BeliefShift claims 2,400 human-annotated trajectories, with "legitimate belief updates
       vs drift" as its central contrast [snippet]. It is the closest overlap with the
       goal-change class and must be read in full before v2 claims that class is new.
     - PersonaMem tests preference-shift tracking [snippet].

   What I did not find: one item set, where a stated decision rule fixes the answer, that puts
   goal change, preference, reassurance and (un)supported fact against each other with
   lexically matched wording and human labels. About 30 searches. This is absence of evidence,
   and 2026 arXiv output in this area is heavy (≥10 new sycophancy benchmarks since June).
2. **The closest published benchmarks do not control lexical cues. That is v2's real opening
   and also its main burden.**
   - Ma et al. separate their conditions by template (Ma et al. repo README):
     - pressure is `I think the answer is "y_w". Are you sure?`;
     - evidence is `Here is a reference note: e`.
   - SycoBench-600's "correct suggestion" uses the same wording as its wrong suggestion
     (`sycobench_camera_ready.tex` l.130). Its "Update" therefore rewards giving in to an
     *unsupported* assertion that happens to be true. That is exactly v2's class (4)
     distinction, collapsed.
   - The NLI literature shows what follows: a template-only classifier would solve these sets,
     as v1's 280/320 and 200/200 already showed for this repo (SYNTHESIS §C).

   v2 is a contribution only if it reports partial-input baselines and contrast sets (§2). It
   is not one merely for adding classes.
3. **No paper isolates the effect of attaching an options list plus a decision-format
   instruction to the user's follow-up on deference. The adjacent evidence points both ways,
   so the diagnostic is open but has no prior to lean on.**
   - **Formats move scores a lot:** up to 76 accuracy points from formatting alone in Sclar et
     al. [repo+snippet]; option-ID selection bias in Zheng et al. [snippet].
   - **Evaluative or side-by-side framing lowers acceptance of a rebuttal** compared with
     follow-up-turn framing (Kim & Khashabi) [snippet].
   - **Clear multiple-choice items were easier to flip** than ambiguous diagnostic cases
     (Kim et al. 2026, medical) [snippet]. This is confounded with item clarity, not a format
     manipulation.
   - **Preemptive rebuttals give more sycophancy than in-context ones** (SycEval) [snippet].

   Nothing shows that forced-choice scaffolding *suppresses* deference. v1's 0/36 pressure
   moves cannot be attributed to the scaffold from the literature. It needs the planned probe.

## 1. Closest benchmarks and datasets

Column key: **Goal≠pressure** = does it separate a goal change from pressure? **Lexical
control** = does it control lexical cues? **Labels** = how labels were obtained.

| Work (verification) | What it tests | Goal≠pressure? | Lexical control? | Labels |
|---|---|---|---|---|
| **SycoBench-600**, Sinha, Findings ACL 2026 [repo: tex] | MCQ; doubt/authority/wrong-suggestion vs matched correct suggestion; Sel = Update − WrongFlip | No | Partial: 3 fixed paraphrases per perturbation. The correct and wrong suggestions are matched in wording, but the correct one carries no evidence, so supported and unsupported are conflated | Manually authored items, not LLM-generated (tex l.89) |
| **Ma et al.**, Findings EMNLP 2026, arXiv 2608.26511 [repo] | R_UY (pressure) vs R_RU (reference note, or the same note attributed to the user); TruthfulQA, PopQA, EX-FEVER, AQuA | No | No: conditions are distinct templates. `user_evidence` (`I think e`) controls source attribution only | Gold from upstream QA; evidence notes "quote-backed" |
| **Big-Big-SycoBench**, Ballon et al. (14 authors), arXiv 2610.15634, Oct 2026 [snippet; HF dataset `martheballon/Big-Big-SycoBench` not reachable] | 450 texts in 10 genres; 5,400 valid vs invalid arguments to revise a quality score; a revision counts only beyond the model's own 20-sample baseline variance | No (evaluative judgments, not user goals) | Unknown | "Human-reviewed"; 12 annotators per snippet. **Closest to class (4)** and to v2's human-label claim |
| **AssertBench**, Lee & Chowdhary, arXiv 2506.11110; NeurIPS 2025 listing, track unknown [repo + snippet] | Single-turn "I know F is correct/incorrect", FEVEROUS SUPPORTS facts; stratified by whether the model knows F | No | Yes for framing (minimal pair differing in one word) | FEVEROUS gold |
| **Belief-R**, Wilie et al., EMNLP 2024 [repo] | Belief update vs maintain after a new premise; trade-off between the two | No (no social pressure, no goals) | Not stated | See paper |
| **BeliefShift**, Myakala, Agrawal, Manche, arXiv 2603.23848, Mar 2026 [snippet] | Multi-session; tracks: temporal belief consistency, contradiction detection, evidence-driven revision; "personalizing models resist drift poorly, grounded models miss legitimate updates" | **Partly**: legitimate change vs drift, over health, politics, values, product preferences | Unknown | Claims 2,400 human-annotated trajectories. **Read in full before claiming goal-change novelty** |
| **PersonaMem**, "Know Me, Respond to Me", arXiv 2504.14225 [snippet] | Tracks preference evolution and responds to the latest preference | Preference change only, no pressure contrast | Unknown | Unknown (likely synthetic) |
| **PrefEval**, Zhao et al., ICLR 2025 per snippet [repo] | Following a stated preference over long contexts; reminder prompts rescue performance | No; preferences are static | No | Generated preference/question pairs |
| **ELEPHANT**, Cheng et al., arXiv 2505.13995 [repo; venue unverified] | Social sycophancy: validation, indirectness, framing; OEQ (3,027), AITA, Subjective Statements (3,777) | No | No | Crowdsourced or Reddit verdicts; LLM-judge metrics; snippet: 2 annotators validated 150 items |
| **Val-Obj**, "Verbalizing LLMs' assumptions…", arXiv 2604.03058 [snippet] | 48 pairs phrased to seek validation vs objective information | No | Paired | Human-written |
| **SYCON-Bench**, Hong et al., Findings EMNLP 2025 [repo + snippet] | Multi-turn pushback (Turn of Flip, Number of Flips); debate, unethical, false-presupposition | No | No | Topic sets |
| **FARM**, Xu et al., "The Earth is Flat because…", ACL 2024 [snippet] | Multi-turn persuasion into misinformation | No (all persuasion is toward a falsehood) | No | Generated persuasive text |
| **Kim & Khashabi**, Findings EMNLP 2025 [snippet] | Rebuttal style (casual vs formal, detailed reasoning) and follow-up vs side-by-side | No | Templates | MCQ gold |
| **PPT-Bench**, arXiv 2604.07749 [snippet, authors not found]; **SPINE**, arXiv 2609.09090 [snippet]; **MedPRESS**, arXiv 2608.02520 [snippet] | Epistemic-attack, adaptive 25-turn and medical pressure | No | No | Mixed |
| "Resist, Update, Reject", Yang & Yeung, arXiv 2609.22359 [snippet] | Flip iff stated source reliability r > prior p; DPO learns the threshold | No | Constructed notation | Synthetic |
| "Anatomy of LLM Sycophancy: What a Flip Rate Hides", arXiv 2610.06522 [**unverified**: one snippet, not found on re-search]; "Beyond the Sycophancy Score", arXiv 2610.08840 [**unverified**] | Said to treat answer format and pushback wording as factors | — | — | Do not cite until checked |

**Does anything already do v2?**
- **Not fully.** All the overlap is partial:
  - class (4) is done with human labels (Big-Big-SycoBench, evaluative domain);
  - legitimate change vs drift is claimed (BeliefShift);
  - validation-seeking is done (ELEPHANT, Val-Obj).
- **Uncovered, as far as I found:**
  - the *decision-rule-grounded* setting, where the goal change determines the answer;
  - goal-change vs pressure contrast pairs with matched wording;
  - an explicit *ambiguous* label alongside the five classes.
- **Both claims rest on snippets,** BeliefShift's especially.

## 2. Methodology v2 should adopt

| Precedent (verification) | Lesson | Concrete practice for v2 |
|---|---|---|
| Gururangan et al., NAACL 2018 [snippet]: hypothesis-only classifier gets ~67% on SNLI and ~53% on MultiNLI | Crowd-writing protocols leave label cues | Report a **follow-up-only baseline** (no context, no prior advice) and a **bag-of-words / first-k-tokens baseline** for each class. Publish the data only if these sit near chance. v1 failed this (280/320) |
| Poliak et al., *SEM 2018 [repo] | Partial-input baselines across 10 datasets | Also a **context-free LLM baseline**: an LLM sees only the follow-up and guesses the class. If that is high, the label is in the wording, not in the interaction |
| Gardner et al., Findings EMNLP 2020, contrast sets [snippet + repo] | Small expert edits that flip gold expose shortcuts; scores drop up to 25% | Build each item as a **contrast set**: the same follow-up wording paired with (a) a context where the new goal changes the answer, (b) one where it doesn't, (c) a supported vs unsupported version of the same fact. Score **contrast consistency** (all members right), not just accuracy |
| Kaushik et al., ICLR 2020, counterfactually augmented data [repo] | Humans edit minimally to a target label and avoid gratuitous changes | Annotator-authored **minimal counterfactuals across classes**, e.g. preference ↔ goal change by editing one clause. Log edit distance, and show classes don't differ in length or specific tokens |
| Le Bras et al., ICML 2020, AFLite [snippet]: SNLI accuracy 92% → 62% after filtering, human accuracy kept | Filter items that weak models solve from surface features | After writing, run an **AFLite-style filter** with a cheap feature classifier, drop or rewrite easily predictable items, and release both the filtered and unfiltered sets. Caveat: filtering against one model family biases the set toward that family's weaknesses. Say so |
| Pavlick & Kwiatkowski, TACL 2019 [snippet]; Nie et al., ChaosNLI, EMNLP 2020 [repo] (100 labels per item on 4,645 items) | Disagreement persists with more raters; it is signal, not noise | Keep **both annotators' raw labels**. On a subset (≥100 items), collect 5–10 extra labels to estimate the human label distribution. Evaluate the "ambiguous" class against that distribution, not as a sixth gold class |
| Liu et al., AmbiEnt, EMNLP 2023 [repo] | Overgenerate, then have linguists annotate; ambiguity is labelled with its disambiguations | For every item labelled ambiguous, require annotators to **write the two readings and the answer under each**. That makes "ambiguous" testable: does the model ask, or state both? |
| Plank, EMNLP 2022 [snippet]; Cabitza et al., AAAI 2023, perspectivism [snippet] | Do not collapse variation into a single gold | Release disaggregated labels and annotator IDs; report results under adjudicated gold *and* soft labels |
| Artstein & Poesio, CL 2008 [snippet] | Choosing an agreement coefficient | Report **Krippendorff's α per class** and the confusion matrix between annotators, and pre-register an α threshold (e.g. ≥0.67) below which a class is merged or dropped. Adjudication must not erase disagreement: keep the pre-adjudication labels |
| Bender & Friedman 2018 / Gebru et al. (cited in SycoBench-600 tex) [repo citation only] | Documentation | Data statement: who wrote the items, annotator background, guideline versions, and blinding procedure |

**Guidelines and adjudication (synthesis, not a single source):**
- Pilot the guideline on about 50 items.
- Revise it, then freeze it.
- Annotate blind to the model's output and to the generator's intended class.
- Adjudicate by discussion with a third person.
- Record the reason for each adjudication.
- Report agreement before adjudication.

## 3. Prompt format and multi-turn literature for the scaffold diagnostic

- **Sclar et al.,** ICLR 2024 [repo + snippet].
  - Finding: up to 76 points of spread from format alone (LLaMA-2-13B); the spread persists
    with scale and instruction tuning.
  - Practice: report the scaffold effect across **several format variants**, not one.
- **Mizrahi et al.,** TACL 2024 [snippet].
  - Finding: model rankings change with instruction paraphrase.
  - Practice: use multi-prompt metrics. One scaffold vs one non-scaffold is a single draw.
- **Zheng et al.,** ICLR 2024 [snippet].
  - Finding: MCQ selection bias comes from option-ID token priors. Removing IDs reduces it for
    most models.
  - Practice: the options list adds an ID prior that can masquerade as stability or as
    switching. **Permute option order** (already in SYNTHESIS E1) and add an ID-free variant.
- **Kim & Khashabi,** Findings EMNLP 2025 [snippet].
  - Finding: follow-up-turn rebuttals are accepted more than side-by-side evaluation. Casual,
    unjustified rebuttals and detailed but wrong reasoning are persuasive.
  - Relevance: the nearest evidence that *framing the decision as an evaluation* reduces
    deference. v2's DECISION-format scaffold may act the same way.
- **Kim et al.,** "The Doctor Will Agree With You Now", HeaLing workshop 2026 [snippet].
  - Finding: clear multiple-choice items flip more readily than ambiguous diagnostic cases.
  - Caveat: confounded, see Top finding 3. It does not show options amplify deference.
- **SycEval,** Fanous et al., AIES 2025 [snippet].
  - Finding: preemptive rebuttals are more sycophantic than in-context ones.
  - Relevance: position and turn structure matter.
- **FlipFlop,** Laban et al., arXiv 2311.08596 [snippet].
  - Finding: "Are you sure?" causes flips 46% of the time on average and a 17% accuracy drop.
- **Laban & Hayashi,** "LLMs Get Lost in Multi-Turn Conversation", ICLR 2026 per snippet
  [snippet].
  - Finding: a 39% average drop when instructions are sharded across turns, driven mostly by
    unreliability.
  - Relevance: extra turns are not neutral filler. They add variance, so the "extra
    conversational turns" arm needs a no-pressure multi-turn control.
- **SYCON-Bench** [repo + snippet].
  - Finding: a third-person persona prompt ("Andrew") raises Turn of Flip by up to 63.8% in
    debate.
  - Relevance: prompt scaffolds *can* strongly suppress multi-turn capitulation. That is the
    closest positive precedent for "scaffold suppresses deference", though the scaffold type
    differs.
- **Röttger et al.,** "Political Compass or Spinning Arrow?", ACL 2024 [**unverified**: search
  did not surface it].
  - Recalled finding: forced-choice and open answers diverge.
  - Do not cite until checked.

**Answer to "has anyone shown forced-choice scaffolding suppresses or amplifies deference?"**
Not directly, as far as I found. Two things are shown:
- Persona or instruction scaffolds suppress capitulation (SYCON-Bench).
- Evaluative or simultaneous framing reduces rebuttal acceptance (Kim & Khashabi, snippet).

The specific "options + DECISION line attached to the pressure message" manipulation is
untested. The diagnostic would be a small new data point, not a paper on its own.

## 4. Novelty verdict

- **New (if it holds after reading BeliefShift and Big-Big-SycoBench in full):**
  - A rule-grounded advice setting in which a *goal change* is the warranted class.
  - Its contrast with preference, reassurance and pressure, in **lexically matched minimal
    pairs**.
  - Supported vs unsupported factual claims that carry the same correction wording.
  - A modeled ambiguous class with written readings.
  - Partial-input baselines showing the classes can't be told apart from surface features.
- **Already done:**
  - Two-sided selectivity metrics (SycoBench-600, Ma et al.).
  - Valid vs invalid arguments with human review (Big-Big-SycoBench).
  - Validation-seeking sycophancy (ELEPHANT).
  - Legitimate change vs drift as a framing (BeliefShift, claimed).
  - The result that mitigations trade the two sides (Ma et al.).
  - Prompt scaffolds that reduce capitulation (SYCON-Bench).
- **Main ACL/EMNLP (dataset track) would need all of the following:**
  - ≥500 items over ≥20 domain families, written as contrast sets.
  - Follow-up-only, bag-of-words and context-free-LLM baselines near chance, with an AFLite-style
    filter reported.
  - Two blinded annotators with α per class, pre-adjudication labels released, and a
    multi-annotator subset for the ambiguous class.
  - ≥5 models across ≥2 families, with family-level inference.
  - A finding existing benchmarks miss. Example: models that score high on SycoBench-600 or
    Ma et al. still fail goal-change items, or treat goal changes as pressure. Show it by
    running those external suites on the same models.
  - Multi-prompt reporting (Sclar, Mizrahi).
- **Workshop scale** is any of:
  - templated items;
  - labels from the generator;
  - one or two models;
  - no partial-input baselines;
  - the scaffold diagnostic as the headline result.

On current evidence, a workshop paper is likely unless the lexical-control and human-label
work is done properly. The class taxonomy alone is not enough.

## Why I might be wrong

- Most 2026 items are snippets. BeliefShift or Big-Big-SycoBench could fully cover classes (1)
  and (4), or could be much weaker than their abstracts suggest.
- Search engines index 2026 arXiv unevenly, so a direct competitor could exist.
- A snippet attributed "evaluative framing reduces sycophancy" to Kim & Khashabi second-hand.
  It is not checked against the paper.

## Sources (search results used)

- Big-Big-SycoBench: https://arxiv.org/abs/2610.15634
- BeliefShift: https://arxiv.org/abs/2603.23848
- AssertBench: https://arxiv.org/abs/2506.11110 ; github.com/achowd32/assert-bench
- Kim & Khashabi: https://aclanthology.org/2025.findings-emnlp.1222.pdf
- Kim et al. 2026 HeaLing: https://aclanthology.org/2026.healing-1.2
- PersonaMem: https://arxiv.org/html/2504.14225v2
- Val-Obj: https://arxiv.org/html/2604.03058v3
- SycEval: https://arxiv.org/html/2502.08177v4
- FlipFlop: https://arxiv.org/abs/2311.08596
- Laban & Hayashi: https://arxiv.org/abs/2505.06120
- Sclar et al.: https://iclr.cc/virtual/2024/poster/18650
- Zheng et al.: https://iclr.cc/virtual/2024/poster/17638
- Mizrahi et al.: https://aclanthology.org/2024.tacl-1.52
- Gururangan et al.: https://aclanthology.org/N18-2017/
- Gardner et al.: https://preview.aclanthology.org/dashboard/2020.findings-emnlp.117
- AFLite: https://mlanthology.org/icml/2020/bras2020icml-adversarial
- Pavlick & Kwiatkowski: https://transacl.org/index.php/tacl/article/view/1780
- Plank: https://www.aclweb.org/anthology/2022.emnlp-main.731.pdf
- Cabitza et al.: https://doi.org/10.1609/aaai.v37i6.25840
- Artstein & Poesio: https://aclanthology.org/J08-4004/
- FARM: https://aclanthology.org/2024.acl-long.858
- SYCON-Bench: https://preview.aclanthology.org/dashboard/2025.findings-emnlp.121
- PPT-Bench: https://arxiv.org/abs/2604.07749
- SPINE: https://arxiv.org/abs/2609.09090
- MedPRESS: https://arxiv.org/html/2608.02520
- Resist/Update/Reject: https://arxiv.org/pdf/2609.22359
- Repos read: debu-sinha/sycobench-600, dependentsign/sycophancy-rational-updating,
  alisawuffles/ambient, easonnie/ChaosNLI, allenai/contrast-sets,
  acmi-lab/counterfactually-augmented-data, msclar/formatspread, azpoliak/hypothesis-only-NLI,
  meg-tong/sycophancy-eval, amazon-science/PrefEval, JiseungHong/SYCON-Bench,
  myracheng/elephant, HLTCHKUST/belief-revision, achowd32/assert-bench
