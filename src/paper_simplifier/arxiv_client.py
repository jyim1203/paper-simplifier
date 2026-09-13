"""Small, polite arXiv Atom API client for the Paper Simplifier corpus."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
OPEN_SEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


def _local_id(url: str) -> tuple[str, int | None]:
    raw = url.rstrip("/").split("/abs/")[-1]
    match = re.fullmatch(r"(.+?)(?:v(\d+))?", raw)
    if not match:
        return raw, None
    return match.group(1), int(match.group(2)) if match.group(2) else None


def _date_bound(value: str, end_of_day: bool) -> str:
    """Convert YYYY-MM-DD to arXiv's YYYYMMDDHHMM range format."""
    parsed = datetime.strptime(value, "%Y-%m-%d")
    suffix = "2359" if end_of_day else "0000"
    return parsed.strftime("%Y%m%d") + suffix


def build_category_query(
    categories: Iterable[str], start_date: str, end_date: str
) -> str:
    """Build a date-bounded OR query for arXiv category search."""
    category_terms = [f"cat:{category}" for category in categories]
    if not category_terms:
        raise ValueError("at least one arXiv category is required")
    category_query = " OR ".join(category_terms)
    return (
        f"({category_query}) AND "
        f"submittedDate:[{_date_bound(start_date, False)} TO {_date_bound(end_date, True)}]"
    )


def deduplicate_records(records: Iterable[dict]) -> list[dict]:
    """Keep the highest version of each canonical arXiv ID, in first-seen order."""
    selected: dict[str, dict] = {}
    order: list[str] = []
    for record in records:
        arxiv_id = record["arxiv_id"]
        if arxiv_id not in selected:
            order.append(arxiv_id)
            selected[arxiv_id] = record
            continue
        current_version = selected[arxiv_id].get("version") or 0
        new_version = record.get("version") or 0
        if new_version > current_version:
            selected[arxiv_id] = record
    return [selected[arxiv_id] for arxiv_id in order]


def download_source(
    versioned_id: str,
    destination: str | Path,
    *,
    opener=urllib.request.urlopen,
    user_agent: str = "PaperSimplifier/0.1 (research corpus; contact project owner)",
    timeout: float = 60.0,
) -> Path:
    """Download one source archive; caller controls whether it is later deleted."""
    request = urllib.request.Request(
        f"https://export.arxiv.org/e-print/{versioned_id}",
        headers={"User-Agent": user_agent, "Accept": "application/x-eprint-tar"},
    )
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with opener(request, timeout=timeout) as response:
        destination_path.write_bytes(response.read())
    return destination_path


def parse_feed(payload: bytes) -> list[dict]:
    """Parse an arXiv Atom response into JSON-serializable records."""
    root = ET.fromstring(payload)
    records: list[dict] = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        arxiv_url = _text(entry.find(f"{{{ATOM_NS}}}id"))
        arxiv_id, version = _local_id(arxiv_url)
        authors: list[str] = []
        affiliations: list[str] = []
        for author in entry.findall(f"{{{ATOM_NS}}}author"):
            name = _text(author.find(f"{{{ATOM_NS}}}name"))
            if name:
                authors.append(name)
            affiliation = _text(author.find(f"{{{ARXIV_NS}}}affiliation"))
            if affiliation and affiliation not in affiliations:
                affiliations.append(affiliation)
        links = entry.findall(f"{{{ATOM_NS}}}link")
        pdf_url = next(
            (
                link.attrib["href"]
                for link in links
                if link.attrib.get("type") == "application/pdf"
            ),
            f"https://arxiv.org/pdf/{arxiv_id}",
        )
        records.append(
            {
                "arxiv_id": arxiv_id,
                "version": version,
                "versioned_id": f"{arxiv_id}v{version}" if version else arxiv_id,
                "title": _text(entry.find(f"{{{ATOM_NS}}}title")),
                "abstract": _text(entry.find(f"{{{ATOM_NS}}}summary")),
                "authors": authors,
                "affiliations": affiliations,
                "categories": [
                    category.attrib["term"]
                    for category in entry.findall(f"{{{ATOM_NS}}}category")
                    if category.attrib.get("term")
                ],
                "primary_category": (
                    entry.find(f"{{{ARXIV_NS}}}primary_category").attrib.get("term")
                    if entry.find(f"{{{ARXIV_NS}}}primary_category") is not None
                    else None
                ),
                "published": _text(entry.find(f"{{{ATOM_NS}}}published")),
                "updated": _text(entry.find(f"{{{ATOM_NS}}}updated")),
                "abstract_url": f"https://arxiv.org/abs/{arxiv_id}",
                "source_url": f"https://export.arxiv.org/e-print/{arxiv_id}"
                + (f"v{version}" if version else ""),
                "pdf_url": pdf_url.replace("http://", "https://", 1),
            }
        )
    return records


class ArxivClient:
    """Polite arXiv API client; one process should share one instance."""

    def __init__(
        self,
        *,
        base_url: str = "https://export.arxiv.org/api/query",
        user_agent: str = "PaperSimplifier/0.1 (research corpus; contact project owner)",
        min_request_interval: float = 3.0,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url
        self.user_agent = user_agent
        self.min_request_interval = min_request_interval
        self.timeout = timeout
        self._last_request_at: float | None = None
        self._open = urllib.request.urlopen

    def query(self, search_query: str, *, start: int = 0, max_results: int = 25) -> list[dict]:
        if not 1 <= max_results <= 2000:
            raise ValueError("max_results must be between 1 and 2000")
        params = urllib.parse.urlencode(
            {
                "search_query": search_query,
                "start": start,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "ascending",
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}?{params}",
            headers={"User-Agent": self.user_agent, "Accept": "application/atom+xml"},
        )
        self._wait_if_needed()
        with self._open(request, timeout=self.timeout) as response:
            payload = response.read()
        self._last_request_at = time.monotonic()
        return parse_feed(payload)

    def _wait_if_needed(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.min_request_interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)


def write_jsonl(path: str | Path, records: Iterable[dict]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch an arXiv candidate manifest.")
    parser.add_argument("--categories", nargs="+", default=["cs.AI", "cs.CL", "cs.LG"])
    parser.add_argument("--start-date", default="2017-01-01")
    parser.add_argument("--end-date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--output", default="data/manifests/candidate_papers.jsonl")
    parser.add_argument("--user-agent", default="PaperSimplifier/0.1 (research corpus; contact project owner)")
    args = parser.parse_args()

    query = build_category_query(args.categories, args.start_date, args.end_date)
    records = ArxivClient(user_agent=args.user_agent).query(
        query, start=args.start, max_results=args.max_results
    )
    records = deduplicate_records(records)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    manifest = [
        {
            **record,
            "retrieved_at": retrieved_at,
            "discovery": {
                "query": query,
                "categories": args.categories,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "start": args.start,
                "max_results": args.max_results,
            },
        }
        for record in records
    ]
    write_jsonl(args.output, manifest)
    print(f"wrote {len(manifest)} candidate records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
