# Paper Simplifier — Core Project Specification

**Status:** Planning / pre-implementation  
**Current phase:** Architecture and design decisions  
**Next implementation target:** Small end-to-end data-ingestion pilot

## 1. Goal

Build and evaluate a small Qwen-based language model that turns selected AI/ML research papers into clear, plain-language explanations.

The first version is intentionally narrow:

- Research area: AI, machine learning, and language/frontier-model methods
- Source: arXiv papers
- Input: title, abstract, introduction, and conclusion/discussion when available
- Output: teacher-generated plain-language explanations
- Training: teacher-generated synthetic instruction tuning using QLoRA
- Hardware: RTX 5070 with 12 GB VRAM and 32 GB system RAM
- Preferred total API spend: under $10, with a hard budget guard before large-scale generation

This project is both a learning exercise and a usable prototype. Every phase should produce an inspectable artifact or test result.

## 2. Terminology: what kind of distillation this is

The initial system will not perform logit-level knowledge distillation. The teacher will generate text explanations, and the student will learn from those examples.

Use this name in code and documentation:

> **Teacher-generated synthetic instruction tuning (sequence-level distillation) with QLoRA.**

This is still a valid distillation-style approach, but the distinction matters: teacher errors and stylistic choices can appear in the training labels, so labels must be audited.

## 3. System architecture

```text
                         ┌─────────────────────────┐
                         │  Corpus selection rules │
                         │  + arXiv metadata API   │
                         └────────────┬────────────┘
                                      │ paper manifest
                                      v
                         ┌─────────────────────────┐
                         │ Source acquisition      │
                         │ Prefer direct extraction│
                         │ Cache only as configured │
                         └────────────┬────────────┘
                                      │
                                      v
                         ┌─────────────────────────┐
                         │ LaTeX/text extraction   │
                         │ title + abstract + intro│
                         │ + conclusion fallback   │
                         └────────────┬────────────┘
                                      │ cleaned examples
                                      v
                         ┌─────────────────────────┐
                         │ Tokenizer statistics    │
                         │ length limits + flags   │
                         └────────────┬────────────┘
                                      │ validated pilot set
                                      v
                         ┌─────────────────────────┐
                         │ Teacher generation      │
                         │ Qwen Flash via Hermes   │
                         │ cost + retry logging    │
                         └────────────┬────────────┘
                                      │ synthetic labels
                                      v
                         ┌─────────────────────────┐
                         │ Label validation/audit   │
                         │ schema + automatic      │
                         │ checks + human sample   │
                         └────────────┬────────────┘
                                      │ frozen dataset/splits
                                      v
       ┌──────────────────────────────┴──────────────────────────────┐
       │                                                             │
       v                                                             v
┌─────────────────┐                                      ┌──────────────────────┐
│ Student baseline│                                      │ QLoRA fine-tuning     │
│ Candidate Qwen  │                                      │ 4-bit + LoRA + SFT    │
└────────┬────────┘                                      └──────────┬───────────┘
         │                                                         │
         └──────────────────────────┬──────────────────────────────┘
                                    v
                         ┌─────────────────────────┐
                         │ Controlled evaluation   │
                         │ factuality, coverage,   │
                         │ clarity, readability,   │
                         │ teacher similarity     │
                         └─────────────────────────┘
```

## 4. Data-flow artifacts

The pipeline should preserve small, useful artifacts rather than storing every possible intermediate file.

```text
data/
├── manifests/
│   ├── candidate_papers.jsonl       # API results and selection metadata
│   ├── corpus_manifest.jsonl        # included/dropped papers and reasons
│   └── splits.json                  # frozen train/validation/test IDs
├── processed/
│   ├── pilot.jsonl                  # cleaned text + extraction metadata
│   ├── teacher_labels.jsonl         # teacher output + usage/cost metadata
│   └── instruction_dataset.jsonl    # final chat-formatted training records
└── cache/                            # optional, size-limited working cache
```

Raw source archives are **not required as a permanent dataset dependency**. The default design is:

1. Request a source archive temporarily.
2. Extract the relevant text.
3. Save the cleaned sections and metadata.
4. Delete the archive unless a debug/cache option is enabled.

A source archive may still be retained for papers that fail extraction or for a small debugging sample.

## 5. Proposed repository structure

