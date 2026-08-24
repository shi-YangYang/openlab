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
    progress INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id TEXT UNIQUE NOT NULL,
    content TEXT,
    language TEXT DEFAULT 'zh',
    status TEXT DEFAULT 'pending',
    error TEXT,
    progress INTEGER DEFAULT 0,
    message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_ids TEXT,
    content TEXT,
    language TEXT DEFAULT 'zh',
    status TEXT DEFAULT 'pending',
    error TEXT,
    progress INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS innovations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_ids TEXT,
    content TEXT,
    language TEXT DEFAULT 'zh',
    status TEXT DEFAULT 'pending',
    error TEXT,
    progress INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    papers TEXT,
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
        conn.executescript(_SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial schema, without data loss."""
    for table, column, ddl in (
        ("analyses", "error", "TEXT"),
        ("reviews", "error", "TEXT"),
        ("papers", "progress", "INTEGER DEFAULT 0"),
        ("analyses", "progress", "INTEGER DEFAULT 0"),
        ("reviews", "progress", "INTEGER DEFAULT 0"),
        ("analyses", "message", "TEXT"),
    ):
        names = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


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


def _analysis_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["content"] = json.loads(data["content"]) if data.get("content") else None
    return data


def set_analysis_status(
    arxiv_id: str, status: str, language: str = "zh", error: Optional[str] = None
) -> None:
    """Create (if missing) or update the status of an analysis row.

    Only ``status``, ``error`` and ``updated_at`` are touched on update so an
    in-progress run never clobbers previously stored content. ``error`` is
    written on every call (``None`` clears any previously recorded reason).
    """
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO analyses (arxiv_id, status, language, error, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(arxiv_id) DO UPDATE SET
                status = excluded.status,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (arxiv_id, status, language, error),
        )
        conn.commit()
    finally:
        conn.close()


def set_analysis_progress(
    arxiv_id: str, progress: int, message: Optional[str] = None
) -> None:
    """Update the analysis progress (0-100) and optional message."""
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE analyses SET progress = ?, message = ?, updated_at = datetime('now')
            WHERE arxiv_id = ?
            """,
            (progress, message, arxiv_id),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_analysis(
    arxiv_id: str,
    content: str,
    language: str = "zh",
    status: str = "done",
    error: Optional[str] = None,
) -> None:
    """Insert or replace the stored analysis for a paper (FR-6 overwrite)."""
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO analyses (arxiv_id, content, language, status, error, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(arxiv_id) DO UPDATE SET
                content = excluded.content,
                language = excluded.language,
                status = excluded.status,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (arxiv_id, content, language, status, error),
        )
        conn.commit()
    finally:
        conn.close()


def get_analysis(arxiv_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM analyses WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return _analysis_row_to_dict(row) if row else None
    finally:
        conn.close()


def list_analyses(arxiv_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        if arxiv_ids:
            placeholders = ",".join("?" for _ in arxiv_ids)
            rows = conn.execute(
                f"SELECT * FROM analyses WHERE arxiv_id IN ({placeholders}) ORDER BY id DESC",
                arxiv_ids,
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM analyses ORDER BY id DESC").fetchall()
        return [_analysis_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def insert_review(
    arxiv_ids: List[str],
    content: Optional[str],
    language: str = "zh",
    status: str = "running",
    error: Optional[str] = None,
) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO reviews (arxiv_ids, content, language, status, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (json.dumps(arxiv_ids), content, language, status, error),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_review(
    review_id: int, content: Optional[str], status: str, error: Optional[str] = None
) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE reviews SET content = ?, status = ?, error = ? WHERE id = ?",
            (content, status, error, review_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_review_progress(review_id: int, progress: int) -> None:
    """Update the review progress (0-100)."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE reviews SET progress = ? WHERE id = ?",
            (progress, review_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_review(review_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["arxiv_ids"] = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
        data["content"] = json.loads(data["content"]) if data.get("content") else None
        return data
    finally:
        conn.close()


def list_reviews() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["arxiv_ids"] = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
            data["content"] = json.loads(data["content"]) if data.get("content") else None
            result.append(data)
        return result
    finally:
        conn.close()


def insert_innovation(
    arxiv_ids: List[str],
    content: Optional[str],
    language: str = "zh",
    status: str = "pending",
    error: Optional[str] = None,
) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO innovations (arxiv_ids, content, language, status, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (json.dumps(arxiv_ids), content, language, status, error),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_innovation(
    innovation_id: int, content: Optional[str], status: str, error: Optional[str] = None
) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE innovations SET content = ?, status = ?, error = ? WHERE id = ?",
            (content, status, error, innovation_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_innovation_progress(innovation_id: int, progress: int) -> None:
    """Update the innovation progress (0-100)."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE innovations SET progress = ? WHERE id = ?",
            (progress, innovation_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_innovation(innovation_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM innovations WHERE id = ?", (innovation_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["arxiv_ids"] = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
        data["content"] = json.loads(data["content"]) if data.get("content") else None
        return data
    finally:
        conn.close()


def list_innovations() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM innovations ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["arxiv_ids"] = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
            data["content"] = json.loads(data["content"]) if data.get("content") else None
            result.append(data)
        return result
    finally:
        conn.close()


def list_innovation_history() -> List[Dict[str, Any]]:
    """Return innovation metadata (no full content), newest first."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM innovations ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            arxiv_ids = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
            content = json.loads(data["content"]) if data.get("content") else None
            data["arxiv_ids"] = arxiv_ids
            data["paper_count"] = len(arxiv_ids)
            data["innovation_count"] = len(content) if isinstance(content, list) else 0
            data.pop("content", None)
            result.append(data)
        return result
    finally:
        conn.close()


def delete_innovation(innovation_id: int) -> bool:
    """Delete an innovation record. Returns True if a row was removed."""
    conn = _connect()
    try:
        cur = conn.execute(
            "DELETE FROM innovations WHERE id = ?", (innovation_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_innovations() -> None:
    """Delete all innovation records."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM innovations")
        conn.commit()
    finally:
        conn.close()


def save_search_history(query: str, mode: str, papers: List[Dict[str, Any]]) -> int:
    """Store a search snapshot (bounded to the configured limit) and return its id."""
    conn = _connect()
    try:
        snapshot = papers[: settings.search_history_snapshot_limit]
        cur = conn.execute(
            "INSERT INTO search_history (query, mode, papers) VALUES (?, ?, ?)",
            (query, mode, json.dumps(snapshot)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_search_history() -> List[Dict[str, Any]]:
    """Return history metadata (no full papers payload), newest first."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM search_history ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            papers = json.loads(data["papers"]) if data.get("papers") else []
            data["paper_count"] = len(papers)
            data.pop("papers", None)
            result.append(data)
        return result
    finally:
        conn.close()


def get_search_history(history_id: int) -> Optional[Dict[str, Any]]:
    """Return a single history snapshot with its full papers list."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM search_history WHERE id = ?", (history_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["papers"] = json.loads(data["papers"]) if data.get("papers") else []
        return data
    finally:
        conn.close()


def delete_search_history(history_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM search_history WHERE id = ?", (history_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_search_history() -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM search_history")
        conn.commit()
    finally:
        conn.close()
