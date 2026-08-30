"""CRUD helpers for the analyses table."""
import json
import sqlite3
from typing import Any, Dict, List, Optional

from . import _connect


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
