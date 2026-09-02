"""SQLite persistence for paper metadata and download status.

Shared infrastructure (schema, connection helper, migrations, row decoding)
lives in this package ``__init__``; table-specific CRUD helpers live in the
submodules and are re-exported here so ``from app import database`` (the
former single-module ``database.py`` import path) keeps working unchanged.
"""
import json
import sqlite3
from typing import Any, Dict

from ..config import settings

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
    metrics TEXT,
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
        ("agent_sessions", "pending", "TEXT"),
        ("papers", "source", "TEXT DEFAULT 'arxiv'"),
        ("papers", "url", "TEXT"),
        ("papers", "error", "TEXT"),
        ("experiment_runs", "metrics", "TEXT"),
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


# Re-export every public CRUD function from the table-specific submodules so
# that ``from . import database`` / ``from .. import database`` callers need
# no changes after the split of the former database.py into this package.
from .agent import (  # noqa: E402,F401
    add_agent_session_usage,
    clear_agent_sessions,
    create_agent_session,
    delete_agent_session,
    get_agent_session,
    list_agent_sessions,
    reset_agent_session_running,
    save_agent_messages,
    set_agent_session_last_usage,
    set_agent_session_pending,
    set_agent_session_running,
    set_agent_session_status,
    update_agent_session_title,
)
from .analyses import (  # noqa: E402,F401
    get_analysis,
    list_analyses,
    set_analysis_progress,
    set_analysis_status,
    upsert_analysis,
)
from .experiments import (  # noqa: E402,F401
    clear_experiments,
    create_experiment_run,
    delete_experiment,
    delete_experiment_run,
    get_experiment,
    get_experiment_run,
    insert_experiment,
    list_experiment_history,
    list_experiment_runs,
    list_experiments,
    reset_stale_experiment_runs,
    set_experiment_progress,
    set_experiment_run_metrics,
    update_experiment,
    update_experiment_run,
)
from .innovations import (  # noqa: E402,F401
    clear_innovations,
    delete_innovation,
    get_innovation,
    insert_innovation,
    list_innovation_history,
    list_innovations,
    set_innovation_progress,
    update_innovation,
)
from .papers import (  # noqa: E402,F401
    delete_paper,
    get_paper,
    list_papers,
    reset_stale_downloads,
    set_download_progress,
    set_status,
    upsert_paper,
)
from .papers_fts import (  # noqa: E402,F401
    build_match_query,
    fts_available,
    rebuild_paper_fts,
    rebuild_paper_fts_if_empty,
    remove_paper_fts,
    reset_probe,
    search_paper_fts,
    update_paper_fts,
)
from .reviews import (  # noqa: E402,F401
    get_review,
    insert_review,
    list_reviews,
    set_review_progress,
    update_review,
)
from .search_history import (  # noqa: E402,F401
    clear_search_history,
    delete_search_history,
    get_search_history,
    list_search_history,
    save_search_history,
)
