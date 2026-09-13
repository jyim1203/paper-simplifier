import tempfile
import unittest
from pathlib import Path

from src.paper_simplifier.paper_extract import (
    extract_pdf_text,
    extract_paper,
    select_extraction_input,
)


class FakePage:
    def __init__(self, text):
        self.text = text

    def get_text(self, mode="text"):
        return self.text


class FakeDocument:
    def __init__(self, pages):
        self.pages = pages

    def __iter__(self):
        return iter(self.pages)


class PaperExtractTests(unittest.TestCase):
    def test_pdf_extraction_returns_pages_and_explicit_quality_warnings(self):
        document = FakeDocument(
            [
                FakePage("Title\n\n1 Introduction\nIntro text."),
                FakePage("2 Conclusion\nConclusion text."),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "paper.pdf"
            pdf_path.write_bytes(b"fake pdf")
            record = extract_pdf_text(pdf_path, opener=lambda _: document)
        self.assertEqual(record["extraction_method"], "pdf_text")
        self.assertIn("1 Introduction", record["text"])
        self.assertEqual(record["page_count"], 2)
        self.assertIn("possible_two_column_ordering", record["extraction_warnings"])
        self.assertIn("equation_structure_degraded", record["extraction_warnings"])

    def test_selection_prefers_tex_entrypoint_over_pdf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "_main.tex").write_text("\\documentclass{article}", encoding="utf-8")
            (root / "paper.pdf").write_bytes(b"pdf")
            selected = select_extraction_input(root)
        self.assertEqual(selected["method"], "latex_source")
        self.assertEqual(selected["path"].name, "_main.tex")

    def test_selection_uses_pdf_when_no_tex_entrypoint_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "paper.pdf").write_bytes(b"pdf")
            selected = select_extraction_input(root)
        self.assertEqual(selected["method"], "pdf_text")
        self.assertEqual(selected["path"].name, "paper.pdf")

    def test_fixture_paper_uses_tex_and_excludes_figure_source(self):
        fixture = Path(__file__).parent / "fixtures" / "2609.11607v1"
        record = extract_paper(fixture)
        self.assertEqual(record["source_selection"], "latex_source")
        self.assertEqual(record["source_path"], "_main.tex")
        self.assertIn("Context-Augmented LLMs", record["title"])
        self.assertIn("Pretrained large language models", record["introduction"])
        self.assertIn("two-stage framework", record["conclusion"])
        self.assertTrue(any(w.startswith("excluded_visual_input:") for w in record["extraction_warnings"]))
        self.assertNotIn("FIGURE COMMANDS", record["introduction"])


    def test_selection_prefers_00readme_toplevel_over_guessed_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "00README.json").write_text(
                '{"sources": [{"usage": "toplevel", "filename": "real_root.tex"}]}',
                encoding="utf-8",
            )
            (root / "real_root.tex").write_text(
                "\\documentclass{article}\n\\begin{document}\n\\end{document}", encoding="utf-8"
            )
            (root / "main.tex").write_text("\\section{Introduction}\nfragment", encoding="utf-8")
            selected = select_extraction_input(root)
        self.assertEqual(selected["path"].name, "real_root.tex")
        self.assertEqual(selected["entrypoint_source"], "00readme")

    def test_selection_skips_body_only_fragment_named_main(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.tex").write_text("\\section{Introduction}\nbody only", encoding="utf-8")
            (root / "manuscript.tex").write_text(
                "\\documentclass{article}\n\\title{T}\n\\begin{document}\n\\end{document}",
                encoding="utf-8",
            )
            selected = select_extraction_input(root)
        self.assertEqual(selected["path"].name, "manuscript.tex")


if __name__ == "__main__":
    unittest.main()
