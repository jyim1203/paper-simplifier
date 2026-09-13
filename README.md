# Paper Simplifier

A small research project for teaching a compact language model to turn AI/ML papers into plain-language explanations.

## arXiv candidate scraper

The first implementation is a metadata-only candidate-manifest tool. It uses arXiv's Atom API and writes one JSON object per line:

```bash
PYTHONPATH=src python -m paper_simplifier.arxiv_client \
  --categories cs.AI cs.CL cs.LG \
  --start-date 2017-01-01 \
  --end-date 2026-09-12 \
  --start 0 \
  --max-results 10 \
  --output data/manifests/candidate_papers.jsonl
```

The default is deliberately small. Do not start with the full corpus. Inspect a small metadata page first, then add source downloading and LaTeX extraction for the selected pilot.

Run the local test suite with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## arXiv protocol decisions

- The API endpoint is `https://export.arxiv.org/api/query`.
- No API key is required for this endpoint.
- Requests identify themselves with a descriptive User-Agent.
- One client instance enforces a 3-second minimum interval between API requests. Keep this conservative interval for the project rather than parallelizing requests.
- Requests use small pages and ascending submission-date order for reproducibility. Pagination should be added later, with checkpoints, rather than issuing a large unbounded request.
- Records preserve both the canonical ID and the exact version returned by the API. The CLI keeps the highest version per canonical ID.
- Metadata is stored in a manifest even before a paper is accepted. Inclusion, topic scoring, deduplication across related works, and source quality are later funnel stages.
- Source archives are not downloaded by the CLI yet. `download_source()` is an explicit one-paper primitive for the upcoming pilot; callers should extract it and delete it by default.

## Extraction CLI

The extractor accepts a directory containing an arXiv source project and/or a PDF. It prefers `_main.tex`, `main.tex`, or another TeX entrypoint, and falls back to PDF text extraction only when no TeX entrypoint is found:

```bash
PYTHONPATH=src python -m paper_simplifier.paper_extract \
  tests/fixtures/2609.11607v1 \
  --output data/processed/2609.11607v1.json
```

The PDF fallback requires PyMuPDF (`pymupdf`). OCR is intentionally not part of v1.

## Current scope boundary

This code does **not** yet decide whether a paper belongs in the final corpus. It extracts candidate text and records quality warnings; category relevance, duplicate handling, and manual inclusion decisions remain separate corpus-funnel stages.

The next slice is to run the extractor on a real source archive copied into the project workspace, add quality thresholds, and measure section/token lengths before starting the 10–25-paper pilot.
