import json

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

    monkeypatch.setattr("app.routes.search.decompose_topic", fake_decompose)
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
    resp = _FakeStreamResponse(
        [data[:100], data[100:]],
        headers={"content-length": "200", "content-type": "application/pdf"},
    )
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

    monkeypatch.setattr("app.routes.llm.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["models"] == [
        {"id": "gpt-4o", "context_length": None, "reasoning_efforts": []},
        {"id": "gpt-4o-mini", "context_length": None, "reasoning_efforts": []},
    ]


def test_llm_models_endpoint_parses_context_length(client, monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "a", "max_context_length": 1048576},
                    {"id": "b", "context_window": 128000},
                    {"id": "c", "permission": [{"id": "x"}]},
                    "plain-id",
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr("app.routes.llm.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["models"] == [
        {"id": "a", "context_length": 1048576, "reasoning_efforts": []},
        {"id": "b", "context_length": 128000, "reasoning_efforts": []},
        {"id": "c", "context_length": None, "reasoning_efforts": []},
        {"id": "plain-id", "context_length": None, "reasoning_efforts": []},
    ]


def test_llm_models_endpoint_parses_reasoning_efforts(client, monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "a", "reasoning_efforts": ["low", "medium", "high"]},
                    {"id": "b", "supported_reasoning_efforts": "low,medium"},
                    {"id": "c", "reasoning_effort": "high"},
                    {"id": "d", "reasoning_effort_options": []},
                    {"id": "e"},
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr("app.routes.llm.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["models"] == [
        {"id": "a", "context_length": None, "reasoning_efforts": ["low", "medium", "high"]},
        {"id": "b", "context_length": None, "reasoning_efforts": ["low", "medium"]},
        {"id": "c", "context_length": None, "reasoning_efforts": ["high"]},
        {"id": "d", "context_length": None, "reasoning_efforts": []},
        {"id": "e", "context_length": None, "reasoning_efforts": []},
    ]


def test_llm_models_endpoint_guesses_reasoning_efforts(client, monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "o3-mini"},
                    {"id": "deepseek-v4-pro"},
                    {"id": "qwen3.8-max"},
                    {"id": "gpt-4o"},
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr("app.routes.llm.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 200
    models = resp.json()["models"]
    by_id = {m["id"]: m["reasoning_efforts"] for m in models}
    assert by_id["o3-mini"] == ["low", "medium", "high"]
    assert by_id["deepseek-v4-pro"] == ["low", "high", "max", "xhigh"]
    assert by_id["qwen3.8-max"] == ["minimal", "low", "medium", "high", "xhigh"]
    assert by_id["gpt-4o"] == []


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

    monkeypatch.setattr("app.routes.llm.httpx.AsyncClient", FakeAsyncClient)

    resp = client.post(
        "/api/llm/models",
        json={"base_url": "https://api.openai.com/v1", "api_key": "sk-test"},
    )
    assert resp.status_code == 401
    assert "invalid api key" in resp.json()["detail"]


def _seed_experiment():
    from app import database

    database.init_db()
    content = json.dumps([
        {"hypothesis": "h", "goal": "g", "datasets": ["d"], "baselines": ["b"], "metrics": ["m"]}
    ])
    rec = database.insert_experiment("papers", None, ["1706.03762"], content, "zh", status="done")
    return rec["id"] if isinstance(rec, dict) else rec


def _seed_run_server(server_id="testrun-srv"):
    # client fixture patches settings.data_dir into tmp_path; seed a server there.
    servers_path = config.settings.data_dir / "servers.json"
    original = (
        json.loads(servers_path.read_text(encoding="utf-8"))
        if servers_path.exists()
        else []
    )
    servers_path.write_text(
        json.dumps(
            original
            + [
                {
                    "id": server_id,
                    "name": "t",
                    "host": "h",
                    "port": 22,
                    "username": "u",
                    "auth_type": "password",
                    "password": "pw-12345678",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_experiment_run_create_validates_references(client):
    missing_exp = client.post(
        "/api/experiment-runs",
        json={"experiment_id": 99999, "server_id": "s1"},
    )
    assert missing_exp.status_code == 404


def test_experiment_run_crud_round_trip(client):
    _seed_run_server()

    exp_id = _seed_experiment()
    resp = client.post(
        "/api/experiment-runs",
        json={"experiment_id": exp_id, "server_id": "testrun-srv"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert set(body["steps"]) == {"sync_code", "setup_env", "launch_training", "monitor_output"}

    run_id = body["id"]
    got = client.get(f"/api/experiment-runs/{run_id}")
    assert got.status_code == 200
    assert "log_tail" in got.json()

    listed = client.get("/api/experiment-runs")
    assert any(r["id"] == run_id for r in listed.json())

    deleted = client.delete(f"/api/experiment-runs/{run_id}")
    assert deleted.status_code == 200
    gone = client.get(f"/api/experiment-runs/{run_id}")
    assert gone.status_code == 404


def test_experiment_run_delete_missing_404(client):
    resp = client.delete("/api/experiment-runs/999999")
    assert resp.status_code == 404


def test_delete_experiment_cascades_runs(client):
    _seed_run_server()

    exp_id = _seed_experiment()
    resp = client.post(
        "/api/experiment-runs",
        json={"experiment_id": exp_id, "server_id": "testrun-srv"},
    )
    assert resp.status_code == 200
    run_id = resp.json()["id"]

    deleted = client.delete(f"/api/experiments/{exp_id}")
    assert deleted.status_code == 200

    gone = client.get(f"/api/experiment-runs/{run_id}")
    assert gone.status_code == 404
    listed = client.get("/api/experiment-runs")
    assert not any(r["id"] == run_id for r in listed.json())


def test_translation_endpoints(client):
    from app import database

    database.init_db()
    database.upsert_paper(make_paper("1706.03762"))
    # set downloaded status with a local pdf
    database.set_status("1706.03762", "downloaded", "x.pdf")

    # status: downloaded but no translation file
    resp = client.get("/api/papers/1706.03762/translation")
    assert resp.status_code == 200
    assert resp.json()["translated"] is False

    # progress before start
    resp = client.get("/api/papers/1706.03762/translate/progress")
    assert resp.status_code == 200
    assert resp.json()["translated"] is False

    # missing paper -> 404
    resp = client.get("/api/papers/9999.9999/translation")
    assert resp.status_code == 404


def test_delete_paper_cleans_translation(client):
    from app import config, database
    from app.translation import delete_translation, translated_path

    database.init_db()
    database.upsert_paper(make_paper("1706.03762"))
    database.set_status("1706.03762", "downloaded", "x.pdf")

    tp = translated_path("1706.03762")
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text("# translation", encoding="utf-8")
    assert tp.exists()

    resp = client.delete("/api/papers/1706.03762")
    assert resp.status_code == 200
    assert not tp.exists()
    # cleanup for other tests that reuse this paper id
    delete_translation("1706.03762")
