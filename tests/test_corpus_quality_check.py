"""Tests for the corpus quality harness (tools/corpus_quality_check.py).

The harness decides whether the parser is good enough to scale, so a
mislabeled row is a wrong measurement, not a cosmetic bug.
"""

import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import corpus_quality_check  # noqa: E402

PROSE = "This is a sufficiently long body of prose for the section. " * 6

PDF_PAYLOAD = b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
TEX_DOC = (
    "\\documentclass{article}\n"
    "\\title{A Cached Paper}\n"
    "\\begin{document}\n\\maketitle\n"
    "\\begin{abstract}Abstract text.\\end{abstract}\n"
    f"\\section{{Introduction}}\n{PROSE}\n"
    f"\\section{{Conclusion}}\n{PROSE}\n"
    "\\end{document}\n"
)


def _tar_bytes(members: dict[str, str]) -> bytes:
    """Build a real tar payload from ``{member_name: text}``."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, text in members.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


# A real TeX tarball whose first member happens to be named ``%PDF_...``. A tar
# stores the first member's NAME at offset 0, so ``data[:4] == b"%PDF"`` is true
# for this file even though it is not a PDF.
PDF_NAMED_TAR = _tar_bytes({"%PDF_weird.tex": "%PDF-1.5\n", "main.tex": TEX_DOC})


class SafeExtractTests(unittest.TestCase):
    def test_pdf_only_payload_leaves_no_src_tree(self):
        """A PDF-only submission must not create the directory it will never fill.

        The old order (mkdir, then the ``%PDF`` check) left an empty ``src/``.
        A later ``--no-download`` run then saw ``src/`` and reported
        ``no_tex_or_pdf_entrypoint`` instead of ``pdf_only_submission``, which
        silently mislabels PDF-only papers as parser failures.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "arXiv-9999.00001" / "src"
            with self.assertRaises(ValueError):
                corpus_quality_check.safe_extract(PDF_PAYLOAD, dest)
            self.assertFalse(dest.exists())

    def test_tar_payload_still_extracts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "src"
            kind = corpus_quality_check.safe_extract(_tar_bytes({"main.tex": TEX_DOC}), dest)
            self.assertTrue(kind.startswith("tar("))
            self.assertTrue((dest / "main.tex").is_file())

    def test_tar_whose_first_member_is_named_pdf_still_extracts(self):
        r"""A tar's first bytes are its first member's NAME, so ``%PDF`` can lie.

        Magic-byte sniffing before the tar attempt called this TeX tarball a
        PDF-only submission, so a real paper would be dropped permanently.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "src"
            kind = corpus_quality_check.safe_extract(PDF_NAMED_TAR, dest)
            self.assertTrue(kind.startswith("tar("))
            self.assertTrue((dest / "main.tex").is_file())

    def test_empty_payload_is_rejected_without_leaving_a_src_tree(self):
        """An empty download must not become an error-free row with empty fields."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "src"
            with self.assertRaises(ValueError) as caught:
                corpus_quality_check.safe_extract(b"", dest)
            self.assertEqual(str(caught.exception), "empty_source_payload")
            self.assertFalse(dest.exists())


