import io
import json
import tempfile
import unittest
from pathlib import Path

from src.paper_simplifier.arxiv_client import (
    ArxivClient,
    build_category_query,
    deduplicate_records,
    download_source,
    parse_feed,
    write_jsonl,
)


SAMPLE_FEED = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <updated>2024-02-01T12:00:00Z</updated>
    <published>2024-01-03T10:00:00Z</published>
    <title>  A Useful Model\n  for Papers </title>
    <summary>  We study a useful model.\n </summary>
    <author><name>Ada Lovelace</name><arxiv:affiliation>Analytical Engine Lab</arxiv:affiliation></author>
    <author><name>Alan Turing</name></author>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom" />
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom" />
    <arxiv:primary_category term="cs.AI" />
    <link href="http://arxiv.org/abs/2401.01234v2" rel="alternate" type="text/html" />
    <link href="http://arxiv.org/pdf/2401.01234v2" rel="related" type="application/pdf" />
  </entry>
</feed>
'''


class ArxivClientTests(unittest.TestCase):
    def test_build_category_query_includes_categories_and_date_range(self):
        query = build_category_query(
            ["cs.AI", "cs.LG"], "2017-01-01", "2026-09-12"
        )
        self.assertIn("cat:cs.AI", query)
        self.assertIn("cat:cs.LG", query)
        self.assertIn("submittedDate:[201701010000 TO 202609122359]", query)
        self.assertIn("OR", query)

    def test_parse_feed_normalizes_text_and_preserves_version(self):
        records = parse_feed(SAMPLE_FEED)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["arxiv_id"], "2401.01234")
        self.assertEqual(record["version"], 2)
        self.assertEqual(record["title"], "A Useful Model for Papers")
        self.assertEqual(record["abstract"], "We study a useful model.")
        self.assertEqual(record["authors"], ["Ada Lovelace", "Alan Turing"])
        self.assertEqual(record["affiliations"], ["Analytical Engine Lab"])
        self.assertEqual(record["categories"], ["cs.AI", "cs.LG"])
        self.assertEqual(record["primary_category"], "cs.AI")
        self.assertEqual(record["source_url"], "https://export.arxiv.org/e-print/2401.01234v2")

    def test_deduplicate_records_keeps_latest_version_per_canonical_id(self):
        older = {"arxiv_id": "2401.01234", "version": 1}
        newer = {"arxiv_id": "2401.01234", "version": 2}
        other = {"arxiv_id": "2402.00001", "version": 1}
        self.assertEqual(deduplicate_records([older, newer, other]), [newer, other])

    def test_client_builds_encoded_request_and_uses_user_agent(self):
        client = ArxivClient(min_request_interval=0)
        response = io.BytesIO(SAMPLE_FEED)
        response.status = 200
        response.headers = {"Content-Type": "application/atom+xml"}

        class Opener:
            def __init__(self):
                self.request = None

            def __call__(self, request, timeout):
                self.request = request
                return response

        opener = Opener()
        client._open = opener
        records = client.query("cat:cs.AI", start=0, max_results=1)
        self.assertEqual(records[0]["arxiv_id"], "2401.01234")
        self.assertIn("search_query=cat%3Acs.AI", opener.request.full_url)
        self.assertEqual(opener.request.get_header("User-agent"), client.user_agent)

    def test_download_source_writes_exact_response_bytes(self):
        response = io.BytesIO(b"fake-tarball")
        response.status = 200

        class Opener:
            def __init__(self):
                self.request = None

            def __call__(self, request, timeout):
                self.request = request
                return response

        opener = Opener()
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "source.tar"
            download_source(
                "2401.01234v2", destination, opener=opener, user_agent="test-agent"
            )
            self.assertEqual(destination.read_bytes(), b"fake-tarball")
        self.assertEqual(opener.request.full_url, "https://export.arxiv.org/e-print/2401.01234v2")
        self.assertEqual(opener.request.get_header("User-agent"), "test-agent")

    def test_write_jsonl_creates_parent_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "manifest.jsonl"
            write_jsonl(path, [{"arxiv_id": "2401.01234"}, {"arxiv_id": "2402.00001"}])
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["arxiv_id"] for row in rows], ["2401.01234", "2402.00001"])


if __name__ == "__main__":
    unittest.main()
