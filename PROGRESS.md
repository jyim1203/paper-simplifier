# Paper Simplifier — Progress Tracker

This file records decisions and verified milestones. It is not a substitute for experiment artifacts or evaluation reports.

## Current status

**Phase:** Ingestion pilot — TeX/PDF extraction slice implemented  
**Next action:** Run the extractor on a real source archive copied into the workspace, then add quality thresholds and token measurements  
**Overall status:** In progress

## Decisions locked so far

- [x] Use Qwen models for teacher/student experiments.
- [x] Prefer total API spending below $10.
- [x] Keep a budget reserve for retries, prompt iteration, and evaluation.
- [x] Use teacher-generated synthetic instruction tuning / sequence-level distillation.
- [x] Use title + abstract + introduction as the core input.
- [x] Use conclusion when available.
- [x] Try final discussion as a conclusion fallback.
- [x] Keep missing-conclusion flags instead of silently pretending every paper has one.
- [x] Prefer temporary source download and extraction over retaining all raw source archives.
- [x] Load tokenizers from the selected Hugging Face student model; do not write one from scratch.
- [x] Begin with a small end-to-end pilot before scaling toward 1,000 papers.
- [x] Benchmark candidate student models before committing to training.
- [x] Combine automatic validation with manual human auditing rather than relying on either alone.
- [x] Prefer established libraries for standard infrastructure; write custom code only for project-specific behavior.

## Initial library shortlist

- [ ] `httpx` or `requests` for HTTP, timeouts, and retries.
- [ ] Python standard library for XML parsing and archive extraction where sufficient.
- [ ] `pylatexenc` only if the pilot shows that simple LaTeX cleanup is insufficient.
- [ ] `pydantic` or `dataclasses` for validated records.
- [ ] `transformers` / `tokenizers` for model loading and tokenization.
- [ ] `datasets` for dataset transformations.
- [ ] `torch`, `bitsandbytes`, `peft`, `trl`, and `accelerate` for QLoRA/SFT.
- [ ] `evaluate`, `rouge_score`, and `bert_score` for automated metrics.
- [ ] `pytest` and `ruff` for tests and code quality.
- [ ] Optional W&B only after local experiment artifacts are working.


## Deferred design decisions

- [x] Create an initial corpus-selection proposal: 2017–cutoff, relevance funnel, soft popularity/lab signals, stratified sampling.
- [ ] Define paper inclusion and exclusion criteria after inspecting candidate-pool counts.
- [ ] Define the teacher prompt and output schema.
- [ ] Choose exact teacher model identifier and verify current pricing/limits.
- [ ] Choose the student model after a small controlled benchmark.
- [ ] Set exact input token cap and truncation policy.
- [ ] Define train/validation/test split policy.
- [ ] Define human evaluation rubric and number of reviewers.
- [ ] Decide whether to retain a larger debug source cache.

## Implementation milestones

### Milestone 0 — Project skeleton

- [ ] Create Python project configuration.
- [ ] Add dependency pinning strategy.
- [ ] Add data/cache paths and ignore rules.
- [ ] Add record schemas and validation tests.

### Milestone 1 — Ingestion pilot

- [x] Query arXiv metadata with rate limiting.
- [x] Save candidate-paper manifest.
- [x] Add a one-paper source-download primitive (not yet used by the CLI).
- [ ] Download source temporarily.
- [x] Add TeX-first extraction with input/include resolution.
- [x] Add PDF text fallback extraction.
- [x] Extract title, abstract, introduction, conclusion, and discussion fallback.
- [x] Save extraction warnings and quality flags.
- [ ] Measure token counts with a candidate Qwen tokenizer.
- [ ] Report archive and processed-data sizes.
- [ ] Manually inspect pilot records.

### Milestone 2 — Teacher pilot

- [ ] Freeze an initial teacher prompt version.
- [ ] Generate labels for the pilot only.
- [ ] Log token usage, latency, retries, and estimated cost.
- [ ] Run automatic output validation.
- [ ] Audit a representative sample manually.
- [ ] Revise and freeze the prompt before expansion.

### Milestone 3 — Student benchmark and training smoke test

- [ ] Run candidate Qwen base models on identical examples.
- [ ] Measure quality, VRAM, speed, and formatting.
- [ ] Select a defensible base model.
- [ ] Run a tiny QLoRA job.
- [ ] Verify checkpoint reload and generation.

### Milestone 4 — Expanded experiment

- [ ] Freeze the held-out split.
- [ ] Expand the training corpus.
- [ ] Generate labels under the budget guard.
- [ ] Fine-tune the selected student.
- [ ] Evaluate base, fine-tuned, and teacher outputs.
- [ ] Produce a final report with limitations.

## Experiment log

| Date | Stage | Artifact/result | Decision or next action |
|---|---|---|---|
| 2026-09-10 | Planning | Initial design reviewed | Architecture documents created; pilot is next |

## Definition of done for the pilot

The pilot is not done until all of these are true:

- [ ] At least 10 usable paper records exist.
- [ ] Each record has metadata and extraction flags.
- [ ] Token counts were measured with an actual candidate tokenizer.
- [ ] No retained record has silently empty core sections.
- [ ] Storage usage was measured.
- [ ] Teacher generation can be dry-run or stopped by a budget ceiling.
- [ ] At least one end-to-end teacher label was generated successfully.
- [ ] The result was manually inspected before scaling.
