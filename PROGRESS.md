# Paper Simplifier — Progress Tracker

This file records decisions and verified milestones. It is not a substitute for experiment artifacts or evaluation reports.

## Current status

**Phase:** Ingestion pilot — parser defects 1–7 all fixed and verified; corpus at 30 papers  
**Next action:** Build the batch runner that writes records from `data/cache` into `data/processed` (nothing writes processed records yet), then the no-Introduction policy, then the PDF route  
**Overall status:** In progress — the parser defects are closed, but the 30-paper cache has never been turned into processed records, so the corpus itself is still a measurement, not a dataset  
**Budget note (2026-09-16, updated):** the account credit is exhausted — `usable $0.01`, and the portal reports `$21.99 of $22.00 cap` used. That cap is account-wide, not project-specific: the ~$8 this project planned to spend on teacher labels is gone, and it should be treated as spent until topped up. Two consequences: teacher labelling cannot start, and review subagents could not run on the pinned provider (`HTTP 402`, then `HTTP 400` on a stale model slug). Delegation was moved off `nous` onto the `deepseek` provider (`delegation.provider: deepseek`, `delegation.model: deepseek-flash`) to restore reviews; AGENTS.md still documents the old `nous` / `deepseek-v4.1-flash` pin. The global default model for new sessions is also credit-blocked, so `hermes chat -q` one-shots fail even though this session and delegation work.

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
- [ ] Define the policy for papers with no Introduction section: 2401.00678v1 is a
      `wlscirep` paper that opens with `\section*{Surgical robot learning}` and never
      says "Introduction", so it is correctly flagged but ships an empty `introduction`
      field and loses two to three sections of input. The candidate rule is to take the
      first body `\section*` block when no Introduction heading exists.

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
| 2026-09-16 | Fix | Defects 4–6 fixed tests-first (37 → 49 tests). Each fix then reviewed by an independent adversarial subagent | All three confirmed; but the reviews refuted one claim per defect and found 1 new mislabel plus 4 regressions in the first-pass fixes |
| 2026-09-16 | Fix + Review | Reworked both first-pass fixes after that review (49 → 59 tests): chapter split is now per-field, PDF detection is tar-aware | All 5 counterexamples fixed, both original targets intact, and **0 of 30** corpus records changed by the rework |
| 2026-09-16 | Review + Fix | Second review round (children died on an API credit 402; findings recovered from their transcripts and their own probe scripts re-run). Their 600-doc fuzzer showed the rework still LOST a field the old parser found on 29 documents (4.8%) | Cause: a heading matched by name was accepted even with an empty body, so a bare chapter heading shadowed a real section. Fixed in `_resolve_field` (62 tests). Fuzz now **0/600 lost**, 154/600 gained |

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

Defects 1–3 and 7 are fixed and verified. Defects 4–6 were fixed on 2026-09-16 (see below); the PDF route is still open.

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

## Defects 4–6 and their review (2026-09-16)

Each fix was written tests-first (the new tests were watched failing before the
fix landed) and then handed to an independent adversarial review subagent that
re-ran the suite, built a throwaway `git worktree` at HEAD to prove the new
tests fail against pre-fix code, and diffed parser output field-by-field over
the 30 cached papers. Every review confirmed its defect — and every review also
refuted at least one claim and found a real problem in the first-pass fix.

| # | Defect | Fix as delivered |
|---|---|---|
| 4 | `\chapter` documents lost both introduction and conclusion; an inner `\section{Background}` answered for the introduction | Field-by-field split resolution: chapter blocks first, section blocks for any field they do not supply (`_block_splits` / `_pick_across`) |
| 5 | One-char escapes leaked as residue — `\{a, b\}` → `\a, b\`, `H\"older` kept its backslash | `_ESCAPED_CHAR_RE` is no longer a 5-char whitelist; it is `\\(.)?` with `DOTALL`, so any remaining escape collapses to its character and a lone backslash is dropped |
| 6 | Harness cached an empty `src/` for PDF-only papers, so they reported `no_tex_or_pdf_entrypoint` | `%PDF` is only trusted after the tar attempt, and an empty `src/` is no longer a cache hit |

