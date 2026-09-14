"""Conservative TeX project extraction for Paper Simplifier.

Design notes (each corresponds to a failure mode observed on real arXiv sources):

- Inputs resolve literally: the requested name, then the name with ``.tex``
  appended. Never ``Path.with_suffix("")``, which turns ``2.1-background`` into
  ``2`` and silently drops a real section file.
- Figure, table, algorithm and math environments are removed wholesale, so
  visual and numeric content cannot leak into narrative prose even when it is
  inlined in a section file instead of living under ``tables/``.
- Section headings are read with a balanced-brace scanner, so optional short
  titles (``\\section[Short]{Long}``) and nested macros in a heading still
  register as boundaries. A heading that fails to register silently merges two
  sections together, which is the most damaging failure in this pipeline.
- Section names are matched on normalized prefixes, so ``Conclusion and Future
  Work`` is a conclusion and not a missing section.
- Every miss is recorded as a warning instead of returning a damaged section
  that looks fine.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Iterator


_INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_ABSTRACT_ENV_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)
_ABSTRACT_CMD_RE = re.compile(r"\\abstract\s*\{")
_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")
_ENV_COMMAND_RE = re.compile(r"\\(?:begin|end)\s*\{[^{}]*\}(?:\s*\[[^\]]*\])?")
_COMMAND_RE = re.compile(r"\\[a-zA-Z@]+\*?")
_BRACE_RE = re.compile(r"[{}]")

# --- section headings -------------------------------------------------------

_SECTION_CMD_RE = re.compile(r"\\section\*?\s*(?:\[[^\]]*\])?\s*\{")
_CHAPTER_CMD_RE = re.compile(r"\\chapter\*?\s*(?:\[[^\]]*\])?\s*\{")
_HEADING_NOISE_RE = re.compile(r"[\s\u00a0]+")
_HEADING_LEAD_NUMBER_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+", re.IGNORECASE)

_INTRO_EXACT = {"introduction", "background", "motivation", "overview"}
_INTRO_PREFIX = ("introduction", "background")
_CONCLUSION_EXACT = {"conclusion", "conclusions", "summary"}
_CONCLUSION_PREFIX = ("conclusion", "concluding")
_DISCUSSION_EXACT = {"discussion", "discussions"}
_DISCUSSION_PREFIX = ("discussion",)

# --- input resolution -------------------------------------------------------

# Directories whose contents are drawings, plots or table cells, not prose.
_VISUAL_DIRS = {
    "figure", "figures", "fig", "figs", "table", "tables", "tab", "tabs",
    "plot", "plots", "diagram", "diagrams", "image", "images", "img",
    "assets", "graphics",
}
# Extensions that are never narrative prose even when \\input-ed.
_NON_NARRATIVE_SUFFIXES = {
    ".bbl", ".bib", ".bst", ".sty", ".cls", ".clo", ".def", ".cfg", ".dtx",
    ".eps", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".csv", ".dat",
    ".json", ".txt", ".toc", ".lof", ".lot", ".out", ".aux", ".log", ".py",
}

# --- environments -----------------------------------------------------------

_BEGIN_RE = re.compile(r"\\begin\s*\{([^{}]*)\}\s*(?:\[[^\]]*\])?")
_END_RE = re.compile(r"\\end\s*\{([^{}]*)\}")

# Environments whose entire body is visual, numeric or code: drop it.
_DROP_ENV_NAMES = {
    "figure", "figure*", "wrapfigure", "sidewaysfigure",
    "table", "table*", "sidewaystable", "longtable", "tabular", "tabular*",
    "tabularx", "tabbing", "array", "matrix", "pmatrix", "bmatrix", "vmatrix",
    "Vmatrix", "smallmatrix", "cases",
    "algorithm", "algorithm*", "algorithmic", "algorithmicx", "algpseudocode",
    "lstlisting", "listing", "verbatim", "verbatim*", "minted", "codeblock",
    "tikzpicture", "pgfpicture", "asy", "pspicture",
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*",
    "displaymath", "split", "subequations", "IEEEeqnarray", "IEEEeqnarray*",
    "thebibliography",
}
_DROP_ENVS = {name.rstrip("*").casefold() for name in _DROP_ENV_NAMES}

# --- command handling -------------------------------------------------------

_DROP_COMMAND_WITH_ARG_RE = re.compile(
    r"\\(?:cite[a-zA-Z]*|label|ref|eqref|autoref|pageref|nameref|"
    r"footnote|footnotemark|footnotetext|thanks|"
    r"bibliography|bibliographystyle|addbibresource|nocite|"
    r"vspace|hspace|vskip|hskip|smallskip|medskip|bigskip|"
    r"index|glossary|hypersetup|geometry|captionsetup|graphicspath|"
    r"usepackage|documentclass|includegraphics|setlength|addtolength)"
    r"\s*(?:\[[^\]]*\])*\s*\{[^{}]*\}"
)
# Citation commands alone may take a second, immediately adjacent mandatory
# argument (``\\citep{key}{postnote}``). This is a separate rule on purpose: a
# second-group allowance on the general drop list above also swallowed the
# prose after ``\\label{key}``, ``\\footnote{key}`` and friends, which silently
# deleted real sentences from corpus abstracts.
_TWO_GROUP_CITE_RE = re.compile(
    r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\])*\s*\{[^{}]*\}(?:\{[^{}]*\})?"
)
_TWO_ARG_UNWRAP_RE = re.compile(
    r"\\(?:href|textcolor|colorbox|texorpdfstring|pdftooltip)"
    r"\s*\{[^{}]*\}\s*\{([^{}]*)\}"
)
# One-argument commands whose argument is prose.
_ONE_ARG_UNWRAP_RE = re.compile(
    r"\\(?:text(?:bf|it|rm|tt|sc|sf|sl|up|md|normal|superscript|subscript)?|"
    r"emph|mbox|hbox|fbox|underline|paragraph|subparagraph|caption|"
    r"textnormal|ensuremath|protect|mbox|mathrm|mathbf|mathit|mathsf|mathtt|"
    r"mathcal|operatorname)\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}"
)
_DEFINITION_RE = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand|DeclareMathOperator|newenvironment)"
    r"\s*\*?\s*\{[^{}]*\}(?:\s*\[[^\]]*\])?(?:\s*\{[^{}]*\})?(?:\s*\{[^{}]*\})?"
)
_PLAIN_DEF_RE = re.compile(r"\\def\s*\\[a-zA-Z@]+\s*(?:#\d\s*)*\{[^{}]*\}")

# Definition commands whose bodies can hold balanced brace groups, e.g.
# ``{\section{Conclusion}}``. _DEFINITION_RE's flat ``[^{}]*`` cannot match
# those, so they are consumed by _strip_definitions with a bracket scanner.
_DEFINITION_HEAD_RE = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand|DeclareMathOperator|newenvironment)\b\s*\*?"
    r"|\\def\b(?=\s*\\[a-zA-Z@])"
)

# Bodies that produce a value or a structure rather than prose. Inlining one
# of these leaves residue once the inner command is dropped
# (``S\\arabic{section}`` becomes a stray "S section"), or reintroduces an
# environment that was already stripped.
_STRUCTURAL_BODY_RE = re.compile(
    r"\\(?:arabic|roman|Roman|alph|Alph|fnsymbol|value|number|begin|end)\b"
)

# --- math and escaping ------------------------------------------------------

_MATH_DISPLAY_RE = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)", re.DOTALL)
_MATH_INLINE_RE = re.compile(r"\$[^$\n]*\$")
_DOLLAR_SENTINEL = "\x00DOLLAR\x00"
_THIN_SPACE_RE = re.compile(r"\\[,;:! ]")
_LINE_BREAK_RE = re.compile(r"\\\\")
_ESCAPED_CHAR_RE = re.compile(r"\\([_%&#])")


def _candidate_path(base: Path, name: str) -> Path | None:
    """Resolve an \\input/\\include target without mangling dotted names."""
    requested = name.strip().replace("\\", "/")
    for candidate in (requested, requested + ".tex"):
        path = base / candidate
        if path.is_file():
            return path
    return None


def _is_visual_asset(requested: str) -> bool:
    """True when a path sits under a figures/tables/plots style directory."""
    parts = [part for part in re.split(r"[\\/]+", requested.strip()) if part not in ("", ".")]
    return any(part.casefold() in _VISUAL_DIRS for part in parts[:-1])


def load_tex_project(entrypoint: str | Path) -> tuple[str, list[str]]:
    """Load the entry TeX file and narrative inputs, excluding visual assets."""
    entry = Path(entrypoint).resolve()
    if not entry.is_file():
        raise FileNotFoundError(entry)
    warnings: list[str] = []
    visited: set[Path] = set()

    def visit(path: Path) -> str:
        path = path.resolve()
        if path in visited:
            warnings.append(f"duplicate_input_skipped:{path.name}")
            return ""
        visited.add(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warnings.append(f"non_utf8_file:{path.name}")
            raw = path.read_text(encoding="latin-1")
        raw = _COMMENT_RE.sub("", raw)
        pieces: list[str] = []
        cursor = 0
        for match in _INPUT_RE.finditer(raw):
            pieces.append(raw[cursor : match.start()])
            requested = match.group(1).strip()
            if _is_visual_asset(requested):
                warnings.append(f"excluded_visual_input:{requested}")
            else:
                child = _candidate_path(path.parent, requested)
                if child is None:
                    warnings.append(f"missing_input:{requested}")
                elif child.suffix.lower() not in ("", ".tex"):
                    warnings.append(f"excluded_non_tex_input:{requested}")
                else:
                    pieces.append(visit(child))
            cursor = match.end()
        pieces.append(raw[cursor:])
        return "\n".join(pieces)

    return visit(entry), warnings


def _balanced_group(text: str, start: int) -> tuple[str, int] | None:
    """Read a brace-balanced group starting at ``text[start] == '{'``.

    Returns ``(inner_text, index_after_closing_brace)`` or None when unbalanced.
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
        index += 1
    return None


