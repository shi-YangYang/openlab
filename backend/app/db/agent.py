"""CRUD helpers for the agent_sessions table."""
import json
import sqlite3
from typing import Any, Dict, List, Optional

from . import _connect


def _agent_session_item(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "running": bool(row["running"]),
        "status": row["status"] or "",
    }


def create_agent_session(session_id: str, title: str = "") -> Dict[str, Any]:
    """Insert a new agent session row and return its metadata."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO agent_sessions (id, title) VALUES (?, ?)",
            (session_id, title or ""),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return _agent_session_item(row)
    finally:
        conn.close()


def list_agent_sessions() -> List[Dict[str, Any]]:
    """Return agent session metadata (no messages), newest updated first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_sessions ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        return [_agent_session_item(r) for r in rows]
    finally:
        conn.close()


def get_agent_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM agent_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        data = _agent_session_item(row)
        data["messages"] = row["messages"] or "[]"
        data["pending"] = row["pending"]
        data["input_tokens"] = row["input_tokens"] or 0
        data["output_tokens"] = row["output_tokens"] or 0
        data["last_input_tokens"] = row["last_input_tokens"] or 0
        data["last_output_tokens"] = row["last_output_tokens"] or 0
        return data
    finally:
        conn.close()


def update_agent_session_title(session_id: str, title: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET title = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (title or "", session_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return _agent_session_item(row) if row else None
    finally:
        conn.close()


def save_agent_messages(session_id: str, messages: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET messages = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (messages, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_agent_session_usage(
    session_id: str, input_tokens: int, output_tokens: int
) -> None:
    """Accumulate token usage for a session (used after each LLM call)."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET input_tokens = input_tokens + ?, output_tokens = output_tokens + ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (int(input_tokens), int(output_tokens), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_agent_session_last_usage(
    session_id: str, input_tokens: int, output_tokens: int
) -> None:
    """Record the most recent LLM call's token usage for a session."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET last_input_tokens = ?, last_output_tokens = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (int(input_tokens), int(output_tokens), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_agent_session_running(session_id: str, running: bool) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET running = ? WHERE id = ?",
            (1 if running else 0, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_agent_session_status(session_id: str, status: str) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET status = ? WHERE id = ?",
            (status, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_agent_session_pending(
    session_id: str, pending: Optional[Dict[str, Any]]
) -> None:
    """Persist (or clear) the session's pending approval payload (spec-035 FR-2).

    ``pending`` is JSON-serialised as-is; ``None`` clears the column. Called
    whenever the in-memory ``session.pending`` changes so the approval state
    survives a restart.
    """
    raw = json.dumps(pending, ensure_ascii=False) if pending is not None else None
    conn = _connect()
    try:
        conn.execute(
            "UPDATE agent_sessions SET pending = ? WHERE id = ?",
            (raw, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def reset_agent_session_running() -> None:
    """Reset ``running``/``status`` for every session (startup recovery).

    The backend serves runs in a single process, so after a restart no run can
    still be alive; any residual ``running=1`` row is a zombie left behind by a
    crash or kill and would otherwise show a permanent "thinking" state.
    """
    conn = _connect()
    try:
        conn.execute("UPDATE agent_sessions SET running = 0, status = ''")
        conn.commit()
    finally:
        conn.close()


def delete_agent_session(session_id: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM agent_sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_agent_sessions() -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM agent_sessions")
        conn.commit()
    finally:
        conn.close()
