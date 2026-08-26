"""CNKI (知网) search provider (Playwright + saved login state).

CNKI is JS-rendered and protected by anti-bot verification. Searching requires
a saved login state (see ``app.platforms``); without one the provider raises
``LoginRequiredError`` so the aggregator degrades to an external link plus a
"need login" hint. When the saved state has expired the search lands on a
verification page and ``LoginExpiredError`` is raised.

Result parsing is CNKI-specific: each hit is a ``<tr>`` whose ``<td class="name">``
holds the title link, ``<td class="author">`` the author links and
``<td class="date">`` the publication date.
"""
import asyncio
import hashlib
import re
from typing import Any, Dict, List
from urllib.parse import quote

from ..platforms import browser, has_state
from ..platforms import LoginRequiredError
from .base import SearchProvider

SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"

_TD_RE = re.compile(r'<td class="([^"]+)"[^>]*>(.*?)</td>', re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')
_LINK_RE = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)


def _stable_id(url: str) -> str:
    """Derive a filesystem-safe, stable identifier from an article URL."""
    return "cnki-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:24]


class CnkiProvider(SearchProvider):
    name = "cnki"

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        if not has_state(self.name):
            raise LoginRequiredError(self.name)
        html = await asyncio.to_thread(browser.fetch_search_html, self.name, query)
        return self._parse(html, max_results)

    def fallback_url(self, query: str) -> str:
        return f"{SEARCH_URL}?kw={quote(query)}"

    def _parse(self, html: str, max_results: int) -> List[Dict[str, Any]]:
        names: List[str] = []
        authors: List[str] = []
        dates: List[str] = []
        for match in _TD_RE.finditer(html):
            cls = match.group(1)
            content = match.group(2)
            if cls == "name":
                names.append(content)
            elif cls == "author":
                authors.append(content)
            elif cls == "date":
                dates.append(_TAG_RE.sub("", content).strip())

        papers: List[Dict[str, Any]] = []
        for i, cell in enumerate(names):
            if len(papers) >= max_results:
                break
            link = _LINK_RE.search(cell)
            if not link:
                continue
            url = link.group(1)
            title = _TAG_RE.sub("", link.group(2)).strip()
            if not title or "/kcms2/article/abstract" not in url:
                continue

            paper_authors: List[str] = []
            if i < len(authors):
                for am in _LINK_RE.finditer(authors[i]):
                    name = _TAG_RE.sub("", am.group(2)).strip()
                    if name:
                        paper_authors.append(name)

            papers.append(
                {
                    "source": self.name,
                    "arxiv_id": _stable_id(url),
                    "title": title,
                    "authors": paper_authors,
                    "abstract": "",
                    "categories": [],
                    "published": dates[i] if i < len(dates) else "",
                    "pdf_url": "",
                    "url": url,
                }
            )
        return papers
