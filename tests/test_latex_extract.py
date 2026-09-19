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
            # Bodies must look like prose: a section whose whole body is a word or
            # two is treated as a leaked heading title, not content (see _has_prose).
            (root / "body.tex").write_text(
                f"\\section{{Introduction}}\n{PROSE}\n\\section{{Discussion}}\n{PROSE}",
                encoding="utf-8",
            )
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["title"], "A Test Paper")
        self.assertEqual(record["abstract"], "Abstract text.")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Discussion")
        self.assertTrue(record["used_discussion_fallback"])
        self.assertIn("sufficiently long body of prose", record["conclusion"])

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


    def test_single_character_escapes_leave_no_backslash_residue(self):
        r"""Every one-character escape collapses to its character, no backslash.

        The old rule listed only \_ \% \& \#. Anything else -- escaped braces,
        accents, a lone backslash before a newline -- fell through both the
        command rule (which needs a letter after the backslash) and the escape
        rule, and reached the corpus as residue: ``H\"older`` in a real abstract
        and ``\{a, b\}`` rendered as ``\a, b\``.
        """
        cases = [
            (r"the set \{a, b\} is finite", "the set a, b is finite"),
            (r'Helmut H\"older smoothness', 'Helmut H"older smoothness'),
            (r"Bernoulli\'s rule holds", "Bernoulli's rule holds"),
            (r"100\% of \_x", "100% of _x"),
            (r"a \| b", "a | b"),
            ("ends the line \\\nnext line", "ends the line\nnext line"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                normalized = normalize_tex_text(raw)
                self.assertNotIn("\\", normalized)
                self.assertEqual(normalized, expected)

    def test_escaped_brace_does_not_leave_a_backslash_behind(self):
        """Regression: the escape rule must run before the brace strip.

        Braces are stripped unconditionally, so collapsing escapes afterwards
        would see ``\\x\\`` and keep both backslashes.
        """
        self.assertEqual(normalize_tex_text(r"the set \{a, b\} is finite"), "the set a, b is finite")
        self.assertNotIn("\\", normalize_tex_text(r"a \{x\} z"))


    def test_chapter_document_is_split_on_chapters_not_sections(self):
        r"""A book/report document's top level is ``\chapter``, not ``\section``.

        ``\section`` is top level in article class but a subsection of a chapter
        elsewhere. Picking the section pattern whenever any ``\section`` exists
        made a chapter-style paper resolve its introduction to an inner
        ``\section{Background}`` and lose the conclusion, which then looked like
        a genuinely missing conclusion rather than a parser mistake.
        """
        main = (
            "\\documentclass{book}\n"
            "\\title{Chapter Style Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\chapter{{Introduction}}\n{PROSE}\n"
            f"\\section{{Background}}\nBACKGROUND_CANARY {PROSE}\n"
            f"\\section{{Method}}\n{PROSE}\n"
            f"\\chapter{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertFalse(record["conclusion_missing"])
        # An inner section is not a boundary: its prose belongs to the chapter.
        self.assertIn("BACKGROUND_CANARY", record["introduction"])
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])

    def test_starred_chapters_are_boundaries_even_with_inner_sections(self):
        r"""``\chapter*{...}`` must register exactly like ``\chapter{...}``."""
        main = (
            "\\documentclass{book}\n"
            "\\title{Starred Chapter Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\chapter*{{Introduction}}\n{PROSE}\n"
            f"\\section*{{Background}}\n{PROSE}\n"
            f"\\chapter*{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])

    def test_section_only_document_still_splits_on_sections(self):
        """Guard: choosing chapter boundaries must not affect article papers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {
                "main.tex": full_doc(
                    f"\\section{{Introduction}}\n{PROSE}\n"
                    f"\\subsection{{Detail}}\n{PROSE}\n"
                    f"\\section{{Conclusion}}\n{PROSE}"
                ),
            })
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertFalse(record["conclusion_missing"])


    def test_section_body_with_an_incidental_chapter_keeps_both_fields(self):
        r"""A ``\chapter`` appendix must not cost the section-level fields.

        Regression guard: preferring the chapter split document-wide emptied
        BOTH fields here and reported them as genuinely missing, where the old
        section scan found both. The chapter split resolves nothing at chapter
        level, so the section split must still answer.
        """
        main = (
            "\\documentclass{report}\n\\title{Mixed Level Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\appendix\n"
            f"\\chapter{{Appendix A}}\nAPPENDIX_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])
        self.assertFalse(record["conclusion_missing"])
        self.assertEqual(record["extraction_warnings"], [])

    def test_chapter_front_matter_still_finds_a_section_level_conclusion(self):
        r"""A chapter-level Introduction must not hide a section-level Conclusion.

        Each field is resolved against the chapter split first and the section
        split second, so this shape gets the chapter Introduction (an inner
        ``\section{Motivation}`` no longer answers for it) *and* keeps the
        conclusion.
        """
        main = (
            "\\documentclass{book}\n\\title{Frontmatter Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\chapter{{Introduction}}\n{PROSE}\n"
            f"\\section{{Motivation}}\n{PROSE}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])

    def test_chapter_in_dead_code_does_not_change_the_split(self):
        r"""``\chapter`` inside ``\iffalse`` is not a real chapter.

        Dead code is not stripped, so the command still reaches the scan. With a
        document-wide preference it flipped the split and emptied both fields;
        per field it resolves nothing and the section split answers.
        """
        main = (
            "\\documentclass{article}\n\\title{Dead Code Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE}\n"
            "\\iffalse\n\\chapter{Dead}\n\\fi\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])

    def test_lone_chapter_divider_between_sections_keeps_both_fields(self):
        r"""A ``\chapter{Part II}`` divider is not the document's top level."""
        main = (
            "\\documentclass{report}\n\\title{Part Divider Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE}\n"
            "\\chapter{Part II}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])


    def test_empty_chapter_heading_does_not_shadow_a_real_conclusion(self):
        r"""A bare ``\chapter{Conclusion}`` with no body is not the conclusion.

        Regression guard: a heading matched by name was accepted even when its
        body normalized to nothing, so an empty chapter-level ``Conclusion``
        blocked the real section-level one and the field came back empty with
        ``conclusion_missing`` set. A fuzz run over 600 heading combinations
        lost a field that the pre-fix parser found on 29 of them; this is that
        mechanism.
        """
        main = (
            "\\documentclass{book}\n\\title{Shadowing Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\chapter{Conclusion}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])
        self.assertFalse(record["conclusion_missing"])

    def test_empty_chapter_conclusion_does_not_kill_the_discussion_fallback(self):
        r"""An empty chapter Conclusion must not suppress the discussion fallback.

        With nothing to fall back from, the empty match suppressed the
        ``\section{Discussion}`` fallback entirely and the record lost a
        conclusion it previously had.
        """
        main = (
            "\\documentclass{book}\n\\title{Fallback Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\n{PROSE}\n"
            f"\\section{{Discussion}}\nDISCUSSION_CANARY {PROSE}\n"
            "\\chapter{Conclusion}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("DISCUSSION_CANARY", record["conclusion"])
        self.assertEqual(record["conclusion_source"], "Discussion")
        self.assertTrue(record["used_discussion_fallback"])

    def test_block_holding_only_a_dropped_environment_is_not_a_section(self):
        r"""A block whose body is nothing but a dropped figure is not prose."""
        main = (
            "\\documentclass{article}\n\\title{Figure Only Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            "\\section{Introduction}\n"
            "\\begin{figure}\n\\caption{only a figure}\n\\end{figure}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        # No introduction text exists, so the field must be flagged, not filled
        # from the figure block.
        self.assertEqual(record["introduction"], "")
        self.assertIn("introduction_not_found", record["extraction_warnings"])
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])


    def test_primary_heading_name_beats_a_weaker_one_in_the_other_split(self):
        r"""``Introduction`` anywhere beats ``Background`` anywhere.

        Heading names are ranked in tiers before the split is consulted. Ranking
        by split first let a chapter-level ``\chapter{Background}`` take the
        introduction slot from a real ``\section{Introduction}``, and a
        ``\chapter{Summary}`` take the conclusion slot from a
        ``\section{Conclusion}`` — discarding the real section's prose while
        every field stayed non-empty. The reviewer's shape matrix caught both.
        """
        main = (
            "\\documentclass{report}\n\\title{Tier Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            "\\chapter{Background}\nCHAPTER_BODY\n"
            f"\\section{{Introduction}}\nINTRO_CANARY {PROSE}\n"
            f"\\section{{Summary}}\nSUMMARY_BODY\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertIn("INTRO_CANARY", record["introduction"])
        self.assertEqual(record["conclusion_source"], "Conclusion")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])


    def test_later_chapter_heading_does_not_shadow_an_earlier_section(self):
        r"""A later ``\chapter`` must not displace an earlier ``\section``.

        Review regression guard: the chapter split used to win regardless of
        document order, so this document's introduction became the chapter's text
        and the earlier section's own prose was dropped from every field. All 103
        affected documents in a 3660-document sweep were exactly this shape.
        """
        main = (
            "\\documentclass{report}\n\\title{Order Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Introduction}}\nSECTION_INTRO_CANARY {PROSE}\n"
            f"\\section{{Conclusion}}\nSECTION_CONC_CANARY {PROSE}\n"
            f"\\chapter{{Introduction}}\nCHAPTER_INTRO_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertEqual(record["intro_source"], "Introduction")
        self.assertIn("SECTION_INTRO_CANARY", record["introduction"])
        self.assertNotIn("CHAPTER_INTRO_CANARY", record["introduction"])
        self.assertIn("SECTION_CONC_CANARY", record["conclusion"])

    def test_nested_heading_residue_is_not_a_section_body(self):
        r"""A block whose only text is a child heading's title is not prose.

        ``\subsection*{Summary}`` leaves the bare word ``Summary`` once commands
        and braces are stripped. That residue passed the emptiness gate, so a
        comment-plus-figure "Introduction" won the field and the real Motivation
        section's prose was discarded.
        """
        main = (
            "\\documentclass{article}\n\\title{Residue Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Motivation}}\nMOTIVATION_CANARY {PROSE}\n"
            "\\section{Introduction}\n"
            "%% comment only\n"
            "\\subsection*{Summary}\n"
            "\\begin{figure}\n\\caption{fig}\\end{figure}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("MOTIVATION_CANARY", record["introduction"])
        self.assertNotEqual(record["introduction"].strip(), "Summary")

    def test_bare_chapter_conclusion_does_not_shadow_a_filled_one(self):
        r"""The emptiness gate's discriminating shape: no ``\section`` anywhere.

        With no section heading the baseline used the chapter pattern directly and
        accepted the first name match, so a bare ``\chapter{Conclusion}`` with no
        body answered for the conclusion while the real ``\chapter{Conclusions}``
        was ignored and the field came back empty. Nothing in the suite built this
        shape before, so the gate had no test that could fail without it.
        """
        main = (
            "\\documentclass{book}\n\\title{Bare Heading Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\chapter{{Introduction}}\nINTRO_CANARY {PROSE}\n"
            "\\chapter{Conclusion}\n"
            f"\\chapter{{Conclusions}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("CONCLUSION_CANARY", record["conclusion"])
        self.assertFalse(record["conclusion_missing"])


    @unittest.expectedFailure
    def test_paragraph_residue_is_not_a_section_body(self):
        r"""KNOWN OPEN DEFECT (review counterexample E4), expected to fail.

        The gate rejects a body only when it normalizes to *exactly* empty, so
        ``\paragraph{Summary}`` leaves the bare word ``Summary``, which is enough
        to win the introduction slot on name alone while the paper's real
        Motivation prose leaves the record. Stripping ``\paragraph`` instead
        deletes sentence-shaped titles that real papers use ("The attribution
        helps establish trust, debug failure modes, ..."), and a content floor
        raises field losses from 7 to 21 in the 600-doc fuzzer. Neither trade was
        taken, so this test documents the defect: it should start passing (and be
        reported as an unexpected success) when the gate is tightened properly.
        """
        main = (
            "\\documentclass{article}\n\\title{Paragraph Residue Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            f"\\section{{Motivation}}\nMOTIVATION_CANARY {PROSE}\n"
            "\\section{Introduction}\n"
            "%% comment only\n"
            "\\paragraph{Summary}\n"
            "\\begin{figure}\n\\caption{fig}\\end{figure}\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("MOTIVATION_CANARY", record["introduction"])
        self.assertNotEqual(record["introduction"].strip(), "Summary")

    def test_heading_command_shown_as_displayed_text_keeps_its_word(self):
        r"""``\texttt{\subsection{X}}`` is an example, not a heading.

        Review counterexample E1: stripping it deleted the word ``X`` from a real
        sentence. A heading command preceded by ``{`` or ``|`` is displayed text.
        """
        main = (
            "\\documentclass{article}\n\\title{Displayed Command Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            "\\section{Introduction}\n"
            "DISPLAY_CANARY We write \\texttt{\\subsection{X}} as an example of the syntax.\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("DISPLAY_CANARY We write X as an example", record["introduction"])

    def test_removing_a_heading_does_not_glue_prose_together(self):
        r"""A stripped heading must leave a separator behind.

        Review counterexample E2: ``clause.\subsection{Child title}Next clause``
        came back as ``clause.Next clause`` — two sentences merged into one word.
        """
        main = (
            "\\documentclass{article}\n\\title{Gluing Paper}\n"
            "\\begin{document}\n\\maketitle\n"
            "\\begin{abstract}Abstract text.\\end{abstract}\n"
            "\\section{Introduction}\n"
            "GLUE_CANARY first clause.\\subsection{Child title}SECOND_CANARY second clause.\n"
            f"\\section{{Conclusion}}\nCONCLUSION_CANARY {PROSE}\n"
            "\\end{document}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_project(root, {"main.tex": main})
            record = extract_tex_project(root / "main.tex")
        self.assertIn("first clause.", record["introduction"])
        self.assertNotIn("clause.SECOND_CANARY", record["introduction"])
        self.assertIn("SECOND_CANARY second clause.", record["introduction"])


if __name__ == "__main__":
    unittest.main()
