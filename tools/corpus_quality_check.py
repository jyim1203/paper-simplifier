"""Empirical corpus quality harness for the Paper Simplifier ingestion stage.

Downloads real arXiv sources, runs the parser over them, and reports the
extraction scoreboard (field hit rates, noise counts, section-name coverage,
per-paper warnings). This is the measurement that decides whether the parser
is good enough to scale toward the corpus target, and it is the harness the
pilot metrics in CORPUS_PLAN.md section 9 are read from.

Sources are cached under data/cache/arXiv-<id>/ (gitignored). The JSON report
defaults to reports/generated/ (gitignored).

Usage:
    python tools/corpus_quality_check.py --n 18
    python tools/corpus_quality_check.py --ids 2401.00625v4 2401.00664v7
    python tools/corpus_quality_check.py --n 18 --ids ...
    python tools/corpus_quality_check.py --ids ... --no-download   # use the cache only
    python tools/corpus_quality_check.py --ids ... --clean         # drop cached sources after
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import shutil
import sys
import tarfile
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.paper_simplifier.arxiv_client import ArxivClient, download_source  # noqa: E402
from src.paper_simplifier.latex_extract import extract_tex_project  # noqa: E402
from src.paper_simplifier.paper_extract import select_extraction_input  # noqa: E402

CACHE_ROOT = REPO_ROOT / "data" / "cache"
DEFAULT_REPORT = REPO_ROOT / "reports" / "generated" / "corpus_quality.json"

# TeX artefacts that should never survive into training input.
NOISE_PATTERNS = {
    "backslash_command": re.compile(r"\\[a-zA-Z@]+"),
    "thin_space": re.compile(r"\\[,;!]"),
    "escaped_char": re.compile(r"\\[_%&#]"),
    "brace": re.compile(r"[{}]"),
    "double_backslash": re.compile(r"\\\\"),
    "ampersand": re.compile(r"&"),
    "dollar": re.compile(r"\$"),
    "env_marker": re.compile(r"\\(?:begin|end)\{"),
    # TeX option residue like [t], [H], [width=0.9\linewidth]; not prose labels
    # such as "[Model]" which some papers use legitimately.
    "option_bracket": re.compile(r"\[(?:[a-zA-Z]+=[^\]]*|[bhtH!p])\]"),
}

# Style-diverse fallback used when the arXiv API is rate-limiting.
FALLBACK_IDS = [
    "1706.03762", "1810.04805", "2106.09685", "2210.03629",
    "2312.00752", "2310.06825", "2501.12948", "2404.19756",
    "2212.10496", "2305.18290",
]


def safe_extract(data: bytes, dest: Path) -> str:
    """Extract an arXiv source payload: tarball, single gzipped .tex, or PDF."""
    dest.mkdir(parents=True, exist_ok=True)
    if data[:4] == b"%PDF":
        raise ValueError("pdf_only_submission")
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            tar.extractall(dest, members=members, filter="data")
        return f"tar({len(members)} files)"
    except tarfile.TarError:
        pass
    try:
        (dest / "main.tex").write_bytes(gzip.decompress(data))
        return "gzip_single_tex"
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"unrecognised source payload: {exc}") from exc


def noise_summary(text: str) -> dict[str, int]:
    counts = {}
    for label, pattern in NOISE_PATTERNS.items():
        found = pattern.findall(text)
        if found:
            counts[label] = len(found)
    return counts


def fetch_ids(client: ArxivClient, n: int) -> list[str]:
    query = f"(cat:cs.CL OR cat:cs.LG) AND submittedDate:[201701010000 TO {time.strftime('%Y%m%d')}2359]"
    for attempt in range(1, 3):
        try:
            records = client.query(query, start=0, max_results=n)
            if records:
                return [r["versioned_id"] for r in records]
        except Exception as exc:  # noqa: BLE001
            print(f"  API attempt {attempt} failed: {type(exc).__name__}: {exc}")
            time.sleep(30)
    print("  arXiv API unavailable; using the built-in fallback ID list")
    return FALLBACK_IDS[:n]


def check_one(vid: str, *, use_cache: bool) -> dict:
    row: dict = {"id": vid}
    workdir = CACHE_ROOT / f"arXiv-{vid}"
    src = workdir / "src"
    # Support the flat layout too: a source manually unpacked straight into
    # data/cache/arXiv-<id>/ with the .tex files at the top level.
    if not src.is_dir() and any(workdir.glob("*.tex")):
        src = workdir
    cached = src.is_dir()
    if use_cache and not cached:
        row["error"] = "not_cached"
        return row

    if not cached:
        archive = workdir / "source.tar"
        if archive.is_file():
            archive.unlink()
        for attempt in range(1, 4):
            try:
                download_source(vid, archive, timeout=120.0)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  [{vid}] download attempt {attempt}: {type(exc).__name__}: {exc}")
                time.sleep(10 * attempt)
        else:
            row["error"] = "download_failed"
            return row
        if (workdir / "src").is_dir():
            shutil.rmtree(workdir / "src")
        try:
            row["archive_bytes"] = archive.stat().st_size
            row["archive_kind"] = safe_extract(archive.read_bytes(), workdir / "src")
        except ValueError as exc:
            row["error"] = str(exc)
            return row
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"extract_failed: {exc}"
            return row
        src = workdir / "src"
        time.sleep(1.5)

    try:
        selected = select_extraction_input(src)
    except FileNotFoundError:
        row["error"] = "no_tex_or_pdf_entrypoint"
        return row
    if selected["method"] != "latex_source":
        row["error"] = "pdf_only_submission"
        return row

    row["entrypoint"] = selected["path"].name
    try:
        rec = extract_tex_project(selected["path"])
    except Exception as exc:  # noqa: BLE001
        row["error"] = f"parse_failed: {type(exc).__name__}: {exc}"
        return row

    for key in ("title", "abstract", "introduction", "conclusion"):
        row[f"{key}_len"] = len(rec[key])
    row["intro_source"] = rec["intro_source"]
    row["conclusion_source"] = rec["conclusion_source"]
    row["used_discussion_fallback"] = rec["used_discussion_fallback"]
    row["conclusion_missing"] = rec["conclusion_missing"]
    row["warnings"] = rec["extraction_warnings"]
    row["data_warnings"] = [w for w in rec["extraction_warnings"]
                            if not w.startswith("excluded_visual_input:")]
    combined = "\n".join(rec[k] for k in ("title", "abstract", "introduction", "conclusion"))
    row["noise"] = noise_summary(combined)
    row["noise_total"] = sum(row["noise"].values())
    row["input_chars"] = sum(len(rec[k]) for k in ("title", "abstract", "introduction", "conclusion"))
    return row


def print_scoreboard(rows: list[dict]) -> None:
    ok = [r for r in rows if "error" not in r]
    print("\n" + "=" * 78)
    print(f"SCOREBOARD   attempted={len(rows)}  parsed={len(ok)}  "
          f"failed={len(rows) - len(ok)}")
    print("=" * 78)
    if not ok:
        for r in rows:
            print(f"  {r['id']:<14} {r.get('error')}")
        return

    def pct(pred) -> str:
        return f"{sum(1 for r in ok if pred(r)) / len(ok):.0%}"

    print(f"  title non-empty:          {pct(lambda r: r['title_len'])}")
    print(f"  abstract non-empty:       {pct(lambda r: r['abstract_len'])}")
    print(f"  introduction non-empty:   {pct(lambda r: r['introduction_len'])}")
    print(f"  conclusion or fallback:   {pct(lambda r: r['conclusion_len'])}")
    print(f"  discussion fallback used: {pct(lambda r: r['used_discussion_fallback'])}")
    print(f"  conclusion MISSING flag:  {pct(lambda r: r['conclusion_missing'])}")
    print(f"  records with noise:       {pct(lambda r: r['noise_total'])}")

    lengths = sorted(r["introduction_len"] for r in ok if r["introduction_len"])
    if lengths:
        print(f"  intro chars: min={lengths[0]} median={lengths[len(lengths) // 2]} max={lengths[-1]}")

    agg: dict[str, int] = {}
    for r in ok:
        for label, count in r["noise"].items():
            agg[label] = agg.get(label, 0) + count
    if agg:
        print(f"  noise totals: {dict(sorted(agg.items(), key=lambda kv: -kv[1]))}")

    intro_names = sorted({r["intro_source"] for r in ok if r["intro_source"]})
    conc_names = sorted({r["conclusion_source"] for r in ok if r["conclusion_source"]})
    print(f"  intro section names seen:      {intro_names}")
    print(f"  conclusion section names seen: {conc_names}")

    print("\n  per paper:")
    for r in rows:
        if "error" in r:
            print(f"    {r['id']:<14} ERROR {r['error']}")
            continue
        flags = [k.replace("_len", "").upper() for k in
                 ("title_len", "abstract_len", "introduction_len", "conclusion_len")
                 if not r[k]]
        print(f"    {r['id']:<14} in={r['input_chars']:>6}ch noise={r['noise_total']:>4} "
              f"intro_src={r['intro_source']!r} conc_src={r['conclusion_source']!r} "
              f"{' '.join('MISSING_' + f for f in flags)}")
        if r["data_warnings"]:
            print(f"        warnings: {r['data_warnings'][:5]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=18, help="how many papers to sample from arXiv")
    ap.add_argument("--ids", nargs="*", default=[], help="explicit arXiv IDs (skips the API)")
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--no-download", action="store_true", help="reuse data/cache only")
    ap.add_argument("--clean", action="store_true", help="delete cached sources when done")
    args = ap.parse_args()

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    if args.ids:
        ids = args.ids
    else:
        print("sampling arXiv metadata...")
        ids = fetch_ids(ArxivClient(min_request_interval=3.0, timeout=180.0), args.n)
    print(f"checking {len(ids)} sources\n")

    rows = []
    for vid in ids:
        try:
            row = check_one(vid, use_cache=args.no_download)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            row = {"id": vid, "error": f"harness_error: {exc}"}
        rows.append(row)
        if "error" not in row:
            print(f"  [ok] {vid:<14} noise={row['noise_total']:>4} "
                  f"in={row['input_chars']:>6}ch")
        else:
            print(f"  [--] {vid:<14} {row['error']}")

    print_scoreboard(rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport: {args.report}")

    if args.clean:
        for vid in ids:
            shutil.rmtree(CACHE_ROOT / f"arXiv-{vid}", ignore_errors=True)
        print("cached sources removed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
