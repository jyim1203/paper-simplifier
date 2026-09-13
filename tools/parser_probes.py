"""Synthetic failure-mode probes for the LaTeX parser.

Each probe builds a throwaway TeX project in a temp dir, runs the extractor,
and checks the behaviour the corpus plan needs. No network, no fixtures on
disk, no project state touched.

These encode the parser conventions real arXiv sources actually use, so a
green run means "the LaTeX parser works" in a falsifiable way. Probes that
disagree with the corpus plan should be fixed in the parser, not relaxed
here, unless the expectation is marked OPINIONATED.

Usage:
    python tools/parser_probes.py          # run all probes, print summary
    python tools/parser_probes.py -v       # plus detail for every probe

Exit code 0 when every probe passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.paper_simplifier.latex_extract import (  # noqa: E402
    extract_tex_project,
    normalize_tex_text,
)
from src.paper_simplifier.paper_extract import select_extraction_input  # noqa: E402

PROSE = "This is a sufficiently long body of prose for the section. " * 6


# --------------------------------------------------------------------------- helpers


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def run(files: dict[str, str]) -> dict:
    """Build a project, run the full extractor, return the record."""
    with tempfile.TemporaryDirectory(prefix="ps_probe_") as td:
        root = Path(td)
        _write(root, files)
        selected = select_extraction_input(root)
        return extract_tex_project(selected["path"])


def select_name(files: dict[str, str]) -> str:
    """Build a project and report which file the selector chooses."""
    with tempfile.TemporaryDirectory(prefix="ps_probe_") as td:
        root = Path(td)
        _write(root, files)
        try:
            return select_extraction_input(root)["path"].name
        except FileNotFoundError:
            return "<none>"


def doc(body: str, *, title: str = "A Test Paper", abstract: str | None = None) -> str:
    """A minimal complete document wrapping `body`."""
    abstract_block = (
        f"\\begin{{abstract}}{abstract}\\end{{abstract}}\n"
        if abstract is not None
        else ""
    )
    title_line = f"\\title{{{title}}}\n" if title is not None else ""
    return (
        "\\documentclass{article}\n"
        f"{title_line}"
        "\\begin{document}\n\\maketitle\n"
        f"{abstract_block}"
        f"{body}\n"
        "\\end{document}\n"
    )


def two_section(section_title: str) -> str:
    return f"\\section{{Introduction}}\n{PROSE}\n\\section{{{section_title}}}\n{PROSE}"


# --------------------------------------------------------------------------- probes


def probe_conclusion_and_future_work() -> tuple[bool, str]:
    """`Conclusion and Future Work` is a normal conclusion."""
    rec = run({"main.tex": doc("\\input{body}"),
               "body.tex": two_section("Conclusion and Future Work")})
    ok = bool(rec["conclusion"]) and not rec["conclusion_missing"]
    return ok, f"conclusion={len(rec['conclusion'])} missing={rec['conclusion_missing']}"


def probe_introduction_and_related_work() -> tuple[bool, str]:
    """`Introduction and Related Work` is a normal introduction."""
    rec = run({"main.tex": doc("\\input{body}"),
               "body.tex": f"\\section{{Introduction and Related Work}}\n{PROSE}\n"
                           f"\\section{{Conclusion}}\n{PROSE}"})
    return bool(rec["introduction"]), f"introduction={len(rec['introduction'])}"


def probe_discussion_conclusion_plural() -> tuple[bool, str]:
    """`Discussions and conclusions` should satisfy the discussion fallback."""
    rec = run({"main.tex": doc("\\input{body}"),
               "body.tex": f"\\section{{Introduction}}\n{PROSE}\n"
                           f"\\section{{Discussions and conclusions}}\n{PROSE}"})
    return bool(rec["conclusion"]), f"conclusion={len(rec['conclusion'])}"


def probe_section_optional_arg() -> tuple[bool, str]:
    """`\\section[Short]{Introduction}` carries an optional short title."""
    rec = run({"main.tex": doc("\\section[Short]{Introduction}\n" + PROSE)})
    return bool(rec["introduction"]), f"introduction={len(rec['introduction'])}"


def probe_section_nested_braces_does_not_absorb() -> tuple[bool, str]:
    """A heading with nested braces must still split the previous section."""
    body = (
        f"\\section{{Introduction}}\n{PROSE}\n"
        f"\\section{{Results for \\textbf{{GPS}}}}\nRESULTS_CANARY {PROSE}\n"
        f"\\section{{Conclusion}}\n{PROSE}"
    )
    rec = run({"main.tex": doc(body)})
    absorbed = "RESULTS_CANARY" in rec["introduction"]
    flagged = any("section" in w or "heading" in w for w in rec["extraction_warnings"])
    return (not absorbed), f"absorbed={absorbed} flagged={flagged}"


def probe_dotted_input_filename() -> tuple[bool, str]:
    """`\\input{2.1-background}` must resolve `2.1-background.tex`."""
    rec = run({
        "main.tex": doc("\\input{2.1-background}"),
        "2.1-background.tex": f"\\section{{Introduction}}\n{PROSE}\n"
                              f"\\section{{Conclusion}}\n{PROSE}",
    })
    missing = [w for w in rec["extraction_warnings"] if w.startswith("missing_input")]
    return (not missing and bool(rec["introduction"])), f"missing={missing}"


def probe_non_tex_input_not_merged() -> tuple[bool, str]:
    """A `.bbl` input is bibliography, not narrative."""
    rec = run({
        "main.tex": doc("\\input{ref.bbl}\n\\input{body}"),
        "ref.bbl": "BIBLIOGRAPHY_CANARY",
        "body.tex": f"\\section{{Introduction}}\n{PROSE}\n\\section{{Conclusion}}\n{PROSE}",
    })
    text = " ".join(str(rec[k]) for k in ("title", "abstract", "introduction", "conclusion"))
    return "BIBLIOGRAPHY_CANARY" not in text, f"leaked={'BIBLIOGRAPHY_CANARY' in text}"


def probe_inline_table_removed() -> tuple[bool, str]:
    """A table inlined in a body file must not become prose."""
    table = ("\\begin{table}\n\\begin{tabular}{lcc}\n\\toprule\n"
             "Model & Acc & F1 \\\\\n\\midrule\n"
             "CANARY_TABLE_ROW & 94.2 & 0.91 \\\\\n\\bottomrule\n"
             "\\end{tabular}\n\\caption{Canary table.}\n\\end{table}\n")
    rec = run({"main.tex": doc(f"\\section{{Introduction}}\n{PROSE}\n{table}\n"
                               f"\\section{{Conclusion}}\n{PROSE}")})
    leaked = "CANARY_TABLE_ROW" in rec["introduction"] or "&" in rec["introduction"]
    return (not leaked), f"leaked_table_rows={leaked}"


def probe_inline_figure_caption_removed() -> tuple[bool, str]:
    """OPINIONATED: a figure caption in a body file is not narrative prose."""
    fig = ("\\begin{figure}\n\\includegraphics[width=0.8\\linewidth]{x.pdf}\n"
           "\\caption{CANARY_CAPTION text.}\n\\end{figure}\n")
    rec = run({"main.tex": doc(f"\\section{{Introduction}}\n{PROSE}\n{fig}\n"
                               f"\\section{{Conclusion}}\n{PROSE}")})
    leaked = "CANARY_CAPTION" in rec["introduction"]
    return (not leaked), f"caption_leaked={leaked}"


def probe_two_arg_cite_removed() -> tuple[bool, str]:
    """natbib two-optional-arg citations must vanish, not degrade to text."""
    rec = run({"main.tex": doc(
        f"\\section{{Introduction}}\n{PROSE} As shown \\cite[e.g., by][p.~3]{{shapiro2021}} before.\n"
        f"\\section{{Conclusion}}\n{PROSE}")})
    intro = rec["introduction"]
    leaked = "shapiro2021" in intro or "[e.g." in intro or "p. 3" in intro
    return (not leaked), f"leaked_citation={leaked}"


def probe_thin_space_and_escapes_removed() -> tuple[bool, str]:
    """`\\,` and `\\_` are spacing/escaping noise, not characters."""
    out = normalize_tex_text(r"10\,000 samples and variable\_name here")
    return ("\\," not in out and "\\_" not in out), repr(out)


def probe_spacing_dimension_removed() -> tuple[bool, str]:
    """`\\vspace{1em}` must not inject its argument into the prose."""
    out = normalize_tex_text(r"before \vspace{1em} after")
    return ("1em" not in out), repr(out)


def probe_entrypoint_reads_00readme() -> tuple[bool, str]:
    """arXiv's 00README.json names the real toplevel; prefer it over guessing."""
    files = {
        "00README.json": '{"sources": [{"usage": "toplevel", "filename": "real_root.tex"}]}',
        "real_root.tex": doc(f"\\section{{Introduction}}\n{PROSE}\n"
                             f"\\section{{Conclusion}}\n{PROSE}", title="Real Title"),
        "main.tex": f"\\section{{Introduction}}\n{PROSE}",
    }
    name = select_name(files)
    rec = run(files)
    return (name == "real_root.tex" and bool(rec["title"])), f"selected={name} title={rec['title']!r}"


