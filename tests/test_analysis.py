import json

import pytest

from app import analysis, database
from app.config import settings
from tests.conftest import make_paper

ANALYSIS_JSON = {
    "summary": {
        "research_problem": "研究问题",
        "method": "方法",
        "contributions": ["贡献一"],
        "conclusion": "结论",
    },
    "experiments": {
        "datasets": ["数据集"],
        "baselines": ["基线"],
        "metrics": ["指标"],
        "key_results": "关键结果",
    },
    "limitations": "局限",
    "future_work": "未来工作",
    "keywords": ["关键词"],
    "tags": ["标签"],
}

REVIEW_JSON = {
    "common_themes": ["共同主题"],
    "differences": ["差异"],
    "research_gaps": ["研究空白"],
    "summary": "综述总结",
}


def _register_paper(arxiv_id, downloaded=True):
    database.upsert_paper(make_paper(arxiv_id))
    if downloaded:
        database.set_status(
            arxiv_id, "downloaded", str(settings.papers_dir / f"{arxiv_id}.pdf")
        )


def _fake_chat(response, captured=None):
    async def fake_chat(messages, temperature=0.2):
        if captured is not None:
            captured.append(messages)
        return response

    return fake_chat


def test_chunk_text_short():
    assert analysis.chunk_text("short text") == ["short text"]


def test_chunk_text_empty():
    assert analysis.chunk_text("") == []


def test_chunk_text_long():
    chunks = analysis.chunk_text("a" * 30000)
    assert len(chunks) > 1
    assert all(len(c) <= analysis.CHUNK_SIZE_CHARS for c in chunks)


async def test_analyze_paper_text_chunks_and_merges(monkeypatch):
    calls = []
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False), calls)
    )
    result = await analysis.analyze_paper_text("paper " * 5000, "zh")
    assert isinstance(result, analysis.PaperAnalysis)
    assert len(calls) > 1


def test_analyze_single_paper(client, monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False))
    )
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    _register_paper("1706.03762")

    resp = client.post("/api/analyze/1706.03762", json={"language": "zh"})
    assert resp.status_code == 200
    assert resp.json() == {"arxiv_id": "1706.03762", "status": "pending"}

    record = client.get("/api/analyses/1706.03762").json()
    assert record["status"] == "done"
    assert record["language"] == "zh"
    content = record["content"]
    assert content["summary"]["research_problem"] == "研究问题"
    assert content["summary"]["contributions"] == ["贡献一"]
    assert content["experiments"]["datasets"] == ["数据集"]
    assert content["keywords"] == ["关键词"]


def test_analyze_language_controls_prompt(client, monkeypatch):
    captured = []
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False), captured)
    )
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    _register_paper("1706.03762")

    client.post("/api/analyze/1706.03762", json={"language": "en"})
    system_prompt = captured[0][0][1]
    assert "English" in system_prompt
    assert "中文" not in system_prompt


def test_analyze_default_language_is_zh(client, monkeypatch):
    captured = []
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False), captured)
    )
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    _register_paper("1706.03762")

    client.post("/api/analyze/1706.03762", json={})
    assert client.get("/api/analyses/1706.03762").json()["language"] == "zh"


def test_analyze_batch_runs_sequentially(client, monkeypatch):
    order = []
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")

    async def fake_chat(messages, temperature=0.2):
        order.append(messages[1][1])
        return json.dumps(ANALYSIS_JSON, ensure_ascii=False)

    monkeypatch.setattr(analysis, "_chat", fake_chat)
    _register_paper("1")
    _register_paper("2")

    resp = client.post("/api/analyze/batch", json={"arxiv_ids": ["1", "2"], "language": "zh"})
    assert resp.status_code == 200
    assert resp.json()["arxiv_ids"] == ["1", "2"]

    records = client.get("/api/analyses", params={"arxiv_ids": "1,2"}).json()
    assert all(r["status"] == "done" for r in records)
    assert order == ["paper full text", "paper full text"]


