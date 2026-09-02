"""GET /api/papers must tolerate NULL metadata columns in the papers table.

Regression test: a row whose abstract/published (or title/pdf_url) is NULL
used to trigger a ResponseValidationError and a 500 on the library page.
"""
import sqlite3

from app import config


def test_list_papers_serializes_null_metadata(client):
    with sqlite3.connect(config.settings.db_path) as conn:
        conn.execute(
            "INSERT INTO papers (arxiv_id, title, abstract, published, pdf_url, url) "
            "VALUES ('null-meta.1', NULL, NULL, NULL, NULL, NULL)"
        )

    resp = client.get("/api/papers")

    assert resp.status_code == 200
    row = next(p for p in resp.json() if p["arxiv_id"] == "null-meta.1")
    assert row["title"] is None
    assert row["abstract"] is None
    assert row["published"] is None
    assert row["pdf_url"] is None
