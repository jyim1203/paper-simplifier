# Paper Simplifier — Progress Tracker

This file records decisions and verified milestones. It is not a substitute for experiment artifacts or evaluation reports.

## Current status

**Phase:** Ingestion pilot — defects 1–3 and 7 fixed and verified; corpus at 30 papers  
**Next action:** Fix defects 4–6 under "Review findings" below, then the quality gate and token measurements, then the PDF fallback route  
**Overall status:** In progress — extraction no longer drops macro-defined names; defects 4–6 and the PDF route remain

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
- [x] Harden TeX extraction: brace-balanced heading boundaries, prefix section-name matching, literal input resolution, visual/math environment stripping, empty-field warnings.
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
| 2026-09-12 | Ingestion pilot | `tools/parser_probes.py` 16/16; `tools/corpus_quality_check.py` over 18 real arXiv sources: title/abstract/conclusion 100%, intro 94% (one paper's intro is commented out upstream), TeX-artifact residue 0% | LaTeX parser accepted; PDF fallback and quality gate are next |
| 2026-09-13 | Review | Independent review subagent re-ran the suite (27 tests, 9 subtests), the probes (16/16) and the corpus harness; reproduced 3 silent-corruption defects | Parser accepted with defects open; see "Review findings" |
| 2026-09-13 | Fix | Defects 1–3 fixed tests-first (27 → 30 tests). Follow-up review found the defect-3 fix had over-reached and deleted prose after `\label`; scoped to citations (31 tests) | Corpus diff 1/29, an improvement; defects 4–7 open |
| 2026-09-14 | Corpus + Fix | Added 2606.19348 (30 papers). Fixed defect 7 (text macros inlined, not deleted) and three latent regressions it introduced (34 → 37 tests) | 22 fields restored over 30 papers; 0 field changes from the follow-up fixes |

## Review findings — parser hardening (2026-09-13)

An independent review subagent re-ran the tests and probes and hunted for silent failure modes.

- Confirmed directly: 16/16 probes; 27 tests passed, 9 subtests passed.
- Confirmed: all eight hardening features behave as described.
- Refuted: the "18 sources; title/abstract/conclusion 100%; residue 0%" figure is **not
  reproducible**. The harness's default sample is capped at 10 IDs (the arXiv API returned
  HTTP 429 and the fallback list holds 10 entries). Over the 29 sources actually cached:
  title 96%, abstract 100%, introduction 96%, conclusion-or-fallback 100%, noise-flagged 7%
  — and both noise hits are false positives of the harness's own `&` heuristic (literal prose
  ampersands). Real TeX residue was 0 on that sample.

### Open defects

Defects 1–3 produce **silently wrong fields with no warning** and were reproduced independently.

| # | Defect | Impact | Where |
|---|---|---|---|
| 1 | A heading command inside a macro definition registers as a real section boundary | Wrong `conclusion`, no warning | `_section_blocks` runs on raw text before definitions are removed |
| 2 | Heading-like text inside `verbatim`/`lstlisting` registers as a heading | Real section silently truncated or lost | `_section_blocks` runs before `_strip_environments` |
| 3 | A two-brace-group `\cite{a}{b}` leaks the second group into prose | TeX residue / injected prose | `_DROP_COMMAND_WITH_ARG_RE` consumes only one `{..}` group |
| 4 | `\chapter`-style documents lose both introduction and conclusion | Content dropped (warns) | `_section_blocks` picks `\section` whenever any exists |
| 5 | Escaped braces `\{x\}` leave stray backslashes | Residue | `_BRACE_RE` / `_ESCAPED_CHAR_RE` |
| 6 | Harness caches an empty `src/` for PDF-only papers | Mislabeled measurement | `corpus_quality_check.py`: `dest.mkdir` runs before the `%PDF` check |
| 7 | Custom macros are deleted from prose instead of expanded | Empty macro-based titles (drives the title 96%) | `normalize_tex_text` (`_COMMAND_RE`) |

Also confirmed: PyMuPDF is not installed, so the PDF route **raises `RuntimeError`** out of
`paper_extract.py` rather than returning a record carrying warnings.

### Resolution (2026-09-13)

Defects 1–3 and 7 are fixed and verified. Defects 4–6 and the PDF route are still open.

| # | Status |
|---|---|
| 1 | Fixed — `_strip_definitions` reads macro bodies with a bracket scanner |
| 2 | Fixed — environments are stripped before the heading scan |
| 3 | Fixed — `_TWO_GROUP_CITE_RE` drops a citation's second mandatory group |
| 7 | Fixed — zero-argument text macros are inlined instead of deleted |
| 4–6 | Open |

### Defect 7 — macro deletion (2026-09-14)

Found by running the parser on arXiv 2606.19348 (now cached as
`data/cache/arXiv-2606.19348v1`). The paper defines its model names as macros
(`\newcommand{\dsviv}{DeepSeek-V4}`); every unknown macro was being deleted, so
the title and abstract lost the model name and all parameter counts with **no
warning** — the fields were still non-empty, so no automatic metric could see it.

`_collect_macros` now builds a table of zero-argument definitions and
`_expand_macros` inlines them. Three follow-up review findings were fixed in turn:
expansion must run *before* environment stripping (a body can introduce a dropped
environment); bodies holding counter/environment commands are structural and are
not collected; and the table must be built from environment-stripped source so a
`\newcommand` shown inside a code listing is not harvested.

Corpus diff over 30 papers: 22 fields restored, 4 titles losing only a stray
backslash, 0 section-resolution changes, and 0 field changes attributable to the
three follow-up fixes.

The first attempt at defect 3 added the second group to the *shared* drop regex,
so it applied to every drop-command. `\label{key}{prose}` then deleted the prose,
and 2401.00664v7's abstract silently lost real sentences. A follow-up review
caught it; the rule is now scoped to citations only.

Corpus diff against the pre-fix parser: 1 of 29 papers differs, and that one is
an improvement (macro residue removed from a conclusion).

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
