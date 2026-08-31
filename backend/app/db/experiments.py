"""CRUD helpers for the experiments and experiment_runs tables."""
import json
import sqlite3
from typing import Any, Dict, List, Optional

from . import _connect


def insert_experiment(
    source_type: str,
    innovation_id: Optional[int],
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
            INSERT INTO experiments
                (source_type, innovation_id, arxiv_ids, content, language, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_type, innovation_id, json.dumps(arxiv_ids), content, language, status, error),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_experiment(
    experiment_id: int, content: Optional[str], status: str, error: Optional[str] = None
) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE experiments SET content = ?, status = ?, error = ? WHERE id = ?",
            (content, status, error, experiment_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_experiment_progress(experiment_id: int, progress: int) -> None:
    """Update the experiment progress (0-100)."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE experiments SET progress = ? WHERE id = ?",
            (progress, experiment_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_experiment(experiment_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["arxiv_ids"] = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
        data["content"] = json.loads(data["content"]) if data.get("content") else None
        return data
    finally:
        conn.close()


def list_experiments() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM experiments ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["arxiv_ids"] = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
            data["content"] = json.loads(data["content"]) if data.get("content") else None
            result.append(data)
        return result
    finally:
        conn.close()


def list_experiment_history() -> List[Dict[str, Any]]:
    """Return experiment metadata (no full content), newest first."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM experiments ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            arxiv_ids = json.loads(data["arxiv_ids"]) if data.get("arxiv_ids") else []
            content = json.loads(data["content"]) if data.get("content") else None
            data["arxiv_ids"] = arxiv_ids
            data["plan_count"] = len(content) if isinstance(content, list) else 0
            data.pop("content", None)
            result.append(data)
        return result
    finally:
        conn.close()


def delete_experiment(experiment_id: int) -> bool:
    """Delete an experiment record. Returns True if a row was removed."""
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_experiments() -> None:
    """Delete all experiment records."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM experiments")
        conn.commit()
    finally:
        conn.close()


_RUN_UPDATABLE_FIELDS = (
    "status",
    "current_step",
    "pid",
    "error",
    "remote_workdir",
    "launch_command",
    "steps_json",
)


def _run_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["mode"] = data.get("mode") or "manual"
    data["status"] = data.get("status") or "pending"
    data["current_step"] = data.get("current_step") or ""
    data["remote_workdir"] = data.get("remote_workdir") or ""
    data["launch_command"] = data.get("launch_command") or ""
    data["steps_json"] = data.get("steps_json") or ""
    data["error"] = data.get("error") or ""
    return data


def create_experiment_run(
    experiment_id: int,
    server_id: str,
    mode: str = "manual",
    remote_workdir: str = "",
    launch_command: str = "",
    steps_json: str = "",
    log_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert an experiment run row and return it."""
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO experiment_runs
                (experiment_id, server_id, mode, status, current_step,
                 log_path, remote_workdir, pid, launch_command, steps_json)
            VALUES (?, ?, ?, 'pending', '', ?, ?, NULL, ?, ?)
            """,
            (experiment_id, server_id, mode, log_path, remote_workdir,
             launch_command, steps_json),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM experiment_runs WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _run_row_to_dict(row)
    finally:
        conn.close()


def get_experiment_run(run_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM experiment_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return _run_row_to_dict(row) if row else None
    finally:
        conn.close()


def list_experiment_runs() -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM experiment_runs ORDER BY id DESC"
        ).fetchall()
        return [_run_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_experiment_run(run_id: int, **fields: Any) -> Optional[Dict[str, Any]]:
    """Whitelisted update of a run row; ``updated_at`` is always refreshed."""
    allowed = {k: v for k, v in fields.items() if k in _RUN_UPDATABLE_FIELDS}
    if not allowed:
        return get_experiment_run(run_id)
    assignments = ", ".join(f"{key} = ?" for key in allowed)
    values = list(allowed.values())
    conn = _connect()
    try:
        cur = conn.execute(
            f"""
            UPDATE experiment_runs
            SET {assignments},
                updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
            WHERE id = ?
            """,
            [*values, run_id],
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM experiment_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return _run_row_to_dict(row) if row else None
    finally:
        conn.close()


def reset_stale_experiment_runs() -> int:
    """Mark residual ``running``/``paused`` runs as interrupted (startup recovery).

    Live runs are owned by the in-memory ``_drivers`` dict (spec-035 FR-4);
    after a restart none can be alive. ``paused`` runs are reset too because
    resuming needs the driver's in-memory step commands (``self.steps``), which
    do not survive a restart. Returns the number of rows reset.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE experiment_runs SET status = 'interrupted', "
            "error = '应用重启，运行中断' WHERE status IN ('running', 'paused')"
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_experiment_run(run_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM experiment_runs WHERE id = ?", (run_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