### What the reviews refuted

The reviews are worth their cost: the first-pass fixes each contained one real
defect that no test I wrote would have caught, because the corpus cannot
exercise those paths (0 of 30 cached papers use `\chapter`, and 0 reach the
archive shapes below).

- **Defect 6, new mislabel (fixed).** `data[:4] == b"%PDF"` is not a type test
  for a tar: a tar stores its first member's *name* at offset 0, so a TeX
  tarball whose first member is `%PDF_weird.tex` was labelled
  `pdf_only_submission` and the download skipped — a real paper dropped on every
  run, where pre-fix code said `not_cached` and would have recovered. The tar
  attempt now runs first and `_pdf_only_archive` confirms with
  `tarfile.is_tarfile`.
- **Defect 6, accepted as a parsed row (fixed).** A 0-byte archive passed as
  `gzip_single_tex` and produced a row with no `error` key and all four fields
  empty, inflating `parsed` and depressing every non-empty percentage.
  `safe_extract` now rejects empty payloads.
- **Defect 6, metric inflation (fixed, and my claim about it was too broad).**
  The new `stray_backslash` pattern also matched `\\` and `\_`, so `noise_total`
  double-counted text the older patterns already covered. It is now disjoint
  from the other *backslash* patterns — but `\&` is still charged twice, by
  `escaped_char` and by the character-level `ampersand` rule, which also fires on
  literal prose ampersands. `noise_total` is a count of pattern hits, not of
  distinct residue.
- **Defect 4, regressions (fixed).** The first-pass fix chose chapters
  document-wide, which emptied *both* fields on any document that merely
  mentions a chapter — a `\chapter` appendix after `\appendix`, an `\input`-ed
  appendix, a lone `\chapter{Part II}` divider, or a `\chapter` leaked out of
  `\iffalse` dead code. It also cost the conclusion on a chapter-front-matter
  thesis with a section-level conclusion. All four shapes are now fixed and
  pinned by tests.
- **Defect 4, rework still lost fields (fixed).** A second review round fuzzed
  600 heading combinations and found the *reworked* resolver losing a field the
  pre-fix parser had found on **29 documents (4.8%)**. The cause was name-only
  matching: a bare `\chapter{Conclusion}` with no body, or a block holding only a
  dropped figure, matched by heading and shadowed the real section-level
  section. `_resolve_field` now requires a candidate's body to normalize to
  something before accepting it, and falls through the splits otherwise. Same
  fuzzer: **0 of 600 lost**, 154 gained. `LOST=[]` on all 12 hand-built
  adversarial cases.
- **Defect 5, inaccurate comment (fixed).** The reviewer showed the escape
  reorder is *not* what fixes `\{x\}` — the optional group already covers that;
  the reorder only matters for adjacent escapes split by braces (`a\{\}b`). The
  code comment claimed otherwise and has been corrected.

### Verified corpus effect

30 cached papers, `--no-download`, before and after the whole batch:

- 28 parsed, 2 `pdf_only_submission` (2401.00684v1, 2401.02981v2 — correctly
  labelled now, previously `no_tex_or_pdf_entrypoint`).
- Title 100%, abstract 100%, introduction 96% (27/28 — see 2401.00678v1 below),
  conclusion-or-fallback 100%.
- Parser output changed for exactly **2** papers, each by **−1 character**:
  2401.00633v1 (a lone backslash before a newline) and 2401.00691v5
  (`H\"older`). No section-resolution, `conclusion_missing` or warning changes.
- Noise totals went from `{stray_backslash: 2, ampersand: 2}` to `{ampersand: 2}`;
  the `ampersand` pair are known false positives of the harness's own heuristic
  (literal prose ampersands).
