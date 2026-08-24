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