```text
paper-simplifier/
├── IDEA.md                          # lightweight design history / decisions
├── PROJECT_SPEC.md                  # current architecture and constraints
├── CORPUS_PLAN.md                   # proposed paper-selection strategy
├── MODEL_OPTIONS.md                 # provisional teacher/student shortlist
├── HOW_IT_WORKS.md                  # learner-facing explanation
├── PROGRESS.md                      # checklist and experiment log
├── README.md                        # setup and quick start (later)
├── pyproject.toml                   # pinned/project dependencies (later)
├── configs/
│   ├── corpus.yaml                  # selection and extraction settings
│   ├── teacher.yaml                 # model, prompt version, budget guard
│   ├── training.yaml                # QLoRA settings
│   └── evaluation.yaml              # metrics and decoding settings
├── data/
│   ├── manifests/
│   ├── processed/
│   └── cache/                       # gitignored, size-limited
├── src/
│   └── paper_simplifier/
│       ├── __init__.py
│       ├── schemas.py               # record formats and validation
│       ├── arxiv_client.py          # metadata/source requests + rate limiting
│       ├── latex_extract.py         # source parsing and section fallbacks
│       ├── token_stats.py           # tokenizer-based measurements
│       ├── teacher_generate.py      # API calls, retries, cost accounting
│       ├── dataset_format.py        # model chat template conversion
│       ├── train_qlora.py            # training entry point
│       └── evaluate.py              # automated metrics and reports
├── tests/
│   ├── test_latex_extract.py
│   ├── test_token_stats.py
│   ├── test_schemas.py
│   └── test_budgeting.py
└── reports/
    ├── pilot/                       # inspected pilot outputs
    └── evaluation/                  # result tables and notes
```

The initial scraper implementation can be smaller than this final structure. Do not create empty modules only for appearance; create a file when its phase starts.

## 6. Corpus-selection policy

The current corpus proposal is documented in `CORPUS_PLAN.md`. The scraper is deterministic and local: an AI model is not used to locate sections or extract text. AI generation begins only after the processed paper input has been created, because extraction is cheaper, reproducible, and easier to validate with code.

The proposed time window is 2017 through a recorded experiment cutoff date. Candidate papers are filtered through categories, title/abstract relevance, source quality, and stratified sampling. Popularity and major-lab signals are soft ranking features rather than hard requirements, because citation counts favor older papers and lab affiliation is incomplete in arXiv metadata.

Start with a 10–25-paper pilot, then target roughly 300–600 usable papers for the first full experiment. Expand toward 1,000 only if the measured diversity and data quality justify it.

## 7. Source-storage policy

The preferred storage mode is **extract-and-discard**:

- Do not permanently save all source archives by default.
- Store cleaned selected sections, metadata, extraction warnings, and token counts.
- Store a configurable number of source archives for debugging, initially 10–25 pilot papers.
- Enforce a cache size limit and make the cache disposable.
- Never make later stages depend on re-downloading a source unless the project explicitly accepts that reproducibility trade-off.

The exact storage estimate depends on source archive sizes and whether compressed archives are kept. The project should measure actual sizes during the pilot and report:

```text
archive_bytes_downloaded
archive_bytes_retained
processed_bytes
cache_bytes_current
```

## 7. Section extraction policy

For each paper, attempt to produce:

- Title
- Abstract
- Introduction or closest introduction-like section
- Conclusion, if found
- Final discussion, if found and needed as a conclusion fallback

Preferred conclusion policy:

1. Use an explicit conclusion/conclusions section.
2. Otherwise use a final discussion section.
3. Otherwise mark `conclusion_missing: true` and retain the example only if the remaining input is usable.
4. Drop clearly corrupted or empty extraction results.

Each processed record must include extraction metadata, such as:

```json
{
  "intro_source": "Introduction",
  "conclusion_source": "Conclusion",
  "conclusion_missing": false,
  "used_discussion_fallback": false,
  "extraction_warnings": [],
  "input_token_count": 0
}
```

The parser must not assume every paper has exactly `\\section{Introduction}` and `\\section{Conclusion}`.

## 8. Tokenizer policy

