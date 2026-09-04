"""Paper metadata backfill from arXiv (spec-039 FR-1).

Papers added through platform search or legacy imports often lack
authors/published/categories, which degrades citation exports (spec-038).
This module selects such papers and refetches their metadata from the arXiv
API by id (reusing the client's built-in rate limit and retries), updating
only metadata columns — local download state is never touched (NFR-2). The
FTS index is kept in sync through the standard write hook.
"""
import logging
from typing import Any, Dict, List, Optional

from . import database
from .arxiv import ArxivClient

logger = logging.getLogger(__name__)


async def backfill_metadata(
    limit: int = 20, client: Optional[ArxivClient] = None
) -> Dict[str, int]:
    """Backfill missing metadata for up to ``limit`` papers.

    Returns ``{updated, skipped_non_arxiv, unchanged, failed}``. Idempotent:
    with no candidate papers all counters are zero. Non-arxiv sources are
    skipped; arXiv lookups that miss or error count as ``failed``; hits whose
    metadata equals the stored one count as ``unchanged``.
    """
    counts = {"updated": 0, "skipped_non_arxiv": 0, "unchanged": 0, "failed": 0}
    missing: List[Dict[str, Any]] = database.list_papers_missing_metadata(limit)
    if not missing:
        return counts

    owns_client = client is None
    if owns_client:
        client = ArxivClient()
    try:
        for paper in missing:
            arxiv_id = paper["arxiv_id"]
            if (paper.get("source") or "arxiv") != "arxiv":
                counts["skipped_non_arxiv"] += 1
                continue
            try:
                entries = await client.fetch_by_ids([arxiv_id])
            except Exception:  # noqa: BLE001 - one bad lookup must not stop the run
                logger.warning("元数据补全查询失败: %s", arxiv_id, exc_info=True)
                counts["failed"] += 1
                continue
            if not entries:
                logger.info("元数据补全未命中: %s", arxiv_id)
                counts["failed"] += 1
                continue
            entry = entries[0]
            fields = {
                "title": entry.get("title") or "",
                "abstract": entry.get("abstract") or "",
                "authors": list(entry.get("authors") or []),
                "categories": list(entry.get("categories") or []),
                "published": entry.get("published") or "",
                "pdf_url": entry.get("pdf_url") or "",
            }
            if database.update_paper_metadata(arxiv_id, fields):
                counts["updated"] += 1
                logger.info("元数据已补全: %s", arxiv_id)
            else:
                counts["unchanged"] += 1
    finally:
        if owns_client:
            await client.aclose()
    return counts
