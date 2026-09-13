# Corpus Plan — Inclusion Criteria and Sampling

**Status:** Proposed, not yet frozen
**Scope:** Curated AI/ML research corpus for sequence-level (synthetic-data) distillation

## 1. Purpose and scope

The corpus is intended to teach a small model to turn research papers into accurate, plain-language explanations. It is **not** intended to be a representative history of AI, a citation leaderboard, or a collection of only the most famous papers.

The target is frontier-model-relevant AI/ML research, with enough variety to teach the model how to explain different kinds of contributions:

- model architectures and pretraining
- data, scaling, and optimization
- instruction tuning, alignment, and reasoning
- retrieval, agents, and tool use
- multimodal/foundation-model methods
- efficient training, inference, quantization, and adaptation
- evaluation, safety, robustness, and interpretability

The initial training corpus may ultimately grow toward approximately 1,000 papers, but the first meaningful experiment should use approximately **300–600 usable papers** only after the 25-paper pilot has been inspected. Expand toward 1,000 only if quality, diversity, and budget remain acceptable.

## 2. Acquisition method

Use a deterministic local scraper/parser, not an AI model, to find papers and extract sections. The AI teacher is reserved for writing the plain-language explanation; using an AI model for discovery or extraction would add cost, variability, and silent errors.

The scraper will:

1. Query arXiv metadata.
2. Deduplicate canonical paper IDs and versions.
3. Apply explicit category, date, and topical candidate rules.
4. Temporarily download a source archive only when needed.
5. Extract and clean title, abstract, introduction, conclusion, and discussion fallback.
6. Save the processed record and quality flags.
7. Delete the temporary archive by default.

If a source archive cannot be parsed, flag the record or drop it. PDF extraction can be a later fallback, but it is not part of the first pilot.

## 3. Hard inclusion criteria

A paper is eligible for final selection only when **all** of these are true:

1. **AI/ML is central.** The paper concerns machine learning, language models, computer vision, multimodal models, reinforcement learning, agents, alignment, evaluation, or ML systems. AI must not merely be a tool used incidentally in another scientific field.
2. **The paper makes a substantive contribution.** It introduces or materially studies a model architecture, training method, dataset/data strategy, objective, scaling insight, reasoning method, evaluation method, safety method, or efficiency/system technique.
3. **It is within the time window.** The primary candidate window is 2017 through the experiment's recorded cutoff date. This is a Transformer-era corpus, not a general history of AI.
4. **It has enough explanatory substance.** The introduction and conclusion/discussion must provide enough context to explain the problem, approach, evidence, and limitations from the selected input sections.
5. **The source is usable.** A LaTeX source archive is available and can be parsed into non-empty, quality-checked sections. Missing conclusion may be allowed only when a usable discussion section is available as fallback.
6. **It is not a duplicate.** Conference/arXiv/technical-report versions and near-duplicate papers must be assigned to one canonical record and kept in the same eventual split.
7. **It is not withdrawn or corrupted.** Withdrawn records, empty sources, and records with unrecoverable extraction errors are excluded.

A paper does **not** need to come from a major lab, have high citations, or be published at a famous venue to qualify.

## 4. Relevance funnel

Start broad, then narrow through transparent stages.

### Stage A — eligible categories

Initial discovery categories:

- `cs.AI`
- `cs.LG`
- `cs.CL`

Optional discovery categories if the pilot misses important work or the candidate pool is too small:

- `stat.ML`
- `cs.CV`
- `cs.RO`
- `cs.NE`

Categories are discovery pools, not automatic inclusion labels. A paper from an optional category still has to satisfy the same AI/ML and frontier-relevance criteria.

### Stage B — topical candidate scoring

Use title and abstract keyword scoring to generate candidates, with manual review of the final candidates and a sample of rejected candidates. Positive topic groups should include terms related to:

- foundation and language models
- transformers and attention
- pretraining, data, and scaling
- instruction tuning and alignment
- reinforcement learning from feedback/preferences
- reasoning and test-time computation
- retrieval-augmented generation
- agents and tool use
- multimodal/foundation-model methods when directly relevant
- efficient training, inference, quantization, and adaptation
- evaluation, safety, robustness, interpretability, and red teaming of these systems

Keyword matching is a candidate generator, not a final truth label. Save the matched terms and topic bucket.

### Stage C — quality and usefulness filters

Prefer papers with:

- usable arXiv source
- meaningful abstract and introduction
- usable conclusion or discussion when available
- a clear method, system, benchmark, or empirical result
- enough information to explain the contribution from title + abstract + introduction + conclusion/discussion
- a problem → method → evidence structure that is useful for plain-language teaching

Drop or flag papers that are:

- withdrawn
- duplicates or alternate versions
- empty/corrupted source
- position papers with no concrete contribution, unless deliberately sampled as context
- too short or missing the core sections
- clearly outside the project's AI/ML explanation target
- mostly an incremental benchmark improvement with little transferable idea, unless it fills an important evaluation gap

## 5. Inclusion scoring rubric

Use this rubric for manual decisions after candidate generation:

| Criterion | Score |
|---|---:|
| AI/ML relevance | 0–2 |
| Technical novelty or importance | 0–3 |
| Frontier-model relevance | 0–2 |
| Educational/explanation value | 0–2 |
| Evidence and limitations are interpretable | 0–1 |
| Source quality and extractability | 0–1 |
| **Total** | **0–11** |