def _balanced_argument(text: str, command: str) -> str | None:
    """Extract the argument of the first ``\\command{...}`` in ``text``."""
    match = re.search(r"\\" + re.escape(command) + r"\s*(?:\[[^\]]*\])?\s*\{", text)
    if match is None:
        return None
    group = _balanced_group(text, match.end() - 1)
    return group[0] if group else None


def _find_env_end(text: str, start: int, name: str) -> int:
    """Index of the ``\\end{name}`` matching a ``\\begin{name}``, or -1."""
    depth = 1
    pos = start
    while pos < len(text):
        begin = _BEGIN_RE.search(text, pos)
        end = _END_RE.search(text, pos)
        if end is None:
            return -1
        if begin is not None and begin.start() < end.start():
            if begin.group(1) == name:
                depth += 1
            pos = begin.end()
        else:
            if end.group(1) == name:
                depth -= 1
                if depth == 0:
                    return end.start()
            pos = end.end()
    return -1


def _strip_environments(text: str) -> str:
    """Drop visual/numeric/code environments; keep the body of prose ones."""
    out: list[str] = []
    pos = 0
    while True:
        begin = _BEGIN_RE.search(text, pos)
        if begin is None:
            out.append(text[pos:])
            break
        name = begin.group(1)
        out.append(text[pos : begin.start()])
        end = _find_env_end(text, begin.end(), name)
        if end == -1:
            # Unbalanced markup: skip the marker and keep scanning.
            pos = begin.end()
            continue
        if name.rstrip("*").casefold() not in _DROP_ENVS:
            out.append(_strip_environments(text[begin.end() : end]))
        closing = _END_RE.search(text, end)
        pos = closing.end() if closing else len(text)
    return "".join(out)


