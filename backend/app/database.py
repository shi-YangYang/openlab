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
    source TEXT DEFAULT 'arxiv',
    url TEXT,
    local_pdf_path TEXT,
    status TEXT DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    error TEXT,
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

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    innovation_id INTEGER,
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

CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT '',
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    messages TEXT DEFAULT '[]',
    running INTEGER DEFAULT 0,
    status TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    last_input_tokens INTEGER DEFAULT 0,
    last_output_tokens INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    server_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'pending',
    current_step TEXT DEFAULT '',
    log_path TEXT,
    remote_workdir TEXT,
    pid INTEGER,
    launch_command TEXT,
    steps_json TEXT,
    error TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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
        ("agent_sessions", "running", "INTEGER DEFAULT 0"),
        ("agent_sessions", "status", "TEXT"),
        ("agent_sessions", "input_tokens", "INTEGER DEFAULT 0"),
        ("agent_sessions", "output_tokens", "INTEGER DEFAULT 0"),
        ("agent_sessions", "last_input_tokens", "INTEGER DEFAULT 0"),
        ("agent_sessions", "last_output_tokens", "INTEGER DEFAULT 0"),
        ("papers", "source", "TEXT DEFAULT 'arxiv'"),
        ("papers", "url", "TEXT"),
        ("papers", "error", "TEXT"),
    ):
        names = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)")


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["authors"] = json.loads(data["authors"]) if data.get("authors") else []
    data["categories"] = json.loads(data["categories"]) if data.get("categories") else []
    data["source"] = data.get("source") or "arxiv"
    data["url"] = data.get("url") or ""
    data["error"] = data.get("error") or ""
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


def delete_experiment_run(run_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM experiment_runs WHERE id = ?", (run_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