A tokenizer is not written from scratch. It is loaded from the selected student model's Hugging Face repository using the `transformers` library:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
encoded = tokenizer(text, add_special_tokens=True)
num_tokens = len(encoded["input_ids"])
```

The tokenizer is used before training to measure the actual length of each example and identify records that exceed the planned limit. The same tokenizer and chat template must be used when formatting training examples.

The tokenizer does not decide what the paper means or summarize anything. It converts text into the integer token IDs the model was trained to understand. Different model families use different token vocabularies, so token counts must be measured with the candidate student's tokenizer rather than character-count guesses.

During the pilot, record token counts for each candidate student. Use a configurable maximum length and an explicit truncation policy instead of silently allowing examples to overflow.

## 9. Teacher labels and validation

Teacher generation is a separate, logged phase. Every label record should contain:

- Paper ID and dataset split
- Teacher model identifier
- Prompt version
- Generation settings
- Input/output token usage when available
- Estimated cost
- Raw teacher response
- Parsing/validation status
- Retry/error information

Automatic checks should flag:

- Empty or excessively short outputs
- Outputs exceeding the target length
- Missing required sections or fields
- Unexplained acronyms
- Obvious prompt leakage
- Claims containing unsupported numbers when source numbers are unavailable
- Repetition or malformed output

Automatic checks are a **filter and triage system**, not a reliable factuality oracle. A human should audit a small random sample and every category of automatic failure before full-scale generation.

## 10. Evaluation policy

Evaluate three systems on the same frozen held-out papers:

1. Base student model
2. QLoRA fine-tuned student
3. Teacher model

Use automatic metrics for useful signals, not as the sole definition of success:

- ROUGE: surface overlap with the teacher/reference
- BERTScore: semantic similarity
- Structured checklist: required content and format
- Factuality checks against the source input where feasible
- Human rubric: clarity, factuality, coverage, jargon, concision, and calibration

The recommended design is hybrid:

- Automate repeatable checks and scoring where possible.
- Manually inspect a stratified sample for factual correctness and readability.
- Use blinded pairwise comparisons for human judgments.

A model-generated accuracy score should be treated as a warning signal, not ground truth. The evaluator may miss subtle hallucinations or confidently agree with incorrect teacher labels.

## 11. Model-selection policy

Benchmark candidate Qwen students before selecting the training base. Use the same small evaluation set, input prompt, decoding settings, and token limits for each candidate.

Record:

- Output quality by the evaluation rubric
- Input and output speed
- Peak VRAM usage
- Context-window behavior
- Chat-template compatibility
- License and distribution constraints
- Training smoke-test success

Cost matters, but the final selection should be defensible as a constrained engineering decision: quality per dollar, quality per VRAM, and reproducibility.

## 12. Experiment stages and stop conditions

### Stage A — 10–25 paper pilot

Stop and fix the pipeline if extraction is unreliable, token lengths are surprising, teacher outputs are inconsistent, or measured cost is materially higher than expected.

### Stage B — small training smoke test

Run a tiny QLoRA job to verify loading, formatting, memory use, checkpointing, and generation. Do not scale until it completes successfully.

### Stage C — expanded dataset

Expand only after the pilot and smoke test pass. Freeze the test split before teacher generation for the expanded set.

### Stage D — final comparison

Run controlled base/fine-tuned/teacher evaluation and preserve all prompts, seeds, model revisions, and outputs.

## 13. Libraries and build-versus-buy policy

Prefer established libraries for standard, failure-prone infrastructure. Write project-specific code only for the decisions that define this experiment: corpus selection, extraction policy, record schemas, budgeting, prompting, and evaluation reports.

| Need | Preferred tool/library | Why |
|---|---|---|
| arXiv metadata | Python standard library (`urllib`, `xml.etree.ElementTree`) or a thin arXiv client | Avoid unnecessary dependencies for a simple Atom API; enforce our own rate limiting and retries |
| HTTP, retries, timeouts | `httpx` or `requests` | Do not hand-roll HTTP behavior |
| Archive handling | Python `tarfile`, `zipfile`, `gzip`, `pathlib` | Standard library is sufficient |
| LaTeX parsing/cleanup | Start with small tested project code; optionally use `pylatexenc` for command-aware conversion | Section selection is project-specific; do not build a full TeX compiler |
| Metadata/data records | `pydantic` or standard-library `dataclasses` | Validate JSONL records and make failures explicit |
| Configuration | YAML/TOML via `PyYAML` or Python `tomllib` | Keep corpus/model/training settings out of code |
| Tokenization/model loading | Hugging Face `transformers` and `tokenizers` | Use the selected model's official tokenizer and chat template |
| Dataset operations | Hugging Face `datasets` | Streaming, mapping, filtering, and reproducible dataset handling |
| Fine-tuning | `peft`, `trl`, `bitsandbytes`, `accelerate`, `torch` | Standard QLoRA/SFT stack; do not implement quantization or backpropagation |
| Automated metrics | `evaluate`, `rouge_score`, `bert_score` | Reuse established metric implementations and document versions |
| Tests | `pytest` | Fast parser/schema/budget regression tests |
| Formatting/linting | `ruff` | One lightweight tool for Python formatting and static checks |
| Experiment metadata | JSONL/CSV first; optional Weights & Biases later | Avoid adding tracking infrastructure until local runs work |

The first implementation should keep the dependency set small. Add a library when it removes a substantial correctness or maintenance risk, not merely to avoid writing a few lines. Conversely, do not reimplement standards-heavy components such as tokenization, quantization, training, or evaluation metrics.

## 14. Budget guard

Preferred total API spend is under $10. Reserve part of the budget for retries, prompt iteration, and evaluation rather than spending everything on first-pass labels.

Before bulk generation, estimate cost from pilot measurements and require:

```text
projected_cost + reserved_buffer <= budget_limit
```

The teacher-generation script should support a dry run and stop before the configured budget ceiling. Exact prices and model identifiers must be verified at implementation time rather than hard-coded from this planning document.