def _strip_definitions(text: str) -> str:
    """Remove macro definitions, including bodies that contain nested braces.

    ``\\newcommand{\\x}{\\section{Conclusion}}`` defines a heading command; it is
    not a section. Left in place, its body registers as a phantom section
    boundary and the prose after it is silently attributed to "Conclusion".
    """
    out: list[str] = []
    pos = 0
    while True:
        match = _DEFINITION_HEAD_RE.search(text, pos)
        if match is None:
            out.append(text[pos:])
            break
        out.append(text[pos : match.start()])
        cursor = match.end()
        if match.group(0).lstrip().startswith("\\def"):
            name = re.compile(r"\s*\\[a-zA-Z@]+").match(text, cursor)
            if name is not None:
                cursor = name.end()
            while True:
                marker = re.compile(r"\s*#\d").match(text, cursor)
                if marker is None:
                    break
                cursor = marker.end()
        # Consume the signature and body groups: {\\name}, [n], [default], {body}.
        for _ in range(5):
            whitespace = re.compile(r"[ \t]*").match(text, cursor)
            cursor = whitespace.end()
            if cursor < len(text) and text[cursor] == "[":
                close = text.find("]", cursor)
                if close == -1:
                    break
                cursor = close + 1
                continue
            if cursor < len(text) and text[cursor] == "{":
                group = _balanced_group(text, cursor)
                if group is None:
                    break
                cursor = group[1]
                continue
            break
        pos = cursor
    return "".join(out)


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t":
        index += 1
    return index


