from app import config, downloader
from app.config import Settings, settings
from tests.conftest import make_paper


def test_search_returns_results(client, fake_arxiv):
    fake_arxiv([make_paper("1706.03762"), make_paper("2301.12345", title="Two")])
    resp = client.post("/api/search", json={
        "query": "attention", "max_results": 10, "platforms": ["arxiv"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "papers" in data
    assert "fallbacks" in data
    papers = data["papers"]
    assert len(papers) == 2
    assert papers[0]["arxiv_id"] == "1706.03762"
    for field in ("title", "authors", "abstract", "categories", "published", "arxiv_id", "source"):
        assert field in papers[0]


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
        "platforms": ["arxiv"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["papers"]) == 1
    assert data["papers"][0]["arxiv_id"] == "2"
    assert fake.queries[0][2] == "cs.AI"


def test_search_topic_decomposes(client, fake_arxiv, monkeypatch):
    async def fake_decompose(topic):
        return "attention mechanism transformer"

    monkeypatch.setattr("app.main.decompose_topic", fake_decompose)
    fake_arxiv([make_paper("1706.03762")])

    resp = client.post("/api/search/topic", json={
        "topic": "transformers", "max_results": 10, "platforms": ["arxiv"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "attention mechanism transformer"
    assert len(data["papers"]) == 1
    assert data["fallbacks"] == []


def test_search_topic_without_api_key(client, monkeypatch):
    monkeypatch.setattr("app.llm.get_effective_config", lambda: {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
    })
    resp = client.post("/api/search/topic", json={
        "topic": "x", "max_results": 10, "platforms": ["arxiv"],
    })
    assert resp.status_code == 400


def test_download_and_skip_duplicate(client, monkeypatch):
    calls = {"n": 0}

    async def fake_download_pdf(arxiv_id, pdf_url, client, on_progress=None):
        calls["n"] += 1
        settings.papers_dir.mkdir(parents=True, exist_ok=True)
        path = settings.papers_dir / f"{arxiv_id}.pdf"
        path.write_bytes(b"%PDF-1.4 fake")
        if on_progress is not None:
            await on_progress(100)
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
    async def fail_download_pdf(arxiv_id, pdf_url, client, on_progress=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(downloader, "download_pdf", fail_download_pdf)

    resp = client.post("/api/download", json={"papers": [make_paper("9999.9999")]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "9999.9999"}).json()
    assert records[0]["status"] == "failed"
    assert records[0]["error"] == "下载失败"


def test_download_failure_reason_maps_to_short_label(client, monkeypatch):
    from app.platforms import LoginExpiredError

    async def fail_expired(arxiv_id, pdf_url, client, on_progress=None):
        raise LoginExpiredError("cnki")

    monkeypatch.setattr(downloader, "download_pdf", fail_expired)

    resp = client.post("/api/download", json={"papers": [make_paper("9999.9999")]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "9999.9999"}).json()
    assert records[0]["status"] == "failed"
    assert records[0]["error"] == "登录已过期"


def test_download_retries_then_succeeds(client, monkeypatch):
    attempts = {"n": 0}

    async def flaky_download_pdf(arxiv_id, pdf_url, client, on_progress=None):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        settings.papers_dir.mkdir(parents=True, exist_ok=True)
        path = settings.papers_dir / f"{arxiv_id}.pdf"
        path.write_bytes(b"%PDF-1.4 fake")
        if on_progress is not None:
            await on_progress(100)
        return path

    monkeypatch.setattr(downloader, "download_pdf", flaky_download_pdf)

    resp = client.post("/api/download", json={"papers": [make_paper("1706.03762")]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "1706.03762"}).json()
    assert records[0]["status"] == "downloaded"
    assert attempts["n"] == 3


def test_download_retries_exhausted(client, monkeypatch):
    attempts = {"n": 0}

    async def always_fail(arxiv_id, pdf_url, client, on_progress=None):
        attempts["n"] += 1
        raise RuntimeError("network down")

    monkeypatch.setattr(downloader, "download_pdf", always_fail)

    resp = client.post("/api/download", json={"papers": [make_paper("9999.9999")]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "9999.9999"}).json()
    assert records[0]["status"] == "failed"
    assert attempts["n"] == config.settings.download_max_retries + 1


def test_download_cnki_paper_routes_to_browser(client, monkeypatch):
    def fake_download_cnki_pdf(article_url, dest_path):
        with open(dest_path, "wb") as f:
            f.write(b"%PDF-1.4 cnki")

    monkeypatch.setattr("app.platforms.browser.download_cnki_pdf", fake_download_cnki_pdf)

    paper = {
        "arxiv_id": "cnki-abc123",
        "title": "知网论文",
        "authors": ["张三"],
        "abstract": "",
        "categories": [],
        "published": "2024-01-15",
        "pdf_url": "",
        "source": "cnki",
        "url": "https://kns.cnki.net/kcms2/article/abstract?v=abc",
    }
    resp = client.post("/api/download", json={"papers": [paper]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == ["cnki-abc123"]

    records = client.get("/api/papers", params={"arxiv_ids": "cnki-abc123"}).json()
    assert records[0]["status"] == "downloaded"
    assert (settings.papers_dir / "cnki-abc123.pdf").exists()


def test_download_cnki_paper_without_url_fails(client):
    paper = {
        "arxiv_id": "cnki-abc123",
        "title": "知网论文",
        "authors": ["张三"],
        "abstract": "",
        "categories": [],
        "published": "2024-01-15",
        "pdf_url": "",
        "source": "cnki",
        "url": "",
    }
    resp = client.post("/api/download", json={"papers": [paper]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "cnki-abc123"}).json()
    assert records[0]["status"] == "failed"


def test_download_baidu_paper_fails_with_clear_reason(client):
    paper = {
        "arxiv_id": "baidu-abc123",
        "title": "百度学术论文",
        "authors": ["张三"],
        "abstract": "",
        "categories": [],
        "published": "2021",
        "pdf_url": "",
        "source": "baidu_xueshu",
        "url": "https://xueshu.baidu.com/usercenter/paper/show?paperid=1",
    }
    resp = client.post("/api/download", json={"papers": [paper]})
    assert resp.status_code == 200
    records = client.get("/api/papers", params={"arxiv_ids": "baidu-abc123"}).json()
    assert records[0]["status"] == "failed"
    assert records[0]["error"] == "无直接 PDF"


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


class _FakeStreamResponse:
    def __init__(self, chunks, headers):
        self._chunks = chunks
        self.headers = headers

    def raise_for_status(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamClient:
    def __init__(self, response):
        self._response = response

    def stream(self, method, url):
        return self._response


async def test_download_pdf_streams_and_reports_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(config.settings, "papers_dir", tmp_path / "papers")
    data = b"x" * 200
    resp = _FakeStreamResponse([data[:100], data[100:]], headers={"content-length": "200"})
    client = _FakeStreamClient(resp)
    progress = []

    async def on_progress(p):
        progress.append(p)

    path = await downloader.download_pdf("1", "http://example/pdf", client, on_progress=on_progress)

    assert path.read_bytes() == data
    assert progress[-1] == 100
    assert progress[0] > 0


def test_delete_paper_endpoint_cleans_pdf(client):
    from app import database

    database.upsert_paper(make_paper("1706.03762"))
    pdf = settings.papers_dir / "1706.03762.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    resp = client.delete("/api/papers/1706.03762")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert not pdf.exists()
    records = client.get("/api/papers").json()
    assert all(r["arxiv_id"] != "1706.03762" for r in records)


def test_delete_paper_endpoint_missing_pdf_still_deletes(client):
    from app import database

    database.upsert_paper(make_paper("1706.03762"))

    resp = client.delete("/api/papers/1706.03762")
    assert resp.status_code == 200
    assert database.get_paper("1706.03762") is None


def test_delete_paper_endpoint_allows_url_like_id(client):
    from urllib.parse import quote

    from app import database

    arxiv_id = "https://xueshu.baidu.com/paper/show?paperid=abc&site=xueshu_se"
    database.upsert_paper(make_paper(arxiv_id))

    resp = client.delete(f"/api/papers/{quote(arxiv_id, safe='')}")
    assert resp.status_code == 200
    assert database.get_paper(arxiv_id) is None


def test_delete_paper_endpoint_missing_paper_404(client):
    resp = client.delete("/api/papers/9999.9999")
    assert resp.status_code == 404


def test_experiment_history_and_delete(client):
    import json

    from app import database

    content = json.dumps([
        {"hypothesis": "h", "goal": "g", "datasets": ["d"], "baselines": ["b"], "metrics": ["m"]}
    ])
    database.insert_experiment("papers", None, ["1706.03762"], content, "zh", status="done")
    database.insert_experiment("innovation", 7, ["1706.03762"], None, "zh", status="done")

    resp = client.get("/api/experiments")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    by_id = {item["id"]: item for item in items}
    for item in items:
        assert "content" not in item

    papers_item = next(i for i in items if i["source_type"] == "papers")
    assert papers_item["plan_count"] == 1
    assert papers_item["source_label"] == "论文: 1 篇"

    innovation_item = next(i for i in items if i["source_type"] == "innovation")
    assert innovation_item["source_label"] == "创新点 #7"

    eid = papers_item["id"]
    resp = client.delete(f"/api/experiments/{eid}")
    assert resp.status_code == 200
    assert len(client.get("/api/experiments").json()) == 1

    resp = client.delete(f"/api/experiments/{eid}")
    assert resp.status_code == 404


def test_clear_experiments(client):
    from app import database

    database.insert_experiment("papers", None, ["1"], None, "zh", status="pending")
    database.insert_experiment("innovation", 5, ["1"], None, "zh", status="pending")

    resp = client.delete("/api/experiments")
    assert resp.status_code == 200
    assert client.get("/api/experiments").json() == []


def test_llm_models_requires_base_url(client):
    resp = client.post("/api/llm/models", json={"base_url": "", "api_key": ""})
    assert resp.status_code == 400


def test_llm_models_endpoint(client, monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self.url = None
            self.headers = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            self.url = url
            self.headers = headers
            return FakeResp()

    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["models"] == ["gpt-4o", "gpt-4o-mini"]


def test_llm_models_endpoint_error_status(client, monkeypatch):
    class FakeResp:
        status_code = 401

        def json(self):
            return {"error": {"message": "invalid api key"}}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr("app.main.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 401
    assert "invalid api key" in resp.json()["detail"]