class CheckOneLabellingTests(unittest.TestCase):
    """``check_one`` must label a PDF-only cache honestly."""

    def _cache_with(self, temp_dir, *, archive=None, src_files=None, empty_src=False,
                    workdir_files=None):
        cache = Path(temp_dir)
        workdir = cache / "arXiv-9999.00001"
        workdir.mkdir(parents=True)
        if archive is not None:
            (workdir / "source.tar").write_bytes(archive)
        if empty_src:
            (workdir / "src").mkdir()
        for name, text in (src_files or {}).items():
            path = workdir / "src" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for name, payload in (workdir_files or {}).items():
            (workdir / name).write_bytes(payload)
        return cache

    def test_cached_pdf_only_archive_is_labelled_pdf_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir, archive=PDF_PAYLOAD)
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache):
                row = corpus_quality_check.check_one("9999.00001", use_cache=True)
        self.assertEqual(row["error"], "pdf_only_submission")

    def test_empty_src_left_by_the_old_harness_is_not_treated_as_cached(self):
        """An empty ``src/`` is not a cached source; the archive is the truth."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir, archive=PDF_PAYLOAD, empty_src=True)
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache):
                row = corpus_quality_check.check_one("9999.00001", use_cache=True)
        self.assertEqual(row["error"], "pdf_only_submission")
        self.assertNotEqual(row.get("error"), "no_tex_or_pdf_entrypoint")

    def test_nothing_cached_reports_not_cached(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir)
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache):
                row = corpus_quality_check.check_one("9999.00001", use_cache=True)
        self.assertEqual(row["error"], "not_cached")

    def test_tex_cache_is_parsed_not_skipped(self):
        """Guard against over-correcting: a real cached tree must still parse."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir, src_files={"main.tex": TEX_DOC})
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache):
                row = corpus_quality_check.check_one("9999.00001", use_cache=True)
        self.assertNotIn("error", row)
        self.assertGreater(row["title_len"], 0)
        self.assertGreater(row["introduction_len"], 0)
        self.assertGreater(row["conclusion_len"], 0)

    def test_tar_named_like_a_pdf_is_not_labelled_pdf_only(self):
        r"""Regression: sniffing byte 0 of a tar reads the member NAME, not a type.

        A TeX tarball whose first member is ``%PDF_weird.tex`` was labelled
        ``pdf_only_submission`` and the download skipped, so a real paper was
        dropped on every run instead of being parsed.
        """
        # Cached-only: the archive is on disk but never unpacked by this harness,
        # so "not_cached" is the honest label -- and never "pdf_only_submission".
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir, archive=PDF_NAMED_TAR)
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache):
                row = corpus_quality_check.check_one("9999.00001", use_cache=True)
        self.assertEqual(row.get("error"), "not_cached")

        # Download path: the payload must be extracted and parsed.
        def fake_download(_vid, destination, **_kwargs):
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(PDF_NAMED_TAR)
            return destination

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir)
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache), \
                    mock.patch.object(corpus_quality_check, "download_source", fake_download), \
                    mock.patch.object(corpus_quality_check.time, "sleep", lambda *_: None):
                row = corpus_quality_check.check_one("9999.00001", use_cache=False)
        self.assertNotIn("error", row)
        self.assertGreater(row["title_len"], 0)

    def test_loose_pdf_in_the_cache_dir_is_labelled_pdf_only(self):
        """A PDF saved loose in the cache dir is the same PDF-only submission."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir, workdir_files={"paper.pdf": PDF_PAYLOAD})
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache):
                row = corpus_quality_check.check_one("9999.00001", use_cache=True)
        self.assertEqual(row["error"], "pdf_only_submission")

    def test_empty_download_does_not_become_a_parsed_row(self):
        """A 0-byte archive used to extract to an empty main.tex and 'parse'.

        That row had no error key and four empty fields, so it inflated the
        parsed count and depressed every non-empty percentage.
        """
        def fake_download(_vid, destination, **_kwargs):
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"")
            return destination

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = self._cache_with(temp_dir)
            with mock.patch.object(corpus_quality_check, "CACHE_ROOT", cache), \
                    mock.patch.object(corpus_quality_check, "download_source", fake_download):
                row = corpus_quality_check.check_one("9999.00001", use_cache=False)
        self.assertEqual(row.get("error"), "empty_source_payload")
        self.assertNotIn("title_len", row)


class NoiseDetectionTests(unittest.TestCase):
    def test_single_character_escape_residue_is_detected(self):
        """The harness was blind to residue like ``H\\"older`` and a stray ``\\{``."""
        for text in (r'H\"older smoothness', r"the set \{a, b\}", "trailing \\\n"):
            with self.subTest(text=text):
                self.assertTrue(corpus_quality_check.noise_summary(text))

    def test_noise_patterns_do_not_double_count(self):
        """Each residue class is charged to exactly one pattern.

        ``noise_total`` is a reported scoreboard metric, so a catch-all
        ``stray_backslash`` that also matches ``\\\\`` and ``\\_`` would inflate
        it for text the older patterns already cover.
        """
        cases = [
            ("a \\\\ b", {"double_backslash": 1}),
            (r"x\_y", {"escaped_char": 1}),
            (r'H\"older', {"stray_backslash": 1}),
            ("trailing \\\n", {"stray_backslash": 1}),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(corpus_quality_check.noise_summary(text), expected)


if __name__ == "__main__":
    unittest.main()