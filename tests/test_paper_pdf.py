from app import config, database
from tests.conftest import make_paper


def _store_downloaded_pdf(arxiv_id: str) -> None:
    database.upsert_paper(make_paper(arxiv_id))
    path = config.settings.papers_dir / f"{arxiv_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 fake")
    database.set_status(arxiv_id, "downloaded", str(path))


def test_get_paper_pdf_returns_file(client):
    _store_downloaded_pdf("1706.03762")
    resp = client.get("/api/papers/1706.03762/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content == b"%PDF-1.4 fake"


def test_get_paper_pdf_404_unknown_paper(client):
    resp = client.get("/api/papers/9999.9999/pdf")
    assert resp.status_code == 404


def test_get_paper_pdf_404_missing_file(client):
    database.upsert_paper(make_paper("1706.03762"))
    resp = client.get("/api/papers/1706.03762/pdf")
    assert resp.status_code == 404


def test_get_paper_pdf_with_slash_arxiv_id(client):
    arxiv_id = "gr-qc/9810059"
    _store_downloaded_pdf(arxiv_id)
    resp = client.get(f"/api/papers/{arxiv_id}/pdf")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake"
