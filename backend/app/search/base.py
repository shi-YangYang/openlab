"""Search provider abstraction.

Every provider normalizes results into a common paper structure so the
aggregator (and downstream API) only has to deal with one shape::

    {
        "source": str,
        "arxiv_id": str,
        "title": str,
        "authors": [str],
        "abstract": str,
        "categories": [str],
        "published": str,
        "pdf_url": str,
        "url": str,
    }
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class SearchProvider(ABC):
    """Interface implemented by each search source."""

    name: str = ""

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Return normalized paper dicts for ``query``."""

    def fallback_url(self, query: str) -> str:
        """External search-page URL used when this provider fails (crawlers)."""
        return ""