def probe_entrypoint_skips_body_only_main() -> tuple[bool, str]:
    """A body-only fragment named main.tex must not shadow the real root."""
    files = {
        "main.tex": f"\\section{{Introduction}}\n{PROSE}\n\\section{{Conclusion}}\n{PROSE}",
        "manuscript.tex": doc(f"\\section{{Introduction}}\n{PROSE}\n"
                              f"\\section{{Conclusion}}\n{PROSE}", title="Manuscript Title"),
    }
    name = select_name(files)
    rec = run(files)
    return (bool(rec["title"])), f"selected={name} title={rec['title']!r}"


def probe_abstract_command_style() -> tuple[bool, str]:
    """Some classes use `\\abstract{...}` instead of the abstract environment."""
    main = ("\\documentclass{article}\n\\title{T}\n\\begin{document}\n\\maketitle\n"
            "\\abstract{The abstract text goes here.}\n"
            f"\\section{{Introduction}}\n{PROSE}\n\\section{{Conclusion}}\n{PROSE}\n"
            "\\end{document}\n")
    rec = run({"main.tex": main})
    return bool(rec["abstract"]), f"abstract={rec['abstract']!r}"


def probe_missing_title_abstract_is_flagged() -> tuple[bool, str]:
    """Empty title/abstract must raise a warning, not pass silently."""
    rec = run({"main.tex": doc(f"\\section{{Introduction}}\n{PROSE}\n"
                               f"\\section{{Conclusion}}\n{PROSE}", title=None)})
    flagged = [w for w in rec["extraction_warnings"] if "title" in w or "abstract" in w]
    return bool(flagged), f"warnings={rec['extraction_warnings']}"


PROBES = [
    probe_conclusion_and_future_work,
    probe_introduction_and_related_work,
    probe_discussion_conclusion_plural,
    probe_section_optional_arg,
    probe_section_nested_braces_does_not_absorb,
    probe_dotted_input_filename,
    probe_non_tex_input_not_merged,
    probe_inline_table_removed,
    probe_inline_figure_caption_removed,
    probe_two_arg_cite_removed,
    probe_thin_space_and_escapes_removed,
    probe_spacing_dimension_removed,
    probe_entrypoint_reads_00readme,
    probe_entrypoint_skips_body_only_main,
    probe_abstract_command_style,
    probe_missing_title_abstract_is_flagged,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print detail for passing probes too")
    args = parser.parse_args()

    failures = []
    for probe in PROBES:
        label = probe.__name__.removeprefix("probe_")
        try:
            ok, detail = probe()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"raised {type(exc).__name__}: {exc}"
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures.append(label)
        if args.verbose or not ok:
            print(f"[{status}] {label}\n         {detail}")

    total = len(PROBES)
    print(f"\n{total - len(failures)}/{total} probes passed")
    if failures:
        print(f"failing: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
