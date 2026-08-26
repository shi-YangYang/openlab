"""Aggregate multiple search providers concurrently.

Each provider runs independently via ``asyncio.gather``. Failures never break
the whole search: a failing provider contributes a ``fallback`` entry (its
external search-page URL) while the others contribute ``papers``.
"""
import asyncio
from typing import Any, Dict, List, Optional

from ..platforms import LoginExpiredError, LoginRequiredError
from .arxiv import ArxivSearchProvider
from .baidu_xueshu import BaiduXueshuProvider
from .base import SearchProvider
from .cnki import CnkiProvider
from .semantic_scholar import SemanticScholarProvider

ALL_PLATFORMS: tuple = ("arxiv", "semantic_scholar", "baidu_xueshu", "cnki")

_PROVIDER_CLASSES: Dict[str, type] = {
    "arxiv": ArxivSearchProvider,
    "semantic_scholar": SemanticScholarProvider,
    "baidu_xueshu": BaiduXueshuProvider,
    "cnki": CnkiProvider,
}


def build_providers(
    platforms: Optional[List[str]] = None,
    arxiv_client: Any = None,
    category: Optional[str] = None,
) -> List[SearchProvider]:
    """Instantiate the providers for the requested platforms (default: all)."""
    names = list(platforms) if platforms else list(ALL_PLATFORMS)
    providers: List[SearchProvider] = []
    for name in names:
        cls = _PROVIDER_CLASSES.get(name)
        if cls is None:
            continue
        if name == "arxiv":
            providers.append(ArxivSearchProvider(client=arxiv_client, category=category))
        else:
            providers.append(cls())
    return providers


async def search(
    query: str,
    platforms: Optional[List[str]] = None,
    max_results: int = 10,
    arxiv_client: Any = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Search the requested platforms concurrently.

    Returns ``{"papers": [...], "fallbacks": [{"platform", "url",
    "need_login", "expired"}, ...]}``.
    """
    providers = build_providers(platforms, arxiv_client=arxiv_client, category=category)
    results = await asyncio.gather(
        *(provider.search(query, max_results=max_results) for provider in providers),
        return_exceptions=True,
    )

    papers: List[Dict[str, Any]] = []
    fallbacks: List[Dict[str, Any]] = []
    for provider, result in zip(providers, results):
        if isinstance(result, BaseException):
            fallbacks.append(
                {
                    "platform": provider.name,
                    "url": provider.fallback_url(query),
                    "need_login": isinstance(result, LoginRequiredError),
                    "expired": isinstance(result, LoginExpiredError),
                }
            )
        else:
            papers.extend(result or [])

    return {"papers": papers, "fallbacks": fallbacks}