def test_analyze_missing_pdf_marks_failed(client, monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False))
    )
    _register_paper("9999.9999", downloaded=True)
    (settings.papers_dir / "9999.9999.pdf").unlink(missing_ok=True)

    client.post("/api/analyze/9999.9999", json={"language": "zh"})
    record = client.get("/api/analyses/9999.9999").json()
    assert record["status"] == "failed"
    assert record["content"] is None
    assert record["error"]


def test_analyze_invalid_json_marks_failed(client, monkeypatch):
    monkeypatch.setattr(analysis, "_chat", _fake_chat("this is not json"))
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    _register_paper("1706.03762")

    client.post("/api/analyze/1706.03762", json={"language": "zh"})
    record = client.get("/api/analyses/1706.03762").json()
    assert record["status"] == "failed"
    assert record["error"]


def test_analysis_overwrites_previous_result(client, monkeypatch):
    responses = iter(
        [
            json.dumps(ANALYSIS_JSON, ensure_ascii=False),
            json.dumps({**ANALYSIS_JSON, "keywords": ["新关键词"]}, ensure_ascii=False),
        ]
    )

    async def fake_chat(messages, temperature=0.2):
        return next(responses)

    monkeypatch.setattr(analysis, "_chat", fake_chat)
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    _register_paper("1706.03762")

    client.post("/api/analyze/1706.03762", json={"language": "zh"})
    first = client.get("/api/analyses/1706.03762").json()
    client.post("/api/analyze/1706.03762", json={"language": "zh"})
    second = client.get("/api/analyses/1706.03762").json()

    assert first["content"]["keywords"] == ["关键词"]
    assert second["content"]["keywords"] == ["新关键词"]


def test_review_returns_comparative_result(client, monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(REVIEW_JSON, ensure_ascii=False))
    )
    _register_paper("1")
    _register_paper("2")
    database.upsert_analysis("1", json.dumps(ANALYSIS_JSON, ensure_ascii=False), "zh")
    database.upsert_analysis("2", json.dumps(ANALYSIS_JSON, ensure_ascii=False), "zh")

    resp = client.post("/api/review", json={"arxiv_ids": ["1", "2"], "language": "zh"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    review_id = data["id"]

    record = client.get(f"/api/reviews/{review_id}").json()
    assert record["status"] == "done"
    assert record["progress"] == 100
    assert record["content"]["common_themes"] == ["共同主题"]
    assert record["content"]["research_gaps"] == ["研究空白"]
    assert record["arxiv_ids"] == ["1", "2"]


def test_review_requires_at_least_two_papers(client):
    resp = client.post("/api/review", json={"arxiv_ids": ["1"], "language": "zh"})
    assert resp.status_code == 400


def test_export_analysis_markdown(client, monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False))
    )
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    _register_paper("1706.03762")
    client.post("/api/analyze/1706.03762", json={"language": "zh"})

    resp = client.get("/api/analyses/1706.03762/export")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    assert "研究问题" in resp.text
    assert "attachment" in resp.headers["content-disposition"]


def test_export_review_markdown(client, monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(REVIEW_JSON, ensure_ascii=False))
    )
    _register_paper("1")
    _register_paper("2")
    resp = client.post("/api/review", json={"arxiv_ids": ["1", "2"], "language": "zh"})
    review_id = resp.json()["id"]

    export_resp = client.get(f"/api/reviews/{review_id}/export")
    assert export_resp.status_code == 200
    assert "共同主题" in export_resp.text


def test_analyses_and_reviews_have_no_api_key_column(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "papers_dir", tmp_path / "data" / "papers")
    monkeypatch.setattr(settings, "db_path", tmp_path / "data" / "openlab.db")
    database.init_db()

    conn = database._connect()
    try:
        for table in ("analyses", "reviews"):
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            columns = [r["name"] for r in rows]
            assert not any("key" in c.lower() for c in columns)
    finally:
        conn.close()