Interpretation:

- **9–11:** strong inclusion candidate
- **7–8:** include when it improves topical, time, institutional, or methodological diversity
- **5–6:** hold for later or include only to fill a documented coverage gap
- **0–4:** exclude

Popularity and affiliation are recorded separately and should not inflate the contribution score. A high citation count cannot rescue a paper that is irrelevant, duplicate, or unusable.

The decision record must include the score, inclusion/exclusion decision, and a short reason. For borderline papers, record the specific coverage gap they would fill.

## 6. Popularity, major labs, and diversity

Use popularity and affiliation as **soft ranking and balancing signals**, not hard requirements.

Why:

- citations favor older papers
- recent important papers have had less time to accumulate citations
- arXiv views/downloads are not stable universal relevance measures
- major-lab affiliation is difficult to identify reliably from arXiv metadata
- a hard major-lab filter would exclude valuable work from universities and smaller labs

Possible ranking features:

- citations, normalized by publication age
- influential citations when available
- recency
- topical relevance score
- author/institution signal when available
- source/extraction quality

The corpus should include a mixture of major industry labs, open research organizations, universities, and smaller/independent groups when the work is relevant and extractable. Record affiliations when available, but do not claim complete lab coverage.

Use institutional prestige as a **discovery signal**, not an inclusion rule. The final corpus should not be dominated by a few labs, first authors, or paper types.

## 7. First 25-paper pilot

The first 25 papers are a pipeline and curriculum pilot, not the final top-25 ranking. Every selected paper should be manually inspected, and every teacher-generated label should be audited before scaling.

Target composition:

| Area | Target |
|---|---:|
| Architectures and pretraining | 6 |
| Modern language-model training/data/scaling | 5 |
| Reasoning and post-training | 5 |
| Multimodal/foundation-model capabilities | 3 |
| Efficient training/inference/adaptation | 3 |
| Evaluation, safety, and limitations | 3 |
| **Total** | **25** |

These are targets, not rigid quotas. A paper may have multiple tags, but assign one primary bucket for balancing. If a category cannot be filled without weakening quality, leave it short and record the gap rather than relaxing the hard criteria silently.

The pilot should deliberately include:

- foundational and recent papers
- big-lab, university, open-lab, and smaller-group work
- successful methods and evaluation/limitation papers
- short and long inputs
- at least a few papers with discussion fallbacks or extraction edge cases, if they still pass quality review
- paired ideas where useful: an original method plus an evaluation/follow-up paper

Avoid selecting 25 model-release papers, 25 benchmark papers, or 25 papers from a handful of major companies. As a soft concentration limit, use no more than 2–3 papers from one lab and no more than 2 papers with the same first author in the pilot unless there is a documented reason.

The pilot must test whether the task is genuinely paper-to-plain-language explanation, rather than abstract paraphrase or memorization of one paper template.

## 8. Sampling for the larger corpus

After the pilot, sample approximately 300–600 papers using strata for:

- time band: 2017–2019, 2020–2022, and 2023–cutoff
- topic bucket
- popularity tier
- institution/lab type when available
- source and section-quality tier

A starting mixture is:

- **50% relevance-ranked papers**
- **30% time/topic-stratified papers**
- **20% discovery/novelty papers**, including newer or less-cited work

Treat these as initial sampling parameters, not permanent truths. Inspect candidate counts first and adjust only through a recorded configuration change. Keep the controlled lower-popularity share so the dataset is not merely a list of famous papers, while retaining relevance-ranked examples for strong signal.

The final held-out evaluation set must be selected and frozen by canonical paper ID before teacher labels are generated. Keep versions and near-duplicates in the same split.

## 9. What the pilot must measure before freezing criteria

Report counts after each funnel stage:

```text
metadata candidates
category-filtered
keyword-relevant
manual-score reviewed
quality-valid
source-available
final sampled
```

Also report counts by year, category, primary topic, popularity tier, institution/lab type, extraction status, and exclusion reason. If the pool is too large, tighten topic or quality thresholds. If it is too small, broaden optional categories or reduce keyword strictness before extending the date range.

For each included pilot paper, measure:

- input characters and student-token count
- section lengths and fallback use
- source archive size and processed-record size
- parser warnings
- later teacher input/output tokens, latency, retries, and estimated cost

## 10. Reproducibility and manifest

Save the following for every candidate, including rejected records:

- canonical arXiv ID and exact version read
- title, authors, categories, dates, and available affiliations
- discovery query/configuration and matched terms
- primary topic bucket and scoring features
- inclusion/exclusion decision, score, and reason
- duplicate/near-duplicate group
- source availability and extraction status
- section names, fallback flags, warnings, and character/token counts
- popularity fields and retrieval date when used
- random seed and sampling strategy
- corpus cutoff date and selection-rule version
- train/evaluation split assignment

Keep dropped papers in the manifest with `included: false`. This distinguishes selection bias from parser failure and makes the funnel auditable.

The evaluation split must be frozen before teacher labels are generated. Teacher prompts, model ID, generation settings, validation failures, and costs belong in the downstream labeling records, not only in informal notes.
