"""SQLite persistence for paper metadata and download status."""
import json
import sqlite3
from typing import Any, Dict, List, Optional

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id TEXT UNIQUE NOT NULL,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    categories TEXT,
    published TEXT,
    pdf_url TEXT,
    local_pdf_path TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    settings.ensure_dirs()
    conn = _connect()
    try:
        conn.execute(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["authors"] = json.loads(data["authors"]) if data.get("authors") else []
    data["categories"] = json.loads(data["categories"]) if data.get("categories") else []
    return data


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
                (arxiv_id, title, authors, abstract, categories, published, pdf_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(arxiv_id) DO UPDATE SET
                title = excluded.title,
                authors = excluded.authors,
                abstract = excluded.abstract,
                categories = excluded.categories,
                published = excluded.published,
                pdf_url = excluded.pdf_url
            """,
            (
                paper["arxiv_id"],
                paper.get("title", ""),
                json.dumps(paper.get("authors", [])),
                paper.get("abstract", ""),
                json.dumps(paper.get("categories", [])),
                paper.get("published", ""),
                paper.get("pdf_url", ""),
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


def set_status(arxiv_id: str, status: str, local_pdf_path: Optional[str] = None) -> None:
    conn = _connect()
    try:
        if local_pdf_path is not None:
            conn.execute(
                "UPDATE papers SET status = ?, local_pdf_path = ? WHERE arxiv_id = ?",
                (status, local_pdf_path, arxiv_id),
            )
        else:
            conn.execute(
                "UPDATE papers SET status = ? WHERE arxiv_id = ?",
                (status, arxiv_id),
            )
        conn.commit()
    finally:
        conn.close()
