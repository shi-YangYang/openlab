"""FTS5 full-text index over the papers library (spec-037).

A ``papers_fts`` virtual table (trigram tokenizer, so Chinese substring and
case-insensitive English matching work) mirrors each library paper: title +
abstract + a flattened analysis summary. Rows are kept in sync from the
application layer (paper upsert/delete, analysis save) and can be rebuilt in
bulk. Everything degrades gracefully when the runtime SQLite lacks FTS5 or
the trigram tokenizer (NFR-1).
"""
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from . import _connect

logger = logging.getLogger(__name__)

# Cached probe result: None = not probed yet, True/False = FTS5+trigram usable.
_FTS_AVAILABLE: Optional[bool] = None

_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5("
    "paper_id UNINDEXED, title, abstract, analysis_text, source,"
    " tokenize='trigram')"
)


def _ensure(conn: sqlite3.Connection) -> bool:
    """Create the virtual table if needed and report availability.

    The DDL is a cheap no-op once the table exists, so it is re-run on every
    call: the module-level cache only remembers hard unavailability, and a
    fresh database (e.g. tests swapping ``db_path``) self-heals.
    """
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is False:
        return False
    try:
        conn.execute(_DDL)
        _FTS_AVAILABLE = True
        return True
    except sqlite3.OperationalError as exc:
        logger.warning("FTS5/trigram 不可用，库内全文检索降级: %s", exc)
        _FTS_AVAILABLE = False
        return False


def fts_available() -> bool:
    """Whether the runtime SQLite supports FTS5 with the trigram tokenizer."""
    conn = _connect()
    try:
        return _ensure(conn)
    finally:
        conn.close()


def reset_probe() -> None:
    """Forget the cached probe result (used by tests)."""
    global _FTS_AVAILABLE
    _FTS_AVAILABLE = None


def _analysis_text(analysis: Optional[Dict[str, Any]]) -> str:
    """Flatten a stored PaperAnalysis JSON into one searchable string."""
    if not analysis:
        return ""
    content = analysis.get("content")
    if not isinstance(content, dict):
        return ""
    parts: List[str] = []
    summary = content.get("summary") or {}
    for key in ("research_problem", "method", "conclusion"):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    contributions = summary.get("contributions") or []
    if isinstance(contributions, list):
        parts.extend(str(c) for c in contributions if str(c).strip())
    for key in ("keywords", "tags"):
        values = content.get(key) or []
        if isinstance(values, list):
            parts.extend(str(v) for v in values if str(v).strip())
    return " ".join(parts)


