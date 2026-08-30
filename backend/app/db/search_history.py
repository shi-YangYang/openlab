"""CRUD helpers for the search_history table."""
import json
from typing import Any, Dict, List, Optional

from ..config import settings
from . import _connect


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
