"""CRUD helpers for the papers table."""
import json
import logging
from typing import Any, Dict, List, Optional

from . import _connect, _row_to_dict
from .papers_fts import remove_paper_fts, update_paper_fts

logger = logging.getLogger(__name__)

PAPER_METADATA_FIELDS = ("title", "abstract", "authors", "categories", "published", "pdf_url")


def _sync_paper_fts(arxiv_id: str) -> None:
    """Keep the FTS row in step with paper writes; never break the write."""
    try:
        update_paper_fts(arxiv_id)
    except Exception:
        logger.warning("FTS 同步失败: %s", arxiv_id, exc_info=True)


def upsert_paper(paper: Dict[str, Any]) -> None:
    """Insert paper metadata, or refresh metadata if the paper already exists.

    The existing download `status` is preserved on conflict so that an already
    downloaded paper is not accidentally reset.
    """
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO papers
                (arxiv_id, title, authors, abstract, categories, published, pdf_url, source, url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(arxiv_id) DO UPDATE SET
                title = excluded.title,
                authors = excluded.authors,
                abstract = excluded.abstract,
                categories = excluded.categories,
                published = excluded.published,
                pdf_url = excluded.pdf_url,
                source = excluded.source,
                url = excluded.url
            """,
            (
                paper["arxiv_id"],
                paper.get("title", ""),
                json.dumps(paper.get("authors", [])),
                paper.get("abstract", ""),
                json.dumps(paper.get("categories", [])),
                paper.get("published", ""),
                paper.get("pdf_url", ""),
                paper.get("source", "arxiv"),
                paper.get("url", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    _sync_paper_fts(paper["arxiv_id"])


def list_papers_missing_metadata(limit: int = 20) -> List[Dict[str, Any]]:
    """Papers with incomplete metadata (spec-039 FR-1), id ascending.

    A paper qualifies when authors, published or categories are missing/empty.
    Non-arxiv sources are included in the candidate pool so callers can count
    them as ``skipped_non_arxiv``.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM papers
            WHERE authors IS NULL OR authors = '' OR authors = '[]'
               OR published IS NULL OR published = ''
               OR categories IS NULL OR categories = '' OR categories = '[]'
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_paper_metadata(arxiv_id: str, fields: Dict[str, Any]) -> bool:
    """Partially update only metadata columns (spec-039 FR-1/NFR-2).

    Download-local state (``local_pdf_path``/``status``/``progress``/``error``)
    is never written here. Returns True when the row exists and at least one
    field actually changed; the FTS index is refreshed on every real write.
    """
    updates: Dict[str, Any] = {}
    for key in PAPER_METADATA_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key in ("authors", "categories"):
            updates[key] = json.dumps(value or [])
        else:
            updates[key] = "" if value is None else str(value)
    if not updates:
        return False
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        if row is None:
            return False
        current = _row_to_dict(row)
        changed: Dict[str, Any] = {}
        for key, value in updates.items():
            old = current.get(key)
            if key in ("authors", "categories"):
                old = json.dumps(old or [])
            elif old is None:
                old = ""
            else:
                old = str(old)
            if old != value:
                changed[key] = value
        if not changed:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in changed)
        conn.execute(
            f"UPDATE papers SET {set_clause} WHERE arxiv_id = ?",
            (*changed.values(), arxiv_id),
        )
        conn.commit()
    finally:
        conn.close()
    _sync_paper_fts(arxiv_id)
    return True


def get_paper(arxiv_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_papers(arxiv_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        if arxiv_ids:
            placeholders = ",".join("?" for _ in arxiv_ids)
            rows = conn.execute(
                f"SELECT * FROM papers WHERE arxiv_id IN ({placeholders}) ORDER BY id DESC",
                arxiv_ids,
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM papers ORDER BY id DESC").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def set_status(
    arxiv_id: str,
    status: str,
    local_pdf_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    conn = _connect()
    try:
        if local_pdf_path is not None:
            conn.execute(
                "UPDATE papers SET status = ?, local_pdf_path = ?, error = ? WHERE arxiv_id = ?",
                (status, local_pdf_path, error, arxiv_id),
            )
        else:
            conn.execute(
                "UPDATE papers SET status = ?, error = ? WHERE arxiv_id = ?",
                (status, error, arxiv_id),
            )
        conn.commit()
    finally:
        conn.close()


def set_download_progress(arxiv_id: str, progress: int) -> None:
    """Update the download progress (0-100) of a paper row."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE papers SET progress = ? WHERE arxiv_id = ?",
            (progress, arxiv_id),
        )
        conn.commit()
    finally:
        conn.close()


def reset_stale_downloads() -> int:
    """Mark residual ``downloading`` papers as failed (startup recovery).

    A fresh process cannot have live downloads, so any ``downloading`` row is
    zombie state left by a crash or kill (spec-035 FR-1). Returns the number
    of rows reset.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE papers SET status = 'failed', error = '应用重启中断' "
            "WHERE status = 'downloading'"
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_paper(arxiv_id: str) -> bool:
    """Delete a paper and its analyses. Returns True if the paper was removed."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM analyses WHERE arxiv_id = ?", (arxiv_id,))
        cur = conn.execute("DELETE FROM papers WHERE arxiv_id = ?", (arxiv_id,))
        conn.commit()
        removed = cur.rowcount > 0
    finally:
        conn.close()
    if removed:
        try:
            remove_paper_fts(arxiv_id)
        except Exception:
            logger.warning("FTS 清理失败: %s", arxiv_id, exc_info=True)
    return removed