- The review-driven rework changed **0 of 30** records — visible only in the
  shapes the corpus does not contain.

### Latent defects recorded, deliberately not fixed

Found by the reviews, pre-existing, and out of the approved scope for this pass.
None affects the current 30 papers.

- `_normalize_heading` applies no escape collapse, so heading-derived fields
  keep the same residue class the prose fix removed:
  `intro_source='Introduction \& Background'`, `_normalize_heading('Background
  \{Methods\}')` = `'background \methods\'`.
- Accents are de-escaped, not transliterated: `H\"older` → `H"older`. Residue-free
  but not the accented character.
- On mixed-level documents the conclusion body swallows trailing appendix text,
  because `\appendix` and `\chapter` are not boundaries under the section split.
- `\iffalse ... \fi` and `\begin{comment} ... \end{comment}` bodies are never
  stripped, so any command inside dead code reaches the heading scan.
- A cache whose `src/` was emptied (interrupted extraction) is relabelled
  `not_cached` rather than repaired; the harness never re-extracts an archive
  that is already on disk. `data/cache/arXiv-2401.00684v1` and
  `arXiv-2401.02981v2` still contain an empty `src/` left by the old harness.
- The harness's `&` noise heuristic still flags literal prose ampersands. A
  tar containing an *empty* `main.tex` is also still accepted as a parsed row
  with four empty fields — the empty-*archive* case is rejected now, but
  rejecting an empty *extraction* belongs to the quality gate in
  `EXTRACTION_POLICY.md`, which is not built yet.
- When the chapter split supplies a field, the titles of that chapter's inner
  `\section` headings survive as loose words in the prose (the heading command
  is dropped, its argument is not). Harmless on the current corpus, which has no
  chapter documents, but visible on chapter-structured papers.
- Two seeded harnesses caught the last two defects and neither is in the repo:
  a 600-document heading fuzzer (`$LOCALAPPDATA/Temp/ps_review/fuzz.py`) and an
  800-document canary fuzzer with a 28-row shape matrix
  (`$LOCALAPPDATA/Temp/ps_review2/{fuzz2,matrix}.py`). Both compare the
  working-tree parser against a `git worktree` of the baseline. Recreate that
  worktree to run them:
  `git worktree add --detach "$LOCALAPPDATA/Temp/ps_head_wt" HEAD`
  They exercise shapes `tests/` and `parser_probes.py` do not, and they are the
  only evidence for the claims in the section above. Promote them into `tools/`
  before the next change to this resolver.

## Third round: heading tiers — reviewed, and NOT safe to ship as-is

The second review round found one class; the fix for it produced another. Both
were reproduced with scripts that reviewer wrote before its session died on an API
credit error, and then the whole round was put through a fresh independent
adversarial review once delegation was moved to a working provider. That review
reproduced every number below and refused to sign the change off.

1. **Empty-body shadowing (fixed, and the fix is sound).** The resolver fell back
   to the other split only when that split returned no *match*, so a bare
   `\chapter{Conclusion}` with no body matched by name, shadowed the real
   section-level Conclusion, and also suppressed the discussion fallback.
   `_resolve_field` now requires a candidate's body to normalize to something.
   The review confirmed the gate is load-bearing — disabling it loses 31 fields
   on the 600-doc corpus and 26 on the 800-doc one — and that it empties no field
   in any corpus tested (0 across 600 + 800 + 216 + 3000 + 3660 + 28 documents).
2. **A weak name winning on split order (fixed).** Ranking by split first let
   `\chapter{Background}` take the introduction slot from a real
   `\section{Introduction}`, and `\chapter{Summary}` take the conclusion slot from
   `\section{Conclusion}`. Name quality now outranks split order. The review
   confirmed the tiers are net-beneficial (own-drop 57 with them vs 62 without on
   the 800-doc corpus; 30 vs 65 on its own generator) and that recognition is a
   strict superset — 0 of 3660 swept documents narrowed, 514 gained a field.