def _iter_definitions(text: str) -> Iterator[tuple[str, int, str]]:
    """Yield ``(name, argument_count, body)`` for each macro definition.

    Bodies are read with the bracket scanner, so a nested body such as
    ``\newcommand{\\x}{\\section{Y}}`` is understood as one definition.
    """
    for match in _DEFINITION_HEAD_RE.finditer(text):
        head = match.group(0).lstrip()
        cursor = _skip_whitespace(text, match.end())
        if head.startswith("\\def"):
            name_match = re.compile(r"\\([a-zA-Z@]+)").match(text, cursor)
            if name_match is None:
                continue
            name = name_match.group(1)
            cursor = name_match.end()
            argument_count = 0
            while True:
                marker = re.compile(r"\s*#(\d)").match(text, cursor)
                if marker is None:
                    break
                argument_count = max(argument_count, int(marker.group(1)))
                cursor = marker.end()
        else:
            if cursor < len(text) and text[cursor] == "{":
                group = _balanced_group(text, cursor)
                if group is None:
                    continue
                name_match = re.match(r"\s*\\([a-zA-Z@]+)", group[0])
                if name_match is None:
                    continue
                name = name_match.group(1)
                cursor = group[1]
            else:
                name_match = re.compile(r"\\([a-zA-Z@]+)").match(text, cursor)
                if name_match is None:
                    continue
                name = name_match.group(1)
                cursor = name_match.end()
            argument_count = 0
            cursor = _skip_whitespace(text, cursor)
            if cursor < len(text) and text[cursor] == "[":
                close = text.find("]", cursor)
                if close != -1:
                    declared = text[cursor + 1 : close].strip()
                    if declared.isdigit():
                        argument_count = int(declared)
                    cursor = close + 1
            cursor = _skip_whitespace(text, cursor)
            if cursor < len(text) and text[cursor] == "[":
                close = text.find("]", cursor)
                if close != -1:
                    cursor = close + 1
        cursor = _skip_whitespace(text, cursor)
        if cursor >= len(text) or text[cursor] != "{":
            continue
        body = _balanced_group(text, cursor)
        if body is None:
            continue
        yield name, argument_count, body[0]


