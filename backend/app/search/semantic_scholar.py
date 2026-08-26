"""Semantic Scholar search provider (Graph API)."""
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

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


class SemanticScholarProvider(SearchProvider):
    name = "semantic_scholar"

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        client = self._client or httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, follow_redirects=True, headers=HEADERS
        )
        try:
            resp = await client.get(
                API_URL,
                params={"query": query, "limit": max_results, "fields": FIELDS},
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
        finally:
            if self._owns_client:
                await client.aclose()
        papers = data.get("data") or []
        return [self._normalize(paper) for paper in papers]

    def fallback_url(self, query: str) -> str:
        return f"https://www.semanticscholar.org/search?q={quote(query)}"

    @staticmethod
    def _normalize(paper: Dict[str, Any]) -> Dict[str, Any]:
        external = paper.get("externalIds") or {}
        paper_id = paper.get("paperId", "")
        arxiv_id = external.get("ArXiv") or paper_id or ""
        open_access = paper.get("openAccessPdf") or {}
        pdf_url = open_access.get("url") or ""
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
