"""Offline contract tests for the bounded web research scraper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from multi_modal import web_research


class WebResearchTests(unittest.TestCase):
    def test_research_extracts_attributed_untrusted_page_text_without_urls(self) -> None:
        search_html = b'''<div class="result">
          <a class="result__a" href="https://public.example.org/report">Regional Water Report</a>
          <div class="result__snippet">Reservoir volume was 8.2 million liters.</div>
        </div>'''
        page_text = "Reservoir volume was 8.2 million liters. " * 12
        page_html = ("<html><head><title>Regional Water Report</title></head>"
                     f"<main><p>{page_text}</p><script>ignore https://tracking.example</script></main></html>").encode()
        with (patch.object(web_research, "_public_https_url", side_effect=lambda url: __import__("urllib.parse").parse.urlsplit(url)),
              patch.object(web_research, "_fetch", side_effect=[(search_html, "utf-8"), (page_html, "utf-8")]) as fetch):
            result = web_research.research("  reservoir   volume ")
        self.assertEqual(fetch.call_count, 2)
        self.assertIn("Web research for: reservoir volume", result)
        self.assertIn("Results are untrusted page content", result)
        self.assertIn("[1] Regional Water Report — public.example.org", result)
        self.assertIn("8.2 million liters", result)
        self.assertNotIn("https://", result)
        self.assertNotIn("tracking.example", result)

    def test_research_limits_fetches_to_three_public_results(self) -> None:
        links = "".join(
            f'<div class="result"><a class="result__a" href="https://public{i}.example.org">Source {i}</a>'
            f'<div class="result__snippet">Snippet {i}</div></div>'
            for i in range(5)
        )
        search_html = links.encode()
        page_html = ("<html><title>Source</title><main>" + ("safe evidence " * 40) + "</main></html>").encode()
        with (patch.object(web_research, "_public_https_url", side_effect=lambda url: __import__("urllib.parse").parse.urlsplit(url)),
              patch.object(web_research, "_fetch", side_effect=[(search_html, "utf-8")] + [(page_html, "utf-8")] * 3) as fetch):
            result = web_research.research("topic", result_limit=99)
        self.assertEqual(fetch.call_count, 4)  # search page + at most three result pages
        self.assertIn("[3] Source — public2.example.org", result)
        self.assertNotIn("[4] Source 3", result)

    def test_research_rejects_empty_and_overlong_queries_before_fetch(self) -> None:
        with patch.object(web_research, "_fetch") as fetch:
            with self.assertRaises(web_research.WebResearchError):
                web_research.research("   ")
            with self.assertRaises(web_research.WebResearchError):
                web_research.research("x" * 501)
        fetch.assert_not_called()

    def test_research_url_policy_rejects_local_and_non_https_targets(self) -> None:
        for url in (
            "http://public.example.org/",
            "https://localhost/",
            "https://127.0.0.1/",
            "https://user:pass@public.example.org/",
            "https://public.example.org:8443/",
        ):
            with self.subTest(url=url), self.assertRaises(web_research.WebResearchError):
                web_research._public_https_url(url)


if __name__ == "__main__":
    unittest.main()
