import tempfile
import unittest
from pathlib import Path

from src.paper_simplifier.latex_extract import (
    extract_tex_project,
    load_tex_project,
    normalize_tex_text,
)

PROSE = "This is a sufficiently long body of prose for the section. " * 6


def build_project(root, files):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def full_doc(body, *, title="A Test Paper", abstract="Abstract text.", abstract_env=True):
    """A minimal complete document wrapping ``body``."""
    abstract_block = (
        f"\\begin{{abstract}}{abstract}\\end{{abstract}}\n"
        if abstract_env and abstract
        else ""
    )
    title_line = f"\\title{{{title}}}\n" if title else ""
    return (
        "\\documentclass{article}\n"
        f"{title_line}"
        "\\begin{document}\n\\maketitle\n"
        f"{abstract_block}{body}\n"
        "\\end{document}\n"
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

    def test_introduction_variants_are_recognised(self):
        headings = ("Introduction", "Introduction and Related Work", "1 Introduction", "Background")
        for heading in headings:
            with self.subTest(heading=heading):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    build_project(root, {
                        "main.tex": full_doc(
                            f"\\section{{{heading}}}\n{PROSE}\n"
                            f"\\section{{Conclusion}}\n{PROSE}"
                        ),
                    })
                    record = extract_tex_project(root / "main.tex")
                self.assertTrue(record["introduction"], heading)

    def test_conclusion_variants_are_recognised(self):
        headings = (
            "Conclusion",
            "Conclusions",
            "Conclusion and Future Work",
            "Conclusions and Future Work",
            "Discussion and Conclusion",
        )
        for heading in headings:
            with self.subTest(heading=heading):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    build_project(root, {
                        "main.tex": full_doc("\\input{body}"),
                        "body.tex": (
                            f"\\section{{Introduction}}\n{PROSE}\n"
                            f"\\section{{{heading}}}\n{PROSE}"
                        ),
                    })
                    record = extract_tex_project(root / "main.tex")
                self.assertTrue(record["conclusion"], heading)
                self.assertFalse(record["conclusion_missing"], heading)

    def test_discussion_fallback_covers_plural_and_combined_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc("\\input{body}"),
                "body.tex": (
                    f"\\section{{Introduction}}\n{PROSE}\n"
                    f"\\section{{Discussions and conclusions}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertTrue(record["conclusion"])
        self.assertTrue(record["used_discussion_fallback"])
        self.assertEqual(record["conclusion_source"], "Discussions and conclusions")

    def test_headings_with_optional_and_nested_arguments_are_boundaries(self):
        body = (
            f"\\section[Intro]{{Introduction}}\n{PROSE}\n"
            f"\\section{{Results for \\textbf{{GPS}}}}\nRESULTS_CANARY {PROSE}\n"
            f"\\section[Conc]{{Conclusion}}\n{PROSE}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": full_doc(body)})
            record = extract_tex_project(root / "main.tex")
        self.assertTrue(record["introduction"])
        self.assertTrue(record["conclusion"])
        # A heading that fails to register would silently merge the sections.
        self.assertNotIn("RESULTS_CANARY", record["introduction"])

    def test_input_with_dotted_filename_resolves(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc("\\input{2.1-background}"),
                "2.1-background.tex": (
                    f"\\section{{Introduction}}\n{PROSE}\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
            missing = [w for w in record["extraction_warnings"] if w.startswith("missing_input")]
        self.assertEqual(missing, [])
        self.assertTrue(record["introduction"])

    def test_non_tex_input_is_not_merged_as_prose(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc("\\input{ref.bbl}\n\\input{body}"),
                "ref.bbl": "BIBLIOGRAPHY_CANARY",
                "body.tex": f"\\section{{Introduction}}\n{PROSE}\n\\section{{Conclusion}}\n{PROSE}",
            })
            record = extract_tex_project(root / "main.tex")
        combined = " ".join(record[key] for key in ("title", "abstract", "introduction", "conclusion"))
        self.assertNotIn("BIBLIOGRAPHY_CANARY", combined)
        self.assertIn("excluded_non_tex_input:ref.bbl", record["extraction_warnings"])

    def test_inline_table_does_not_leak_into_prose(self):
        table = (
            "\\begin{table}\n\\begin{tabular}{lcc}\n\\toprule\n"
            "Model & Acc & F1 \\\\\n\\midrule\n"
            "CANARY_TABLE_ROW & 94.2 & 0.91 \\\\\n\\bottomrule\n"
            "\\end{tabular}\n\\caption{Canary table.}\n\\end{table}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    f"\\section{{Introduction}}\n{PROSE}\n{table}\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("CANARY_TABLE_ROW", record["introduction"])
        self.assertNotIn("&", record["introduction"])

    def test_two_argument_citation_is_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    f"\\section{{Introduction}}\n{PROSE} As shown "
                    f"\\cite[e.g., by][p.~3]{{shapiro2021}} before.\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("shapiro2021", record["introduction"])
        self.assertNotIn("[e.g.", record["introduction"])

    def test_normalize_handles_thin_space_and_spacing_commands(self):
        self.assertEqual(
            normalize_tex_text(r"10\,000 samples and variable\_name here"),
            "10 000 samples and variable_name here",
        )
        self.assertEqual(normalize_tex_text(r"before \vspace{1em} after"), "before after")

    def test_abstract_command_style_is_supported(self):
        main = (
            "\\documentclass{article}\n\\title{A Test Paper}\n\\begin{document}\n\\maketitle\n"
            "\\abstract{Command style abstract.}\n"
            f"\\section{{Introduction}}\n{PROSE}\n\\section{{Conclusion}}\n{PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["abstract"], "Command style abstract.")

    def test_missing_title_and_abstract_are_flagged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    f"\\section{{Introduction}}\n{PROSE}\n\\section{{Conclusion}}\n{PROSE}",
                    title=None,
                    abstract=None,
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertIn("title_not_found", record["extraction_warnings"])
        self.assertIn("abstract_not_found", record["extraction_warnings"])


    def test_heading_inside_macro_definition_is_not_a_section_boundary(self):
        """A \\section living inside a \\newcommand must not create a section."""
        main = (
            "\\documentclass{article}\n"
            "\\newcommand{\\conclusionheader}{\\section{Conclusion}}\n"
            "\\title{A Test Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["conclusion"], "")
        self.assertIn("conclusion_or_discussion_not_found", record["extraction_warnings"])

    def test_heading_like_text_inside_verbatim_is_not_a_section_boundary(self):
        """A heading-looking line inside verbatim must not truncate a section."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    f"\\section{{Introduction}}\n{PROSE}\n"
                    "\\begin{verbatim}\n\\section{Conclusion}\n"
                    "fake conclusion text\n\\end{verbatim}\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("fake conclusion text", record["conclusion"])
        self.assertIn("sufficiently long body", record["conclusion"])

    def test_citation_with_two_mandatory_groups_leaves_no_residue(self):
        """\\citep{key}{postnote} must not leak the second group into prose."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    f"\\section{{Introduction}}\n{PROSE} As shown by "
                    "\\citep{smith2020}{extra group words} we improve things.\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("extra group words", record["introduction"])
        self.assertNotIn("smith2020", record["introduction"])


    def test_only_citation_commands_drop_a_second_adjacent_group(self):
        """A non-citation command must not swallow a following braced group.

        Regression guard: an earlier fix let the second-group rule apply to
        every command in the drop list, so \\label{key}{real prose} deleted the
        prose. Real corpus papers lost abstract sentences to this.
        """
        self.assertEqual(
            normalize_tex_text(r"see \label{eq:1}{REAL PROSE} here"),
            "see REAL PROSE here",
        )
        self.assertEqual(
            normalize_tex_text(r"note \footnote{a}{REAL PROSE} end"),
            "note REAL PROSE end",
        )


    def test_defined_text_macros_are_expanded_in_title_and_prose(self):
        """\\newcommand text macros must be inlined, not deleted.

        Real papers define their model names this way (\\dsviv -> DeepSeek-V4);
        deleting the macro silently strips the name from the title, abstract and
        body while every field still looks non-empty.
        """
        main = (
            "\\documentclass{article}\n"
            "\\newcommand{\\dsviv}{DeepSeek-V4}\n"
            "\\newcommand{\\dsvivp}{DeepSeek-V4-Pro}\n"
            "\\title{\\dsviv{}: A Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}We present \\dsviv{} and \\dsvivp{}.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE} We use \\dsviv{{}} here.\n"
            f"\\section{{Conclusion}}\n{PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("DeepSeek-V4", record["title"])
        self.assertIn("DeepSeek-V4-Pro", record["abstract"])
        self.assertIn("DeepSeek-V4", record["introduction"])
        self.assertNotIn("dsviv", record["abstract"])

    def test_parameterised_macro_body_is_not_inlined(self):
        """A macro with arguments cannot be inlined without parsing call sites.

        Guard against over-eager expansion: inlining ``[[#1]]`` would leak
        parameter placeholders into prose.
        """
        main = (
            "\\documentclass{article}\n"
            "\\newcommand{\\wrap}[1]{[[#1]]}\n"
            "\\title{A Test Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE} we \\wrap{{use}} it.\n"
            f"\\section{{Conclusion}}\n{PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("[[#1]]", record["introduction"])
        self.assertIn("use", record["introduction"])


    def test_line_break_is_not_half_eaten_by_the_thin_space_rule(self):
        """A LaTeX line break ``\\\\`` must not leave a stray backslash.

        The thin-space rule matches backslash+space, so it eats the second half
        of a line break unless the line-break rule runs first. Titles using
        ``\\\\`` for a visual break showed the residue.
        """
        normalized = normalize_tex_text(r"DeepSeek-V4: \\ Towards Efficiency")
        self.assertNotIn("\\", normalized)
        self.assertIn("Towards Efficiency", normalized)


    def test_macro_body_wrapping_a_dropped_environment_does_not_leak(self):
        """An environment introduced by a macro body must still be stripped.

        Expansion runs before environment stripping for this reason: otherwise
        \\myfig -> \\begin{figure}...\\end{figure} never gets removed and visual
        content leaks into prose (and into the title).
        """
        main = (
            "\\documentclass{article}\n"
            "\\newcommand{\\myfig}{\\begin{figure}\\caption{SECRETCAP}\\end{figure}}\n"
            "\\title{A Test Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE} See \\myfig{{}} now.\n"
            f"\\section{{Conclusion}}\n{PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("SECRETCAP", record["introduction"])
        self.assertNotIn("SECRETCAP", record["title"])

    def test_counter_macro_is_not_inlined_into_prose(self):
        """A counter macro body is structural, not text; inlining it leaves junk.

        \\thesection -> S\\arabic{section} expands to 'S' once \\arabic is deleted,
        so prose reads 'Section S section' where deleting the macro was correct.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    "\\renewcommand{\\thesection}{S\\arabic{section}}\n"
                    f"\\section{{Introduction}}\n{PROSE} As shown in Section "
                    "\\thesection{} we see.\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("S section", record["introduction"])

    def test_definition_inside_verbatim_is_not_harvested(self):
        """A \\newcommand shown inside a code listing is not a real definition."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    "\\begin{verbatim}\n\\newcommand{\\cmdone}{RESIDUE}\n"
                    "\\end{verbatim}\n"
                    f"\\section{{Introduction}}\n{PROSE} See \\cmdone{{}} now.\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertNotIn("RESIDUE", record["introduction"])


if __name__ == "__main__":
    unittest.main()
