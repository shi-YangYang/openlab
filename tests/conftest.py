import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import config  # noqa: E402
from app.main import app, get_arxiv_client  # noqa: E402


class FakeArxivClient:
    def __init__(self, papers):
        self.papers = papers
        self.queries = []

    async def search(self, query, max_results=10, category=None):
        self.queries.append((query, max_results, category))
        return self.papers


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    papers_dir = data_dir / "papers"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", papers_dir)
    monkeypatch.setattr(config.settings, "uploads_dir", data_dir / "uploads")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    monkeypatch.setattr(config.settings, "arxiv_request_interval", 0.0)
    monkeypatch.setattr(config.settings, "download_retry_delay", 0.0)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fake_arxiv(client):
    def _set(papers):
        fake = FakeArxivClient(papers)
        client.app.dependency_overrides[get_arxiv_client] = lambda: fake
        return fake

    yield _set
    client.app.dependency_overrides.clear()


def make_paper(arxiv_id, title="Title", published="2024-05-01T17:59:59Z",
               categories=None, authors=None):
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors or ["Alice", "Bob"],
        "abstract": "Abstract of " + arxiv_id,
        "categories": categories or ["cs.AI"],
        "published": published,
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
    }
