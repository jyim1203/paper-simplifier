"""Select and extract paper input with TeX-first, PDF-fallback policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from .latex_extract import extract_tex_project


def _find_tex_entrypoint(root: Path) -> Path | None:
    preferred = ("_main.tex", "main.tex", "paper.tex")
    for name in preferred:
        path = root / name
        if path.is_file():
            return path
    candidates = sorted(root.glob("*.tex"))
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "\\begin{document}" in text and "\\documentclass" in text:
            return path
    return None


def _find_pdf(root: Path) -> Path | None:
    pdfs = sorted(root.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def select_extraction_input(root: str | Path) -> dict:
    """Choose the preferred TeX entrypoint, otherwise one PDF."""
    root_path = Path(root).resolve()
    tex = _find_tex_entrypoint(root_path)
    if tex:
        return {"method": "latex_source", "path": tex}
    pdf = _find_pdf(root_path)
    if pdf:
        return {"method": "pdf_text", "path": pdf}
    raise FileNotFoundError(f"no TeX entrypoint or PDF found in {root_path}")


def extract_pdf_text(
    pdf_path: str | Path,
    *,
    opener: Callable[[str | Path], object] | None = None,
) -> dict:
    """Extract a PDF text layer using PyMuPDF; OCR is intentionally not attempted."""
    if opener is None:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError(
                "PDF fallback requires PyMuPDF; install pymupdf or use a TeX source archive"
            ) from exc
        opener = fitz.open
    document = opener(str(pdf_path))
    pages = [page.get_text("text") for page in document]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    return {
        "extraction_method": "pdf_text",
        "source_path": str(Path(pdf_path).name),
        "text": text,
        "page_count": len(pages),
        "extraction_warnings": [
            "possible_two_column_ordering",
            "figure_or_table_text_detected",
            "equation_structure_degraded",
        ],
    }


def extract_paper(root: str | Path) -> dict:
    """Run the selected extraction route and annotate the selected source."""
    selected = select_extraction_input(root)
    if selected["method"] == "latex_source":
        record = extract_tex_project(selected["path"])
    else:
        record = extract_pdf_text(selected["path"])
    record["source_selection"] = selected["method"]
    record["source_path"] = str(selected["path"].name)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a paper from a TeX/PDF project directory.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(extract_paper(args.root), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