def test_analyze_without_api_key_returns_400(client, monkeypatch):
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper full text")
    monkeypatch.setattr(analysis, "get_effective_config", lambda: {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
    })
    _register_paper("1706.03762")

    client.post("/api/analyze/1706.03762", json={"language": "zh"})
    record = client.get("/api/analyses/1706.03762").json()
    assert record["status"] == "failed"


def test_analyze_not_downloaded_returns_409(client):
    _register_paper("1706.03762", downloaded=False)
    resp = client.post("/api/analyze/1706.03762", json={"language": "zh"})
    assert resp.status_code == 409
    assert "尚未下载" in resp.json()["detail"]


def test_analyze_missing_paper_returns_404(client):
    resp = client.post("/api/analyze/does.not.exist", json={"language": "zh"})
    assert resp.status_code == 404


def test_analyze_batch_not_downloaded_returns_409(client):
    _register_paper("1", downloaded=True)
    _register_paper("2", downloaded=False)
    resp = client.post(
        "/api/analyze/batch", json={"arxiv_ids": ["1", "2"], "language": "zh"}
    )
    assert resp.status_code == 409
    assert "2" in resp.json()["detail"]
    assert client.get("/api/analyses/1").status_code == 404


def test_review_failure_records_error(client, monkeypatch):
    async def fail_chat(messages, temperature=0.2):
        raise RuntimeError("boom")

    monkeypatch.setattr(analysis, "_chat", fail_chat)
    _register_paper("1")
    _register_paper("2")

    resp = client.post("/api/review", json={"arxiv_ids": ["1", "2"], "language": "zh"})
    assert resp.status_code == 200

    reviews = database.list_reviews()
    assert len(reviews) == 1
    assert reviews[0]["status"] == "failed"
    assert reviews[0]["progress"] == 100
    assert "boom" in reviews[0]["error"]


async def test_chat_sets_request_timeout(monkeypatch):
    created = {}

    class FakeMessage:
        content = "ok"

    class FakeChatModel:
        def __init__(self, **kwargs):
            created.update(kwargs)

        async def ainvoke(self, messages):
            return FakeMessage()

    def fake_chat(**kwargs):
        return FakeChatModel(**kwargs)

    monkeypatch.setattr(analysis, "ChatOpenAI", fake_chat)
    monkeypatch.setattr(analysis, "get_effective_config", lambda: {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "model": "gpt-4o-mini",
    })

    result = await analysis._chat([("system", "x"), ("human", "y")])
    assert result == "ok"
    assert created["request_timeout"] == analysis.LLM_REQUEST_TIMEOUT_SECONDS


async def test_analyze_paper_text_calls_progress_callback(monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False))
    )
    progress_calls = []

    async def on_progress(progress, message):
        progress_calls.append((progress, message))

    await analysis.analyze_paper_text("paper " * 5000, "zh", on_progress=on_progress)

    assert progress_calls
    assert progress_calls[0][0] >= 0
    assert progress_calls[-1][0] == 100
    assert any("分块" in m for _, m in progress_calls)
    assert any("合并" in m for _, m in progress_calls)


def test_analysis_progress_written_to_db(client, monkeypatch):
    monkeypatch.setattr(
        analysis, "_chat", _fake_chat(json.dumps(ANALYSIS_JSON, ensure_ascii=False))
    )
    monkeypatch.setattr(analysis, "extract_text", lambda path: "paper " * 5000)
    _register_paper("1706.03762")

    client.post("/api/analyze/1706.03762", json={"language": "zh"})
    record = client.get("/api/analyses/1706.03762").json()

    assert record["status"] == "done"
    assert record["progress"] == 100
    assert record["message"]


def test_analysis_record_schema_has_progress_and_message():
    from app.schemas import AnalysisRecord, PaperRecord, ReviewRecord

    assert "progress" in AnalysisRecord.model_fields
    assert "message" in AnalysisRecord.model_fields
    assert "error" in AnalysisRecord.model_fields
    assert "progress" in PaperRecord.model_fields
    assert "progress" in ReviewRecord.model_fields
    assert "error" in ReviewRecord.model_fields
