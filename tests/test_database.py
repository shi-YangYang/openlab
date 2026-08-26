import json

from app import config, database
from tests.conftest import make_paper


def test_upsert_and_get_paper(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()

    paper = make_paper("1706.03762")
    database.upsert_paper(paper)

    record = database.get_paper("1706.03762")
    assert record["arxiv_id"] == "1706.03762"
    assert record["authors"] == ["Alice", "Bob"]
    assert record["categories"] == ["cs.AI"]
    assert record["status"] == "pending"

    # Upserting again refreshes metadata but does not reset status.
    database.set_status("1706.03762", "downloaded", "/tmp/x.pdf")
    database.upsert_paper(paper)
    assert database.get_paper("1706.03762")["status"] == "downloaded"


def test_set_status_and_list(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()
    database.upsert_paper(make_paper("1", title="One"))
    database.upsert_paper(make_paper("2", title="Two"))
    database.set_status("1", "downloaded", str(data_dir / "papers" / "1.pdf"))

    all_papers = database.list_papers()
    assert len(all_papers) == 2

    filtered = database.list_papers(["1"])
    assert len(filtered) == 1
    assert filtered[0]["status"] == "downloaded"
    assert filtered[0]["title"] == "One"


def test_no_api_key_column_in_schema(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()
    conn = database._connect()
    try:
        rows = conn.execute("PRAGMA table_info(papers)").fetchall()
    finally:
        conn.close()

    columns = [r["name"] for r in rows]
    assert not any("key" in c.lower() for c in columns)
    # All spec-required columns exist.
    for required in ("id", "arxiv_id", "title", "authors", "abstract",
                     "categories", "published", "pdf_url", "local_pdf_path",
                     "status", "created_at"):
        assert required in columns


def test_migration_adds_error_column_without_data_loss(tmp_path, monkeypatch):
    import sqlite3

    data_dir = tmp_path / "data"
    papers_dir = data_dir / "papers"
    db_path = data_dir / "openlab.db"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", papers_dir)
    monkeypatch.setattr(config.settings, "db_path", db_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT UNIQUE NOT NULL,
            content TEXT,
            language TEXT DEFAULT 'zh',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_ids TEXT,
            content TEXT,
            language TEXT DEFAULT 'zh',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO analyses (arxiv_id, content, language, status)
            VALUES ('1', '{}', 'zh', 'done');
        INSERT INTO reviews (arxiv_ids, content, language, status)
            VALUES ('["1"]', '{}', 'zh', 'done');
        """
    )
    conn.commit()
    conn.close()

    database.init_db()

    conn = database._connect()
    try:
        for table in ("analyses", "reviews"):
            cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            assert "error" in cols
        row = conn.execute("SELECT * FROM analyses WHERE arxiv_id = '1'").fetchone()
        assert row["status"] == "done"
        assert row["content"] == "{}"
        review = conn.execute("SELECT * FROM reviews WHERE id = 1").fetchone()
        assert review["status"] == "done"
        assert review["arxiv_ids"] == '["1"]'
    finally:
        conn.close()


def test_migration_adds_progress_message_columns_without_data_loss(tmp_path, monkeypatch):
    import sqlite3

    data_dir = tmp_path / "data"
    papers_dir = data_dir / "papers"
    db_path = data_dir / "openlab.db"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", papers_dir)
    monkeypatch.setattr(config.settings, "db_path", db_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE papers (
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
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT UNIQUE NOT NULL,
            content TEXT,
            language TEXT DEFAULT 'zh',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_ids TEXT,
            content TEXT,
            language TEXT DEFAULT 'zh',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO papers (arxiv_id, title, status) VALUES ('1', 'Old paper', 'downloaded');
        INSERT INTO analyses (arxiv_id, content, language, status)
            VALUES ('1', '{}', 'zh', 'done');
        INSERT INTO reviews (arxiv_ids, content, language, status)
            VALUES ('["1"]', '{}', 'zh', 'done');
        """
    )
    conn.commit()
    conn.close()

    database.init_db()

    conn = database._connect()
    try:
        papers_cols = [r["name"] for r in conn.execute("PRAGMA table_info(papers)").fetchall()]
        analyses_cols = [r["name"] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()]
        reviews_cols = [r["name"] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()]
        assert "progress" in papers_cols
        assert "progress" in analyses_cols
        assert "message" in analyses_cols
        assert "progress" in reviews_cols

        paper = conn.execute("SELECT * FROM papers WHERE arxiv_id = '1'").fetchone()
        assert paper["status"] == "downloaded"
        assert paper["progress"] == 0
        analysis = conn.execute("SELECT * FROM analyses WHERE arxiv_id = '1'").fetchone()
        assert analysis["status"] == "done"
        assert analysis["progress"] == 0
        review = conn.execute("SELECT * FROM reviews WHERE id = 1").fetchone()
        assert review["status"] == "done"
        assert review["progress"] == 0
    finally:
        conn.close()


def test_source_column_default_and_upsert(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()

    # Default source is "arxiv" when not provided.
    database.upsert_paper(make_paper("1706.03762"))
    record = database.get_paper("1706.03762")
    assert record["source"] == "arxiv"
    assert record["url"] == ""

    # Explicit source/url are persisted.
    database.upsert_paper(
        {
            "arxiv_id": "upload-token",
            "title": "Uploaded",
            "authors": ["A"],
            "abstract": "",
            "categories": [],
            "published": "",
            "pdf_url": "",
            "source": "upload",
            "url": "https://example.com/x",
        }
    )
    record = database.get_paper("upload-token")
    assert record["source"] == "upload"
    assert record["url"] == "https://example.com/x"