Seeded, deterministic, baseline vs working tree, all re-run by the reviewer:

| check | before | after |
|---|---|---|
| 600-doc heading fuzzer — documents losing a field | 29 (4.8%) | **0** |
| 800-doc canary fuzzer — documents losing a field | 0 | **0** |
| 800-doc canary fuzzer — documents where new LOST a conclusion | — | **0** |
| 28-row shape matrix — rows OK | 16 | 22 |
| tests / probes | 49 / 16 | 63 / 16 |
| 30-paper corpus | unchanged | unchanged |

### The review's verdict: do not push this hunk yet

**The root-cause explanation that used to be written here was wrong, and the
review refuted it.** This section previously claimed that all 42 own-section prose
drops came from `\iffalse`/`comment` bodies not being stripped. That is false: 5
of the 38 affected documents contain no dead code at all, and rebuilding all 38
with every `\iffalse...\fi` and `comment` block deleted *still* leaves 20 of them
dropping prose. Dead code is one of three mechanisms, not the explanation.

The dominant cause is **split precedence applied regardless of document order**.
`_block_splits` returns the chapter split first, so a chapter-level heading that
occurs *later* in the document shadows an *earlier* section-level heading whose
prose was the baseline's answer. Every one of the 103 affected documents in an
exhaustive 3660-document sweep is exactly the shape `\section{X}` followed by a
later `\chapter{Y}`. Three minimal dead-code-free reproductions run through the
real CLI on both sides:

- `\section{Introduction}` + prose, then `\chapter{Introduction}` + prose — the
  earlier section's introduction prose is dropped from every field.
- `\section{Summary}` + prose, then `\chapter{Conclusion}` + prose — the Summary
  prose is dropped.
- `\section{Motivation}` + prose, then `\section{Introduction}` whose body is only
  a comment, a `\subsection*{Summary}` and a figure — the introduction field
  becomes the single word `Summary` instead of the Motivation prose, because the
  gate accepts a body that is nothing but a nested heading's residue.

Ablation attributes it cleanly: reverting the split precedence alone removes
100% of the tight clean-document cases on the reviewer's own corpus (30 → 0),
while removing the tiers makes them worse (30 → 65) and removing the gate changes
nothing (30 → 30). So the gate is the fix for field loss, the tiers are a net
improvement, and **the split-precedence rule is the thing to fix** — by ordering
candidates within a tier by document position. That needs its own review.

Other findings from the same review:

- The reported "attribution regression" (baseline 19 → current 33) is a metric
  artifact: the metric unions the canaries of every block sharing a heading name
  and silently skips 292 of 469 checks for short-arg/`\textbf` headings. Under a
  strict metric — the reported source must name the exact block the text came
  from — baseline and current are both **0**. Not a regression.
- Fallback semantics hold exactly (624 shapes swept: 0 cases of
  `used_discussion_fallback` true with a non-Discussion source, 0 mismatches
  between `conclusion_missing` and an empty conclusion).
- Performance: 2.1x on a typical 15 KB paper (0.5 ms → 1.2 ms), rising to 8.0x on
  a 623 KB heading-dense document with no recognised name (9.8 ms → 78 ms),
  because `normalize_tex_text` now runs per candidate block instead of once per
  field over the chosen body. Absolute cost stays under 100 ms.
- **Test coverage is thinner than it looks.** Three of the four tests added this
  round pass on the unmodified baseline and therefore prove nothing: they build
  documents that contain a `\section`, so the baseline never hit the bug they
  describe. The emptiness gate ships with **no** discriminating test; the shape
  that would discriminate is a document with no `\section` at all (a bare
  `\chapter{Conclusion}` alongside a real `\chapter{Conclusions}`).

### Fix applied after that review

Two changes to the resolver, both aimed at the review's remaining defects:

1. **Candidates are ordered by document position within a tier.** `_resolve_field`
   merges the blocks of every split into one list sorted by heading offset (ties
   keep split order), so a chapter heading appearing later can no longer displace
   an earlier section whose prose was the answer. `_section_blocks` now returns the
   heading offset to make that possible.
2. **Child heading titles are stripped from block bodies.** `_strip_headings`
   removes `\section`/`\subsection`/`\subsubsection` commands *together with their
   titles* from the block they belong to, so a heading's name can no longer pass for
   that block's prose (the `\subsection*{Summary}` residue that let a
   comment-plus-figure block win a field).

Measured after the fix, same seeded harnesses, baseline vs current:

| check | pre-fix | post-fix |
|---|---|---|
| 800-doc canary fuzzer — prose-drop docs | 115 | **80** |
| 800-doc canary fuzzer — documents losing a field | 0 | 7 (see below) |
| 600-doc heading fuzzer — documents losing a field | 0 | 7 (see below) |
| 600-doc heading fuzzer — documents gaining a field | 154 | 143 |
| dead-code-free docs still losing a section's own prose | 3 / 216 | **3 / 216** |
| 30-paper corpus | unchanged | unchanged |
| tests / probes | 63 / 16 | 66 / 16 |

**The 7 new "field loss" documents are not content loss.** Every one had a baseline
field whose entire value was heading residue — measured values `Conclusion`,
`Part II`, `[Short]Background`, `Conclusion`, `Conclusions`, `Concluding remarks`,
`Discussion` — with the field's reported source being the heading it leaked from.
That residue is exactly what stripping removes, so the field is now empty and
carries an `introduction_not_found` / `conclusion_or_discussion_not_found` warning.
A one-word field silently passing as content is worse than an empty flagged field
the retention gate can reject.

**The 3 remaining clean-document cases are the documented tier trade:** a weaker
name earlier plus a stronger name later (`\section{Summary}` before
`\chapter{Conclusion}`) resolves to the stronger name and the earlier section's
prose is not used. That is the point of ranking, it is the trade the review measured
as net-beneficial (own-drop 57 with the tiers vs 62 without; 514 documents gained a
field), and it is now recorded in the code.

Performance improved at the same time: candidates are normalized once instead of
once per tier, so the worst case fell from 8.0x to 5.6x (7.1 ms → 40 ms at 600 KB)
and a realistic 15 KB paper is 1.6x (0.9 ms → 1.4 ms).

The coverage gap the review identified is closed: a document with **no** `\section`
at all is now tested (`test_bare_chapter_conclusion_does_not_shadow_a_filled_one` —
the only one of the three new tests that fails on baseline, verified in a HEAD
worktree; it failed with `'CONCLUSION_CANARY' not found in ''`). The other two guard
the intermediate revision rather than HEAD, since baseline never took the
chapter-first path; each says so in its docstring.

### Second review of the fix, and the corrected claims

A second independent review (94 API calls, 17.5 min) confirmed the fix repairs
C1/C3/C4, loses no prose (0 prose-bearing field losses; 777/777 baseline-nonempty
-> current-empty fields across 40,000 dead-code-free documents were bare heading
words; 0 of 1,063 drops handed a field to a weaker-named source; 0 attribution
violations under a strict metric) and confirmed the 30-paper corpus scoreboard is
identical. It still returned `push_safe: No`, and it was right to: **three claims
written here were wrong**, and a fourth defect (E4) survives.

**Claims corrected:**

- **"The corpus is unchanged"** was too strong. 8 of 28 records differ: the two
  known escape fixes, plus heading TITLES removed by `_strip_headings`
  (`Acknowledgments`, `Repro/Reproducibility Statement`, `Ethics Statement`,
  `Related work`, `Outline`, `Notations`, `Organization`, `Key Findings`,
  `DeepSeek-V3`, `Nonparametric Additive Models`, ...). Verified rather than
  assumed: no field is emptied, `intro_source`/`conclusion_source`/
  `conclusion_missing`/fallback flags and every scoreboard figure are unchanged,
  and each sentence adjacent to a removed title is still present in the same
  field. (A naive line-level diff made those removals look like prose deletions;
  substring checks against the current records showed all of it still there —
  the apparent prose deletions were diff alignment artifacts.)
