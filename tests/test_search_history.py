import pytest

from app import config, database
from app.main import get_arxiv_client
from tests.conftest import make_paper


def test_search_saves_keyword_history(client, fake_arxiv):
    fake_arxiv([make_paper("1"), make_paper("2")])
    resp = client.post("/api/search", json={"query": "attention", "max_results": 10})
    assert resp.status_code == 200

    history = client.get("/api/search/history").json()
    assert len(history) == 1
    assert history[0]["query"] == "attention"
    assert history[0]["mode"] == "keyword"
    assert history[0]["paper_count"] == 2
    assert "papers" not in history[0]


def test_topic_search_saves_history(client, fake_arxiv, monkeypatch):
    async def fake_decompose(topic):
        return "attention mechanism transformer"

    monkeypatch.setattr("app.main.decompose_topic", fake_decompose)
    fake_arxiv([make_paper("1")])

    resp = client.post("/api/search/topic", json={"topic": "transformers", "max_results": 10})
    assert resp.status_code == 200

    history = client.get("/api/search/history").json()
    assert len(history) == 1
    assert history[0]["mode"] == "topic"
    assert history[0]["query"] == "transformers"
    assert history[0]["paper_count"] == 1


def test_history_detail_and_delete(client, fake_arxiv):
    fake_arxiv([make_paper("1"), make_paper("2")])
    client.post("/api/search", json={"query": "q", "max_results": 10})

    history = client.get("/api/search/history").json()
    hid = history[0]["id"]

    detail = client.get(f"/api/search/history/{hid}").json()
    assert detail["query"] == "q"
    assert len(detail["papers"]) == 2
    assert detail["papers"][0]["arxiv_id"] == "1"

    assert client.delete(f"/api/search/history/{hid}").status_code == 200
    assert client.get("/api/search/history").json() == []


def test_history_not_found(client):
    assert client.get("/api/search/history/9999").status_code == 404
    assert client.delete("/api/search/history/9999").status_code == 404


def test_history_clear(client, fake_arxiv):
    fake_arxiv([make_paper("1")])
    client.post("/api/search", json={"query": "a", "max_results": 10})
    client.post("/api/search", json={"query": "b", "max_results": 10})
    assert len(client.get("/api/search/history").json()) == 2

    assert client.delete("/api/search/history").status_code == 200
    assert client.get("/api/search/history").json() == []


def test_history_snapshot_limit(client, fake_arxiv, monkeypatch):
    monkeypatch.setattr(config.settings, "search_history_snapshot_limit", 2)
    fake_arxiv([make_paper(str(i)) for i in range(5)])
    client.post("/api/search", json={"query": "q", "max_results": 10})

    history = client.get("/api/search/history").json()
    assert history[0]["paper_count"] == 2

    detail = client.get(f"/api/search/history/{history[0]['id']}").json()
    assert len(detail["papers"]) == 2


def test_failed_search_not_recorded(client, fake_arxiv):
    class RaisingClient:
        async def search(self, query, max_results=10, category=None):
            raise RuntimeError("boom")

    client.app.dependency_overrides[get_arxiv_client] = lambda: RaisingClient()
    with pytest.raises(RuntimeError):
        client.post("/api/search", json={"query": "x", "max_results": 10})

    assert client.get("/api/search/history").json() == []


def test_history_migration_idempotent(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()
    database.save_search_history("q", "keyword", [make_paper("1")])

    # Running init_db again must be idempotent and keep existing history.
    database.init_db()
    history = database.list_search_history()
    assert len(history) == 1
    assert history[0]["paper_count"] == 1

    detail = database.get_search_history(history[0]["id"])
    assert detail["papers"][0]["arxiv_id"] == "1"
