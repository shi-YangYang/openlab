"""CRUD helpers for the reviews table."""
import json
from typing import Any, Dict, List, Optional

from . import _connect


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