- **"Performance is 5.6x worst case / 40 ms at 600 KB"** was density-dependent,
  not a bound. Measured: 1.8x at 16.5 KB, 3.95x at 600 KB realistic, 6.4x at
  600 KB heading-dense, 7.0x at 1 MB. Absolute cost at 600 KB realistic is
  ~27 ms.
- **"The residue class is closed"** was wrong — see E4.

**Fixed after the review** (all verified against the reviewer's own repro files):

- **E1** — a heading command used as *displayed text* (`\texttt{\subsection{X}}`)
  was stripped with its argument, deleting the word `X` from a real sentence. Now
  guarded by `_guarded`: a heading command preceded by `{` or `|` is not a heading.
- **E2** — removing a heading left no separator, gluing two clauses into one word
  (`clause.\subsection{Child title}Next` -> `clause.Next`). The strip now leaves a
  space.

**Open defects recorded, deliberately not fixed:**

- **E4 (the reviewer's strongest point).** The gate rejects a body only when it
  normalizes to *exactly* empty, so residue this module does not strip —
  `\paragraph{Summary}`, `\textbf{X}`, `\begin{center}`, `\item[X]` — leaves a
  word or two, which still wins a field on name alone while the paper's real prose
  leaves the record. Repro: `\section{Motivation}` + prose, then
  `\section{Introduction}` whose body is a comment, `\paragraph{Summary}` and a
  figure; current returns `introduction='Summary'` where the baseline returned the
  Motivation prose. Both repairs were tried and rejected on measurement:
  stripping `\paragraph`/`\subparagraph` deletes the sentence-shaped titles real
  papers give them (e.g. "The attribution helps establish trust, debug failure
  modes, and extract insights regarding"), and a 3-word/20-char content floor
  rejects genuinely short sections (field-loss docs 7 -> 21 in the 600-doc
  fuzzer). The test `test_paragraph_residue_is_not_a_section_body` encodes the
  defect and is marked `expectedFailure`, so it will surface as an unexpected
  success when the gate is tightened properly.
- **E3** — in the discussion fallback an exact `Discussion` beats an earlier
  `Discussion and Conclusion` whose prose actually contained the conclusion
  (2 of 5,776 exhaustive documents).
- **E5** — a child heading with a sentence-shaped title loses that title text from
  the field. This is what the corpus deletions are; defensible, but it is a
  behaviour change versus baseline.
- Perf, as above, is density-dependent.

Net state: 68 tests pass with 1 expected failure, 16/16 probes, fuzzer field
losses 7 of 600 (all bare heading words) and prose-drop 80 of 800, corpus
scoreboard identical with 8 records differing only by heading titles and the two
escape fixes.

Reachability on the current corpus, measured rather than assumed (the parser scans
`_strip_definitions(_strip_environments(loaded narrative))`, not every file on
disk, so `.sty`/`.cls` hits do not count):
- `\chapter` in scanned text: **0 of 28** parsed papers, so the split/tier logic
  is unreachable and the 30-paper output is identical before and after. This is
  why every corpus diff in this document is zero.
- `\iffalse` in scanned text: **2 of 28** — `2401.00633v1` (two template
  title/author blocks) and `2401.00676v1` (one block holding ~4.5 KB of narrative
  prose plus two `\subsection` commands). Neither block hides a `\chapter` or
  `\section`, so no phantom boundary is registered, and neither block's prose
  reaches an extracted field (checked directly against title/abstract/
  introduction/conclusion). The defect is reachable but currently harmless.

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
