from app import config, downloader
from app.config import Settings, settings
from tests.conftest import make_paper


def test_search_returns_results(client, fake_arxiv):
    fake_arxiv([make_paper("1706.03762"), make_paper("2301.12345", title="Two")])
    resp = client.post("/api/search", json={"query": "attention", "max_results": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["arxiv_id"] == "1706.03762"
    for field in ("title", "authors", "abstract", "categories", "published", "arxiv_id"):
        assert field in data[0]


def test_search_filters_by_category_and_date(client, fake_arxiv):
    fake = fake_arxiv([
        make_paper("1", published="2024-01-01T00:00:00Z"),
        make_paper("2", published="2024-06-01T00:00:00Z"),
    ])
    resp = client.post("/api/search", json={
        "query": "x",
        "max_results": 10,
        "category": "cs.AI",
        "date_from": "2024-03-01",
        "date_to": "2024-12-31",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["arxiv_id"] == "2"
    assert fake.queries[0][2] == "cs.AI"


def test_search_topic_decomposes(client, fake_arxiv, monkeypatch):
    async def fake_decompose(topic):
        return "attention mechanism transformer"

    monkeypatch.setattr("app.main.decompose_topic", fake_decompose)
    fake_arxiv([make_paper("1706.03762")])

    resp = client.post("/api/search/topic", json={"topic": "transformers", "max_results": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "attention mechanism transformer"
    assert len(data["papers"]) == 1


def test_search_topic_without_api_key(client, monkeypatch):
    monkeypatch.setattr("app.llm.get_effective_config", lambda: {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
    })
    resp = client.post("/api/search/topic", json={"topic": "x", "max_results": 10})
    assert resp.status_code == 400


def test_download_and_skip_duplicate(client, monkeypatch):
    calls = {"n": 0}

    async def fake_download_pdf(arxiv_id, pdf_url, client):
        calls["n"] += 1
        settings.papers_dir.mkdir(parents=True, exist_ok=True)
        path = settings.papers_dir / f"{arxiv_id}.pdf"
        path.write_bytes(b"%PDF-1.4 fake")
        return path

    monkeypatch.setattr(downloader, "download_pdf", fake_download_pdf)

    paper = make_paper("1706.03762")
    resp = client.post("/api/download", json={"papers": [paper]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == ["1706.03762"]
    assert data["skipped"] == []

    assert (settings.papers_dir / "1706.03762.pdf").exists()
    records = client.get("/api/papers", params={"arxiv_ids": "1706.03762"}).json()
    assert records[0]["status"] == "downloaded"
    assert records[0]["local_pdf_path"]

    # Duplicate download is skipped.
    resp2 = client.post("/api/download", json={"papers": [paper]})
    data2 = resp2.json()
    assert data2["accepted"] == []
    assert data2["skipped"] == ["1706.03762"]
    assert calls["n"] == 1


def test_download_failure_marks_failed(client, monkeypatch):
    async def fail_download_pdf(arxiv_id, pdf_url, client):
        raise RuntimeError("network down")

    monkeypatch.setattr(downloader, "download_pdf", fail_download_pdf)

    resp = client.post("/api/download", json={"papers": [make_paper("9999.9999")]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "9999.9999"}).json()
    assert records[0]["status"] == "failed"


def test_api_key_default_empty(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert Settings().llm_api_key == ""


def test_api_key_read_from_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-123")
    assert Settings().llm_api_key == "sk-test-123"


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
