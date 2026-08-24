"""arXiv API client.

Queries the arXiv Atom API and parses entries into structured metadata.
Implements a simple request-interval rate limiter and retry with backoff to
comply with arXiv's usage guidelines.
"""
import asyncio
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

ATOM_NS = "{http://www.w3.org/2005/Atom}"

API_URL = "https://export.arxiv.org/api/query"

_VERSION_RE = re.compile(r"v\d+$")


class ArxivClient:
    def __init__(
        self,
        interval: float = 3.0,
        max_retries: int = 3,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.interval = interval
        self.max_retries = max_retries
        self._client = client
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_params(
        self, query: str, max_results: int, category: Optional[str]
    ) -> Dict[str, Any]:
        search_query = f"all:{query}"
        if category:
            search_query = f"{search_query} AND cat:{category}"
        return {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
        }

    async def search(
        self, query: str, max_results: int = 10, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = self._build_params(query, max_results, category)
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                async with self._lock:
                    wait = self.interval - (time.monotonic() - self._last_request)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    client = await self._get_client()
                    resp = await client.get(API_URL, params=params)
                    self._last_request = time.monotonic()

                if resp.status_code == 200:
                    return self._parse(resp.text)
                if resp.status_code in (429, 500, 502, 503):
                    last_error = httpx.HTTPStatusError(
                        f"arXiv API returned {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                else:
                    resp.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        if last_error is not None:
            raise last_error
        return []

    def _parse(self, text: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(text)
        return [self._parse_entry(entry) for entry in root.findall(f"{ATOM_NS}entry")]

    def _parse_entry(self, entry: ET.Element) -> Dict[str, Any]:
        arxiv_id = ""
        id_el = entry.find(f"{ATOM_NS}id")
        if id_el is not None and id_el.text:
            arxiv_id = id_el.text.strip().split("/abs/")[-1]
            arxiv_id = _VERSION_RE.sub("", arxiv_id)

        authors: List[str] = []
        for author in entry.findall(f"{ATOM_NS}author"):
            name_el = author.find(f"{ATOM_NS}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        categories: List[str] = []
        for cat in entry.findall(f"{ATOM_NS}category"):
            term = cat.get("term")
            if term and term not in categories:
                categories.append(term)

        title = self._text(entry, "title")
        abstract = self._text(entry, "summary")
        published = self._text(entry, "published")

        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": categories,
            "published": published,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        }

    @staticmethod
    def _text(entry: ET.Element, tag: str) -> str:
        el = entry.find(f"{ATOM_NS}{tag}")
        return (el.text or "").strip() if el is not None else ""
