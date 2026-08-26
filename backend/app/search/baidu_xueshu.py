"""Baidu Xueshu (百度学术) search provider (Playwright + saved login state).

Baidu Xueshu is JS-rendered and protected by anti-bot verification. Searching
requires a saved login state (see ``app.platforms``); without one the provider
raises ``LoginRequiredError`` so the aggregator degrades to an external link
plus a "need login" hint. When the saved state has expired the search lands on
a verification page and ``LoginExpiredError`` is raised.

Result parsing is Baidu Xueshu specific: each hit is an ``<h3 class="paper-title">``
block carrying the title/URL, followed by a ``paper-abstract`` block and a
``paper-info`` block with author links (``wd=author%3A%28...%29``) and a
``YYYY年`` publication year.
"""
import asyncio
import hashlib
import re
from typing import Any, Dict, List
from urllib.parse import quote

from ..platforms import browser, has_state
from ..platforms import LoginRequiredError
from .base import SearchProvider

SEARCH_URL = "https://xueshu.baidu.com/s"

_TAG_RE = re.compile(r"<[^>]+>")


def _stable_id(url: str) -> str:
    """Derive a filesystem-safe, stable identifier from an article URL."""
    return "baidu-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:24]

# One result: the title <h3> block plus everything up to the "paper-source" div.
_RESULT_RE = re.compile(
    r'<h3[^>]*class="[^"]*paper-title[^"]*"[^>]*>(.*?)</h3>'
    r'(.*?)<div[^>]*class="paper-source"',
    re.DOTALL,
)
_AUTHOR_RE = re.compile(r'wd=author%3A%28[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
_ABSTRACT_RE = re.compile(r'class="paper-abstract">(.*?)</div>', re.DOTALL)
_INFO_RE = re.compile(r'class="paper-info">(.*?)</div>', re.DOTALL)
_YEAR_RE = re.compile(r'(\d{4})年')
_URL_RE = re.compile(
    r'href="(https://xueshu\.baidu\.com/usercenter/paper/show\?paperid=[^"]*)"'
)


class BaiduXueshuProvider(SearchProvider):
    name = "baidu_xueshu"

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        if not has_state(self.name):
            raise LoginRequiredError(self.name)
        html = await asyncio.to_thread(browser.fetch_search_html, self.name, query)
        return self._parse(html, max_results)

    def fallback_url(self, query: str) -> str:
        return f"{SEARCH_URL}?wd={quote(query)}"

    def _parse(self, html: str, max_results: int) -> List[Dict[str, Any]]:
        papers: List[Dict[str, Any]] = []
        for match in _RESULT_RE.finditer(html):
            if len(papers) >= max_results:
                break
            title_html, rest = match.group(1), match.group(2)

            url_match = _URL_RE.search(title_html)
            if url_match is None:
                continue
            url = url_match.group(1).replace("&amp;", "&")
            title = _TAG_RE.sub("", title_html).strip()
            if not title:
                continue

            abstract = ""
            abs_match = _ABSTRACT_RE.search(rest)
            if abs_match is not None:
                abstract = _TAG_RE.sub("", abs_match.group(1)).strip()

            authors: List[str] = []
            published = ""
            info_match = _INFO_RE.search(rest)
            if info_match is not None:
                info = info_match.group(1)
                for author_cell in _AUTHOR_RE.finditer(info):
                    name = _TAG_RE.sub("", author_cell.group(1)).strip()
                    name = name.rstrip("，,、")
                    if name:
                        authors.append(name)
                year_match = _YEAR_RE.search(info)
                if year_match is not None:
                    published = year_match.group(1)

            papers.append(
                {
                    "source": self.name,
                    "arxiv_id": _stable_id(url),
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "categories": [],
                    "published": published,
                    "pdf_url": "",
                    "url": url,
                }
            )
        return papers
