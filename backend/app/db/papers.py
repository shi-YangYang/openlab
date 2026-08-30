"""CRUD helpers for the papers table."""
import json
from typing import Any, Dict, List, Optional

from . import _connect, _row_to_dict


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


def delete_paper(arxiv_id: str) -> bool:
    """Delete a paper and its analyses. Returns True if the paper was removed."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM analyses WHERE arxiv_id = ?", (arxiv_id,))
        cur = conn.execute("DELETE FROM papers WHERE arxiv_id = ?", (arxiv_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
