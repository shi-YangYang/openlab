"""arXiv search provider wrapping the existing ArxivClient."""
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from ..arxiv import ArxivClient
from .base import SearchProvider


class ArxivSearchProvider(SearchProvider):
    name = "arxiv"

    def __init__(
        self,
        client: Optional[ArxivClient] = None,
        category: Optional[str] = None,
    ) -> None:
        self._client = client
        self._category = category

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        client = self._client or ArxivClient()
        raw = await client.search(
            query, max_results=max_results, category=self._category
        )
        return [self._normalize(paper) for paper in raw]

    def fallback_url(self, query: str) -> str:
        return f"https://arxiv.org/search/?searchtype=all&query={quote(query)}"

    @staticmethod
    def _normalize(paper: Dict[str, Any]) -> Dict[str, Any]:
        arxiv_id = paper.get("arxiv_id", "")
        return {
            "source": "arxiv",
            "arxiv_id": arxiv_id,
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "abstract": paper.get("abstract", ""),
            "categories": paper.get("categories", []),
            "published": paper.get("published", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
        }