def _collect_macros(text: str) -> dict[str, str]:
    """Name -> expansion for definitions safe to inline.

    Only zero-argument definitions are collected: a macro with parameters
    cannot be expanded without parsing its call sites, so it is left alone and
    dropped later like any other unknown command. Real papers define model
    names this way (``\\dsviv`` -> ``DeepSeek-V4``), and deleting those silently
    strips the name from the title, abstract and body.
    """
    macros: dict[str, str] = {}
    for name, argument_count, body in _iter_definitions(text):
        if argument_count or _STRUCTURAL_BODY_RE.search(body):
            continue
        macros[name] = body
    return macros


def _expand_macros(text: str, macros: dict[str, str]) -> str:
    """Inline simple text macros, resolving nested definitions a few levels deep."""
    if not macros:
        return text
    pattern = re.compile(r"\\([a-zA-Z@]+)(\s*\{\})?")

    def replace(match: re.Match[str]) -> str:
        body = macros.get(match.group(1))
        return match.group(0) if body is None else body

    for _ in range(6):
        expanded = pattern.sub(replace, text)
        if expanded == text:
            break
        text = expanded
    return text


def _unwrap_commands(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = _DEFINITION_RE.sub("", text)
        text = _PLAIN_DEF_RE.sub("", text)
        # Must precede the general drop rule, which would otherwise consume
        # only the first group and leave the second as stray prose.
        text = _TWO_GROUP_CITE_RE.sub("", text)
        text = _DROP_COMMAND_WITH_ARG_RE.sub("", text)
        text = _TWO_ARG_UNWRAP_RE.sub(r"\1", text)
        text = _ONE_ARG_UNWRAP_RE.sub(r"\1", text)
    return text


def normalize_tex_text(text: str, macros: dict[str, str] | None = None) -> str:
    """Turn common TeX prose into readable plain text without claiming perfect fidelity."""
    text = _COMMENT_RE.sub("", text)
    # Expand first: a macro body can itself introduce an environment, and that
    # environment still has to be dropped by the strip that follows.
    text = _expand_macros(text, macros or {})
    text = _strip_environments(text)
    # Protect escaped dollars so inline-math pairing cannot swallow prose.
    text = text.replace("\\$", _DOLLAR_SENTINEL)
    text = _MATH_DISPLAY_RE.sub(" ", text)
    text = _MATH_INLINE_RE.sub(" ", text)
    text = text.replace("$", " ").replace(_DOLLAR_SENTINEL, "$")
    # Order matters: the thin-space rule matches backslash followed by a space,
    # so it would eat the second half of a ``\\`` line break and leave a stray
    # backslash behind (visible in titles that break a line).
    text = _LINE_BREAK_RE.sub(" ", text)
    text = _THIN_SPACE_RE.sub(" ", text)
    text = text.replace("~", " ").replace("---", "-").replace("--", "-")
    text = _unwrap_commands(text)
    text = _ENV_COMMAND_RE.sub(" ", text)
    text = _COMMAND_RE.sub(" ", text)
    text = _BRACE_RE.sub("", text)
    text = _ESCAPED_CHAR_RE.sub(r"\1", text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _normalize_heading(title: str) -> str:
    text = _COMMAND_RE.sub(" ", title.casefold())
    text = _BRACE_RE.sub("", text)
    text = _HEADING_LEAD_NUMBER_RE.sub("", text)
    text = _HEADING_NOISE_RE.sub(" ", text).strip()
    return text.strip(" .,:;-–")


def _section_blocks(text: str) -> list[tuple[str, str]]:
    """Split on top-level headings, returning ``(title, body)`` pairs."""
    pattern = _SECTION_CMD_RE if _SECTION_CMD_RE.search(text) else _CHAPTER_CMD_RE
    heads: list[tuple[str, int, int]] = []
    pos = 0
    while True:
        match = pattern.search(text, pos)
        if match is None:
            break
        group = _balanced_group(text, match.end() - 1)
        if group is None:
            pos = match.end()
            continue
        title, body_start = group
        heads.append((title.strip(), match.start(), body_start))
        pos = body_start
    blocks: list[tuple[str, str]] = []
    for index, (title, _start, body_start) in enumerate(heads):
        stop = heads[index + 1][1] if index + 1 < len(heads) else len(text)
        blocks.append((title, text[body_start:stop]))
    return blocks


def _pick(
    blocks: Iterable[tuple[str, str]],
    exact: set[str],
    prefixes: tuple[str, ...],
) -> tuple[str, str] | None:
    """Best heading match: normalized exact first, then normalized prefix."""
    candidates = [(title, _normalize_heading(title), body) for title, body in blocks]
    for title, normalized, body in candidates:
        if normalized in exact:
            return title, body
    for title, normalized, body in candidates:
        if normalized.startswith(prefixes):
            return title, body
    return None


def extract_tex_project(entrypoint: str | Path) -> dict:
    """Extract the project-level fields needed by the pilot dataset."""
    raw, warnings = load_tex_project(entrypoint)
    raw = re.sub(r"\\end\{document\}.*$", "", raw, flags=re.DOTALL)
    # Definitions are removed before section scanning, so the macro table has to
    # be built while they are still present. Environments are stripped first so a
    # \\newcommand shown inside a code listing is not taken for a real definition.
    macros = _collect_macros(_strip_environments(raw))

    title_text = _balanced_argument(raw, "title")
    abstract_env = _ABSTRACT_ENV_RE.search(raw)
    if abstract_env is not None:
        abstract_text = abstract_env.group(1)
    elif _ABSTRACT_CMD_RE.search(raw):
        abstract_text = _balanced_argument(raw, "abstract")
    else:
        abstract_text = None

    # Section boundaries must be read from prose, not from the preamble: a
    # heading inside a macro definition or a code listing otherwise registers
    # as a real section and silently mis-assigns the text that follows it.
    scanned = _strip_definitions(_strip_environments(raw))
    blocks = _section_blocks(scanned)
    introduction = _pick(blocks, _INTRO_EXACT, _INTRO_PREFIX)
    conclusion = _pick(blocks, _CONCLUSION_EXACT, _CONCLUSION_PREFIX)
    discussion = _pick(blocks, _DISCUSSION_EXACT, _DISCUSSION_PREFIX)

    title = normalize_tex_text(title_text, macros) if title_text else ""
    abstract = normalize_tex_text(abstract_text, macros) if abstract_text else ""
    intro_body = normalize_tex_text(introduction[1], macros) if introduction else ""
    conclusion_source = (
        conclusion[0] if conclusion else discussion[0] if discussion else None
    )
    conclusion_body = (
        conclusion[1] if conclusion else discussion[1] if discussion else ""
    )
    conclusion_text = normalize_tex_text(conclusion_body, macros)

    if not title:
        warnings.append("title_not_found")
    if not abstract:
        warnings.append("abstract_not_found")
    if not intro_body:
        warnings.append("introduction_not_found")
    if not conclusion_text:
        warnings.append("conclusion_or_discussion_not_found")

    return {
        "extraction_method": "latex_source",
        "entrypoint": str(Path(entrypoint).name),
        "title": title,
        "abstract": abstract,
        "introduction": intro_body,
        "intro_source": introduction[0] if introduction else None,
        "conclusion": conclusion_text,
        "conclusion_source": conclusion_source,
        "used_discussion_fallback": conclusion is None and discussion is not None,
        "conclusion_missing": not conclusion_text,
        "extraction_warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract paper sections from a TeX project.")
    parser.add_argument("entrypoint", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    record = extract_tex_project(args.entrypoint)
    payload = json.dumps(record, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