def update_paper_fts(arxiv_id: str) -> bool:
    """Refresh the FTS row for one paper (metadata + analysis fallback).

    Returns True when a row was written. No-op when FTS is unavailable or the
    paper itself no longer exists.
    """
    from .analyses import get_analysis
    from .papers import get_paper

    conn = _connect()
    try:
        if not _ensure(conn):
            return False
        paper = conn.execute(
            "SELECT arxiv_id, title, abstract, source FROM papers WHERE arxiv_id = ?",
            (arxiv_id,),
        ).fetchone()
        if paper is None:
            conn.execute("DELETE FROM papers_fts WHERE paper_id = ?", (arxiv_id,))
            conn.commit()
            return False
        try:
            analysis = get_analysis(arxiv_id)
        except Exception:
            analysis = None
        conn.execute("DELETE FROM papers_fts WHERE paper_id = ?", (arxiv_id,))
        conn.execute(
            "INSERT INTO papers_fts (paper_id, title, abstract, analysis_text, source)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                arxiv_id,
                paper["title"] or "",
                paper["abstract"] or "",
                _analysis_text(analysis),
                paper["source"] or "arxiv",
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def remove_paper_fts(arxiv_id: str) -> None:
    """Drop the FTS row for a deleted paper (no-op when FTS is unavailable)."""
    conn = _connect()
    try:
        if not _ensure(conn):
            return
        conn.execute("DELETE FROM papers_fts WHERE paper_id = ?", (arxiv_id,))
        conn.commit()
    finally:
        conn.close()


def rebuild_paper_fts() -> int:
    """Wipe and rebuild the whole index from papers + analyses. Returns count."""
    from .papers import list_papers

    conn = _connect()
    try:
        if not _ensure(conn):
            return 0
    finally:
        conn.close()
    papers = list_papers()
    for paper in papers:
        try:
            update_paper_fts(paper["arxiv_id"])
        except Exception:
            logger.warning("FTS 重建单篇失败: %s", paper.get("arxiv_id"), exc_info=True)
    return len(papers)


def rebuild_paper_fts_if_empty() -> int:
    """Startup backfill (NFR-3): rebuild only when index is empty but library isn't."""
    conn = _connect()
    try:
        if not _ensure(conn):
            return 0
        fts_rows = conn.execute("SELECT COUNT(*) AS n FROM papers_fts").fetchone()["n"]
        paper_rows = conn.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
    finally:
        conn.close()
    if fts_rows > 0 or paper_rows == 0:
        return 0
    return rebuild_paper_fts()


def build_match_query(q: str) -> str:
    """Turn a space-separated query into an FTS5 phrase query (AND semantics).

    Each term becomes a quoted phrase (trigram substring match); terms are
    joined with AND so every term must hit. Embedded double quotes are escaped
    by doubling them.
    """
    terms = [t for t in (w.strip() for w in q.split()) if t]
    return " AND ".join('"' + t.replace('"', '""') + '"' for t in terms)


def _build_like_query(terms: List[str]) -> tuple:
    """Build AND-combined LIKE conditions over the same fields FTS indexes.

    Trigram MATCH cannot match terms shorter than 3 characters, so queries
    containing any such term (mixed-length included, to keep one consistent
    AND engine) fall back to substring LIKE. ``%``/``_``/``\\`` in terms are
    escaped. Returns (where_clause, params).
    """
    fields = ("title", "abstract", "analysis_text", "source")
    parts: List[str] = []
    params: List[str] = []
    for term in terms:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        parts.append(
            "("
            + " OR ".join(
                f"papers_fts.{f} LIKE ? ESCAPE '\\'" for f in fields
            )
            + ")"
        )
        params.extend(f"%{escaped}%" for _ in fields)
    return " AND ".join(parts), params


def search_paper_fts(q: str, limit: int = 50) -> List[Dict[str, Any]]:
    """MATCH + rank-ordered search returning full paper metadata.

    Each hit carries ``matched_in``: which indexed fields contain the terms.
    Queries containing any term shorter than 3 characters (which trigram
    MATCH cannot hit) run as LIKE over the indexed columns instead, with the
    same result shape. Raises nothing; returns [] when FTS is unavailable
    (callers decide whether that should surface as 503 via ``fts_available``).
    """
    terms = [t for t in (w.strip() for w in q.split()) if t]
    if not terms:
        return []
    conn = _connect()
    try:
        if not _ensure(conn):
            return []
        if any(len(t) < 3 for t in terms):
            where, query_params = _build_like_query(terms)
            order = "papers_fts.rowid"
        else:
            where = "papers_fts MATCH ?"
            query_params = [build_match_query(q)]
            order = "papers_fts.rank"
        try:
            rows = conn.execute(
                "SELECT p.*, papers_fts.title AS fts_title,"
                " papers_fts.abstract AS fts_abstract,"
                " papers_fts.analysis_text AS fts_analysis,"
                " papers_fts.source AS fts_source"
                " FROM papers_fts JOIN papers p"
                " ON p.arxiv_id = papers_fts.paper_id"
                f" WHERE {where} ORDER BY {order} LIMIT ?",
                (*query_params, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("FTS 查询失败: %r", q, exc_info=True)
            return []
        from . import _row_to_dict

        lowered = [t.lower() for t in terms]
        results: List[Dict[str, Any]] = []
        for row in rows:
            data = _row_to_dict(row)
            haystack = {
                "title": (row["fts_title"] or "").lower(),
                "abstract": (row["fts_abstract"] or "").lower(),
                "analysis": (row["fts_analysis"] or "").lower(),
                "source": (row["fts_source"] or "").lower(),
            }
            data["matched_in"] = [
                field for field, text in haystack.items() if any(t in text for t in lowered)
            ]
            results.append(data)
        return results
    finally:
        conn.close()
