"""Conservative TeX project extraction for Paper Simplifier."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


_INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_SECTION_RE = re.compile(r"\\section(\*)?\s*\{([^{}]*)\}")
_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)
_TITLE_RE = re.compile(r"\\title\s*(?:\[[^]]*\])?\s*\{(.*?)\}", re.DOTALL)
_COMMENT_RE = re.compile(r"(?<!\\)%.*?(?=\n|$)")
_MATH_RE = re.compile(
    r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(?:equation\*?|align\*?|gather\*?|\w*matrix)\}.*?\\end\{(?:equation\*?|align\*?|gather\*?|\w*matrix)\}|\$.*?\$",
    re.DOTALL,
)
_DROP_COMMAND_WITH_ARG_RE = re.compile(
    r"\\(?:cite[a-z]*|label|ref|autoref|footnote|footnotemark|bibliography|addbibresource)\s*(?:\[[^]]*\])?\s*\{[^{}]*\}"
)
_UNWRAP_COMMAND_WITH_ARG_RE = re.compile(
    r"\\(?:text(?:bf|it|rm|tt|sc|sf|normalfont)?|emph|mbox|href|url|vspace|hspace|,|;|!|quad|qquad|textsuperscript)\s*(?:\[[^]]*\])?\s*\{([^{}]*)\}"
)
_ENV_COMMAND_RE = re.compile(r"\\(?:begin|end)\s*\{[^{}]*\}")
_COMMAND_RE = re.compile(r"\\[a-zA-Z@]+\*?(?:\s*)")
_BRACE_RE = re.compile(r"[{}]")


def _candidate_path(base: Path, name: str) -> Path | None:
    candidate = (base / name).with_suffix("")
    for suffix in (".tex", ""):
        path = Path(str(candidate) + suffix)
        if path.is_file():
            return path
    return None


def load_tex_project(entrypoint: str | Path) -> tuple[str, list[str]]:
    """Load the entry TeX file and narrative inputs, excluding figures/tables."""
    entry = Path(entrypoint).resolve()
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
            lowered = requested.replace("\\", "/").lower()
            if lowered.startswith(("figures/", "figure/", "tables/", "table/")):
                warnings.append(f"excluded_visual_input:{requested}")
            else:
                child = _candidate_path(path.parent, requested)
                if child is None:
                    warnings.append(f"missing_input:{requested}")
                else:
                    pieces.append(visit(child))
            cursor = match.end()
        pieces.append(raw[cursor:])
        return "\n".join(pieces)

    if not entry.is_file():
        raise FileNotFoundError(entry)
    return visit(entry), warnings


def _unwrap_commands(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = _DROP_COMMAND_WITH_ARG_RE.sub("", text)
        text = _UNWRAP_COMMAND_WITH_ARG_RE.sub(r"\1", text)
    return text


def normalize_tex_text(text: str) -> str:
    """Turn common TeX prose into readable plain text without claiming perfect fidelity."""
    text = _COMMENT_RE.sub("", text)
    text = _MATH_RE.sub(" ", text)
    text = _ENV_COMMAND_RE.sub(" ", text)
    text = text.replace("~", " ").replace("---", "-").replace("--", "-")
    text = _unwrap_commands(text)
    text = _COMMAND_RE.sub(" ", text)
    text = _BRACE_RE.sub("", text)
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\#", "#")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _balanced_argument(text: str, command: str) -> str | None:
    match = re.search(r"\\" + re.escape(command) + r"\s*(?:\[[^]]*\])?\s*\{", text)
    if match is None:
        return None
    start = match.end()
    depth = 1
    index = start
    while index < len(text):
        if text[index] == "{" and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif text[index] == "}" and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start : index]
        index += 1
    return None


def _section_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(_SECTION_RE.finditer(text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(2).strip(), text[match.end() : end]))
    return blocks


def _first_matching(blocks: Iterable[tuple[str, str]], names: Iterable[str]) -> tuple[str, str] | None:
    wanted = {name.casefold() for name in names}
    for title, body in blocks:
        if title.casefold().strip() in wanted:
            return title, body
    return None


def extract_tex_project(entrypoint: str | Path) -> dict:
    """Extract the project-level fields needed by the pilot dataset."""
    raw, warnings = load_tex_project(entrypoint)
    raw = re.sub(r"\\end\{document\}.*$", "", raw, flags=re.DOTALL)
    title_text = _balanced_argument(raw, "title")
    abstract_match = _ABSTRACT_RE.search(raw)
    blocks = _section_blocks(raw)
    introduction = _first_matching(blocks, ("Introduction", "Background"))
    conclusion = _first_matching(blocks, ("Conclusion", "Conclusions"))
    discussion = _first_matching(blocks, ("Discussion", "Discussions"))
    conclusion_source = conclusion[0] if conclusion else discussion[0] if discussion else None
    conclusion_body = conclusion[1] if conclusion else discussion[1] if discussion else ""
    if introduction is None:
        warnings.append("introduction_not_found")
    if conclusion is None and discussion is None:
        warnings.append("conclusion_or_discussion_not_found")
    return {
        "extraction_method": "latex_source",
        "entrypoint": str(Path(entrypoint).name),
        "title": normalize_tex_text(title_text) if title_text else "",
        "abstract": normalize_tex_text(abstract_match.group(1)) if abstract_match else "",
        "introduction": normalize_tex_text(introduction[1]) if introduction else "",
        "intro_source": introduction[0] if introduction else None,
        "conclusion": normalize_tex_text(conclusion_body),
        "conclusion_source": conclusion_source,
        "used_discussion_fallback": conclusion is None and discussion is not None,
        "conclusion_missing": conclusion is None and discussion is None,
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
