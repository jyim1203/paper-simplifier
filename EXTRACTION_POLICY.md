# Extraction Policy

## Primary route: TeX source

When an arXiv source archive is available, use the top-level TeX entrypoint identified by arXiv metadata (usually `_main.tex` or `main.tex`). Resolve narrative `\\input{...}` and `\\include{...}` files recursively.

Do not treat every `.tex` file as paper prose. Figure and table inputs are excluded from the main narrative because they often contain drawing commands, table cells, or layout noise rather than readable explanation. Their existence is recorded as an extraction warning.

The first implementation extracts:

- title
- abstract
- Introduction, with Background as a fallback name
- Conclusion or Conclusions
- Discussion/Discussions when no conclusion exists

Common citations, labels, references, formatting commands, comments, and math blocks are removed or simplified. This is intentionally conservative: warnings are retained rather than silently presenting a damaged section as perfect text.

## Fallback route: PDF text

If the source archive is missing, not TeX, malformed, or fails quality checks, use text extraction from the PDF. Record `extraction_method: pdf_text` and warnings such as `possible_two_column_ordering`, `figure_or_table_text_detected`, or `equation_structure_degraded`.

PDF extraction is acceptable for a pilot, but it is lower quality for section boundaries, equations, tables, and two-column reading order. OCR is explicitly out of scope for v1 because modern arXiv AI/ML papers usually have a text layer and OCR would add substantial dependencies and noise.

## Quality gate before retaining a record

A processed record should not be retained as usable merely because extraction returned bytes. Check that:

- title is non-empty;
- abstract is non-empty;
- introduction is non-empty and above a minimum character threshold;
- conclusion or discussion is non-empty, or the record is explicitly flagged as missing it;
- extracted text is not mostly TeX commands, figure syntax, or table markup;
- the section order is plausible;
- warnings are saved with the record.

The extractor does not decide final corpus relevance. Category, topic, duplicate, and educational-value decisions happen in the later corpus funnel.
