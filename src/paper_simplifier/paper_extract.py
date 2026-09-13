"""Select and extract paper input with TeX-first, PDF-fallback policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from .latex_extract import extract_tex_project


def _toplevel_from_00readme(root: Path) -> str | None:
    """arXiv ships 00README.json naming the canonical toplevel file.

    Reading it beats guessing: a paper whose real root is ``main_arxiv.tex``
    often still ships a ``main.tex`` that is only a body fragment, and picking
    the fragment silently loses the title and abstract.
    """
    manifest = root / "00README.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return None
    for entry in data.get("sources", []) or []:
        if isinstance(entry, dict) and entry.get("usage") == "toplevel":
            filename = entry.get("filename")
            if filename and (root / filename).is_file():
                return filename
    return None


def _looks_like_root(path: Path) -> bool:
    """A real root document has a preamble and/or a document body."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "\\begin{document}" in text or "\\documentclass" in text


def _find_tex_entrypoint(root: Path) -> tuple[Path | None, str | None]:
    """Pick the TeX root: 00README first, then validated preferred names."""
    declared = _toplevel_from_00readme(root)
    if declared:
        return root / declared, "00readme"

    preferred = ("_main.tex", "main.tex", "paper.tex", "manuscript.tex")
    for name in preferred:
        path = root / name
        if path.is_file() and _looks_like_root(path):
            return path, "preferred_name"

    candidates = sorted(root.glob("*.tex"))
    for path in candidates:
        if "\\documentclass" in path.read_text(encoding="utf-8", errors="ignore"):
            return path, "documentclass_scan"
    for path in candidates:
        if _looks_like_root(path):
            return path, "document_body_scan"
    if candidates:
        return candidates[0], "first_tex_file"
    return None, None


def _find_pdf(root: Path) -> Path | None:
    pdfs = sorted(root.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def select_extraction_input(root: str | Path) -> dict:
    """Choose the preferred TeX entrypoint, otherwise one PDF."""
    root_path = Path(root).resolve()
    tex, source = _find_tex_entrypoint(root_path)
    if tex:
        return {"method": "latex_source", "path": tex, "entrypoint_source": source}
    pdf = _find_pdf(root_path)
    if pdf:
        return {"method": "pdf_text", "path": pdf, "entrypoint_source": "pdf"}
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
    record.setdefault("entrypoint_source", selected.get("entrypoint_source"))
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
