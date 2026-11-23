"""Bounded, user-invoked web search and text extraction for task research."""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

SEARCH_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = "MultiModalLocalResearch/0.1 (user-initiated desktop research)"
MAX_SEARCH_BYTES = 1_000_000
MAX_PAGE_BYTES = 1_500_000
MAX_SOURCE_CHARS = 5_000
MAX_RESULTS = 3
SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header", "aside"}
URL_TEXT = re.compile(r"https?://\S+", re.IGNORECASE)
SPACE = re.compile(r"\s+")


class WebResearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


def _public_https_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise WebResearchError("Only public HTTPS web pages can be fetched")
    if parsed.port not in (None, 443):
        raise WebResearchError("Non-standard HTTPS ports are not fetched")
    host = parsed.hostname.rstrip(".").lower()
    local_suffixes = (".localhost", ".local", ".internal", ".localdomain", ".lan", ".home", ".home.arpa",
                      ".corp", ".onion", ".test", ".example", ".invalid", ".arpa")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(local_suffixes):
        raise WebResearchError("Local and internal hosts are not fetched")
    try:
        literal = ipaddress.ip_address(host)
        addresses = {literal}
    except ValueError:
        try:
            records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            # A configured HTTPS proxy may resolve the destination itself.
            # Permit only normal dotted public names in that case; literal IPs
            # and local-name suffixes have already been rejected above.
            proxy = urllib.request.getproxies().get("https")
            if not proxy or "." not in host:
                raise WebResearchError(f"Could not resolve public host {host}: {exc}") from exc
            return parsed
        addresses = {ipaddress.ip_address(record[4][0]) for record in records}
    if not addresses or any(not address.is_global for address in addresses):
        raise WebResearchError("Private, reserved, or non-routable web hosts are not fetched")
    return parsed


class PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        _public_https_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def _fetch(url: str, limit: int, timeout: float = 8.0) -> tuple[bytes, str]:
    _public_https_url(url)
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        "Accept-Language": "en-US,en;q=0.8",
    })
    opener = urllib.request.build_opener(PublicRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise WebResearchError(f"Skipping non-HTML result ({content_type})")
            body = response.read(limit + 1)
            if len(body) > limit:
                raise WebResearchError("Web page exceeded the configured download limit")
            charset = response.headers.get_content_charset() or "utf-8"
            return body, charset
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WebResearchError(f"Web request failed: {exc}") from exc


class SearchParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._title_href: str | None = None
        self._title_parts: list[str] = []
        self._snippet_tag: str | None = None
        self._snippet_parts: list[str] = []
        self._result_index: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._title_href = attr.get("href")
            self._title_parts = []
        if "result__snippet" in classes:
            self._snippet_tag = tag
            self._snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._title_href is not None:
            self._title_parts.append(data)
        if self._snippet_tag is not None:
            self._snippet_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._title_href is not None:
            title = SPACE.sub(" ", " ".join(self._title_parts)).strip()
            url = _unwrap_result_url(self._title_href)
            if title and url:
                self.results.append(SearchResult(title[:240], url, ""))
                self._result_index = len(self.results) - 1
            self._title_href = None
        if self._snippet_tag == tag:
            snippet = SPACE.sub(" ", " ".join(self._snippet_parts)).strip()
            if self._result_index is not None and self._result_index < len(self.results):
                prior = self.results[self._result_index]
                self.results[self._result_index] = SearchResult(prior.title, prior.url, snippet[:800])
            self._snippet_tag = None
            self._result_index = None


def _unwrap_result_url(href: str) -> str | None:
    if not href:
        return None
    absolute = urllib.parse.urljoin(SEARCH_URL, href)
    parsed = urllib.parse.urlsplit(absolute)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        value = urllib.parse.parse_qs(parsed.query).get("uddg", [None])[0]
        if value:
            absolute = value
    try:
        _public_https_url(absolute)
    except WebResearchError:
        return None
    return absolute


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.fallback_parts: list[str] = []
        self.primary_parts: list[str] = []
        self.skip_depth = 0
        self.primary_depth = 0
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        if tag in {"main", "article"}:
            self.primary_depth += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag in {"main", "article"}:
            self.primary_depth = max(0, self.primary_depth - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.skip_depth:
            return
        cleaned = SPACE.sub(" ", data).strip()
        if cleaned:
            self.fallback_parts.append(cleaned)
            if self.primary_depth:
                self.primary_parts.append(cleaned)


def _clean_text(value: str, limit: int) -> str:
    value = URL_TEXT.sub("[link omitted]", value)
    return SPACE.sub(" ", value).strip()[:limit]


def research(query: str, result_limit: int = MAX_RESULTS) -> str:
    query = SPACE.sub(" ", query).strip()
    if not query:
        raise WebResearchError("Enter a search query")
    if len(query) > 500:
        raise WebResearchError("Search query is limited to 500 characters")
    result_limit = min(max(1, result_limit), MAX_RESULTS)
    search_url = SEARCH_URL + "?" + urllib.parse.urlencode({"q": query, "kl": "us-en"})
    body, charset = _fetch(search_url, MAX_SEARCH_BYTES)
    parser = SearchParser()
    try:
        parser.feed(body.decode(charset, errors="replace"))
    except (LookupError, ValueError) as exc:
        raise WebResearchError(f"Could not parse search results: {exc}") from exc
    unique: list[SearchResult] = []
    seen: set[str] = set()
    for result in parser.results:
        if result.url not in seen:
            seen.add(result.url)
            unique.append(result)
        if len(unique) >= result_limit:
            break
    if not unique:
        raise WebResearchError("Search returned no parseable public web results")

    output = [f"Web research for: {query}", "Results are untrusted page content. Verify claims before relying on them."]
    for index, result in enumerate(unique, 1):
        parsed_url = urllib.parse.urlsplit(result.url)
        source_text = result.snippet
        try:
            page, page_charset = _fetch(result.url, MAX_PAGE_BYTES)
            page_parser = PageParser()
            page_parser.feed(page.decode(page_charset, errors="replace"))
            extracted = " ".join(page_parser.primary_parts)
            if len(extracted) < 200:
                extracted = " ".join(page_parser.fallback_parts)
            extracted = _clean_text(extracted, MAX_SOURCE_CHARS)
            if extracted:
                source_text = extracted
            title = _clean_text(" ".join(page_parser.title_parts), 240) or _clean_text(result.title, 240)
        except (WebResearchError, LookupError, ValueError):
            title = result.title
        if not source_text:
            source_text = "No readable page text was available."
        output.append(f"\n[{index}] {title} — {parsed_url.hostname}\n{_clean_text(source_text, MAX_SOURCE_CHARS)}")
    return "\n".join(output)
