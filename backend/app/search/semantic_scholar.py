"""Semantic Scholar search provider (Graph API)."""
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

from ..config import settings
from ..llm_config import get_http_proxy
from .base import SearchProvider

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

FIELDS = "title,authors,abstract,url,externalIds,publicationDate,openAccessPdf,paperId"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

TIMEOUT_SECONDS = 30.0

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 2
BACKOFF_DELAYS: Tuple[float, ...] = (1.0, 2.0)
RETRY_AFTER_CAP = 5.0


class SemanticScholarProvider(SearchProvider):
    name = "semantic_scholar"

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        client = self._client or httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=HEADERS,
            proxy=get_http_proxy() or None,
        )
        try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    data = await self._request(client, query, max_results)
                    break
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    retryable = status == 429 or (status is not None and status >= 500)
                    if attempt < MAX_RETRIES and retryable:
                        await asyncio.sleep(self._wait_seconds(exc.response, attempt))
                        continue
                    raise
                except (httpx.TransportError, httpx.TimeoutException):
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(BACKOFF_DELAYS[attempt])
                        continue
                    raise
        finally:
            if self._owns_client:
                await client.aclose()
        papers = data.get("data") or []
        return [self._normalize(paper) for paper in papers]

    async def _request(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> Dict[str, Any]:
        resp = await client.get(
            API_URL,
            params={"query": query, "limit": max_results, "fields": FIELDS},
            headers=self._request_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _wait_seconds(response: Optional[Any], attempt: int) -> float:
        raw = ""
        if response is not None:
            try:
                raw = response.headers.get("Retry-After") or ""
            except AttributeError:
                raw = ""
        if raw:
            try:
                seconds = float(raw.strip())
            except ValueError:
                seconds = None
            if seconds is not None:
                return max(0.0, min(seconds, RETRY_AFTER_CAP))
        return BACKOFF_DELAYS[attempt]

    def _request_headers(self) -> Dict[str, str]:
        headers = dict(HEADERS)
        api_key = settings.semantic_scholar_api_key
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    @staticmethod
    def _looks_like_pdf_url(url: str) -> bool:
        if not url.lower().endswith(".pdf"):
            return False
        return url.startswith("http://") or url.startswith("https://")

    def fallback_url(self, query: str) -> str:
        return f"https://www.semanticscholar.org/search?q={quote(query)}"

    @staticmethod
    def _normalize(paper: Dict[str, Any]) -> Dict[str, Any]:
        external = paper.get("externalIds") or {}
        paper_id = paper.get("paperId", "")
        arxiv_id = external.get("ArXiv") or paper_id or ""
        open_access = paper.get("openAccessPdf") or {}
        # ``openAccessPdf.url`` is not guaranteed to be a PDF file (it may be a
        # landing page likeosti.gov). Only trust it when it looks like a direct
        # PDF link; otherwise prefer the arXiv PDF (if an ArXiv id exists).
        pdf_url = ""
        oa_url = (open_access.get("url") or "").strip()
        if SemanticScholarProvider._looks_like_pdf_url(oa_url):
            pdf_url = oa_url
        if not pdf_url and external.get("ArXiv"):
            pdf_url = f"https://arxiv.org/pdf/{external['ArXiv']}"

        authors = [
            author.get("name", "")
            for author in (paper.get("authors") or [])
            if author.get("name")
        ]
        published = paper.get("publicationDate") or paper.get("year") or ""
        if isinstance(published, int):
            published = str(published)

        url = paper.get("url") or (
            f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""
        )
        return {
            "source": "semantic_scholar",
            "arxiv_id": arxiv_id,
            "title": paper.get("title", ""),
            "authors": authors,
            "abstract": paper.get("abstract") or "",
            "categories": [],
            "published": published,
            "pdf_url": pdf_url,
            "url": url,
        }
