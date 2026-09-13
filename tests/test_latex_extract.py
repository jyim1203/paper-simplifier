import tempfile
import unittest
from pathlib import Path

from src.paper_simplifier.latex_extract import (
    extract_tex_project,
    load_tex_project,
    normalize_tex_text,
)


class LatexExtractTests(unittest.TestCase):
    def test_normalize_removes_commands_citations_and_math(self):
        text = r"An \textbf{important} result~\citep{paper} uses $x^2$ and -- clear prose."
        normalized = normalize_tex_text(text)
        self.assertEqual(normalized, "An important result uses and - clear prose.")

    def test_normalize_drops_bibliography_commands(self):
        self.assertEqual(normalize_tex_text("Conclusion text.\\bibliography{main}"), "Conclusion text.")

    def test_load_project_resolves_input_but_skips_figures_and_tables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.tex").write_text(
                r"""\begin{document}
\begin{abstract}Abstract text.\end{abstract}
\input{body}
\end{document}""",
                encoding="utf-8",
            )
            (root / "body.tex").write_text(
                r"""\section{Introduction}
Intro text.
\input{figures/plot}
\input{tables/results}
\section{Conclusion}
Conclusion text.""",
                encoding="utf-8",
            )
            (root / "figures").mkdir()
            (root / "tables").mkdir()
            (root / "figures/plot.tex").write_text("FIGURE NOISE", encoding="utf-8")
            (root / "tables/results.tex").write_text("TABLE NOISE", encoding="utf-8")
            loaded, warnings = load_tex_project(root / "main.tex")
        self.assertIn("Intro text.", loaded)
        self.assertNotIn("FIGURE NOISE", loaded)
        self.assertNotIn("TABLE NOISE", loaded)
        self.assertEqual(len(warnings), 2)
        self.assertTrue(all(item.startswith("excluded_visual_input:") for item in warnings))

    def test_extract_project_uses_discussion_when_conclusion_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.tex").write_text(
                r"""\title{A Test Paper}
\begin{document}
\begin{abstract}Abstract text.\end{abstract}
\input{body}
\end{document}""",
                encoding="utf-8",
            )
            (root / "body.tex").write_text(
                r"""\section{Introduction}
Intro text.
\section{Discussion}
Discussion text.""",
                encoding="utf-8",
            )
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["title"], "A Test Paper")
        self.assertEqual(record["abstract"], "Abstract text.")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Discussion")
        self.assertTrue(record["used_discussion_fallback"])
        self.assertEqual(record["conclusion"], "Discussion text.")


if __name__ == "__main__":
    unittest.main()
