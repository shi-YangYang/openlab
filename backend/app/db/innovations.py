"""CRUD helpers for the innovations table."""
import json
from typing import Any, Dict, List, Optional

from . import _connect


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
