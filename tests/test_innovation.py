import json

import pytest

from app import config, database, innovation
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


def _innovation_points(count=3):
    return [
        {
            "title": f"创新点{i}",
            "description": f"描述{i}",
            "basis": [f"依据{i}"],
            "expected_contribution": f"贡献{i}",
        }
        for i in range(1, count + 1)
    ]


def _register_paper(arxiv_id, with_analysis=True):
    database.upsert_paper(make_paper(arxiv_id))
    if with_analysis:
        database.upsert_analysis(arxiv_id, json.dumps(ANALYSIS_JSON, ensure_ascii=False), "zh")


def _fake_chat(response, captured=None):
    async def fake_chat(messages, temperature=0.3):
        if captured is not None:
            captured.append(messages)
        return response

    return fake_chat


def test_innovations_table_migration_idempotent(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()
    database.init_db()

    conn = database._connect()
    try:
        rows = conn.execute("PRAGMA table_info(innovations)").fetchall()
    finally:
        conn.close()
    columns = [r["name"] for r in rows]
    for required in ("id", "arxiv_ids", "content", "language", "status", "error", "progress", "created_at"):
        assert required in columns
    assert not any("key" in c.lower() for c in columns)


def test_single_paper_innovation(client, monkeypatch):
    monkeypatch.setattr(
        innovation, "_chat", _fake_chat(json.dumps(_innovation_points(3), ensure_ascii=False))
    )
    _register_paper("1706.03762")

    resp = client.post("/api/innovations", json={"arxiv_ids": ["1706.03762"], "count": 3, "language": "zh"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["arxiv_ids"] == ["1706.03762"]
    innovation_id = data["id"]

    record = client.get(f"/api/innovations/{innovation_id}").json()
    assert record["status"] == "done"
    assert record["progress"] == 100
    content = record["content"]
    assert len(content) == 3
    point = content[0]
    assert point["title"] == "创新点1"
    assert point["description"] == "描述1"
    assert point["basis"] == ["依据1"]
    assert point["expected_contribution"] == "贡献1"


def test_multi_paper_innovation(client, monkeypatch):
    monkeypatch.setattr(
        innovation, "_chat", _fake_chat(json.dumps(_innovation_points(2), ensure_ascii=False))
    )
    _register_paper("1")
    _register_paper("2")

    resp = client.post("/api/innovations", json={"arxiv_ids": ["1", "2"], "count": 2, "language": "zh"})
    assert resp.status_code == 200
    record = client.get(f"/api/innovations/{resp.json()['id']}").json()
    assert record["status"] == "done"
    assert record["arxiv_ids"] == ["1", "2"]
    assert len(record["content"]) == 2


def test_innovation_count_validation(client):
    resp = client.post("/api/innovations", json={"arxiv_ids": ["1"], "count": 0, "language": "zh"})
    assert resp.status_code == 400
    resp = client.post("/api/innovations", json={"arxiv_ids": ["1"], "count": 11, "language": "zh"})
    assert resp.status_code == 400
    resp = client.post("/api/innovations", json={"arxiv_ids": [], "count": 3, "language": "zh"})
    assert resp.status_code == 400


def test_innovation_count_controls_result(client, monkeypatch):
    monkeypatch.setattr(
        innovation, "_chat", _fake_chat(json.dumps(_innovation_points(5), ensure_ascii=False))
    )
    _register_paper("1706.03762")

    resp = client.post("/api/innovations", json={"arxiv_ids": ["1706.03762"], "count": 5, "language": "zh"})
    record = client.get(f"/api/innovations/{resp.json()['id']}").json()
    assert record["status"] == "done"
    assert len(record["content"]) == 5


def test_innovation_language_controls_prompt(client, monkeypatch):
    captured = []
    monkeypatch.setattr(
        innovation, "_chat", _fake_chat(json.dumps(_innovation_points(3), ensure_ascii=False), captured)
    )
    _register_paper("1706.03762")

    client.post("/api/innovations", json={"arxiv_ids": ["1706.03762"], "count": 3, "language": "en"})
    system_prompt = captured[0][0][1]
    assert "English" in system_prompt
    assert "中文" not in system_prompt


def test_innovation_default_count_is_3(client, monkeypatch):
    captured = []
    monkeypatch.setattr(
        innovation, "_chat", _fake_chat(json.dumps(_innovation_points(3), ensure_ascii=False), captured)
    )
    _register_paper("1706.03762")

    resp = client.post("/api/innovations", json={"arxiv_ids": ["1706.03762"]})
    assert resp.status_code == 200
    system_prompt = captured[0][0][1]
    assert "exactly 3" in system_prompt


def test_innovation_export_markdown(client, monkeypatch):
    monkeypatch.setattr(
        innovation, "_chat", _fake_chat(json.dumps(_innovation_points(3), ensure_ascii=False))
    )
    _register_paper("1706.03762")

    resp = client.post("/api/innovations", json={"arxiv_ids": ["1706.03762"], "count": 3, "language": "zh"})
    innovation_id = resp.json()["id"]

    export_resp = client.get(f"/api/innovations/{innovation_id}/export")
    assert export_resp.status_code == 200
    assert "text/markdown" in export_resp.headers["content-type"]
    assert "创新点" in export_resp.text
    assert "创新点1" in export_resp.text
    assert "attachment" in export_resp.headers["content-disposition"]


def test_innovation_failure_records_error(client, monkeypatch):
    async def fail_chat(messages, temperature=0.3):
        raise RuntimeError("boom")

    monkeypatch.setattr(innovation, "_chat", fail_chat)
    _register_paper("1")

    resp = client.post("/api/innovations", json={"arxiv_ids": ["1"], "count": 3, "language": "zh"})
    assert resp.status_code == 200

    innovations = database.list_innovations()
    assert len(innovations) == 1
    assert innovations[0]["status"] == "failed"
    assert innovations[0]["progress"] == 100
    assert "boom" in innovations[0]["error"]


def test_innovation_not_found_returns_404(client):
    assert client.get("/api/innovations/99999").status_code == 404


def test_innovation_record_schema_fields():
    from app.schemas import InnovationPoint, InnovationRecord

    assert "title" in InnovationPoint.model_fields
    assert "description" in InnovationPoint.model_fields
    assert "basis" in InnovationPoint.model_fields
    assert "expected_contribution" in InnovationPoint.model_fields
    assert "arxiv_ids" in InnovationRecord.model_fields
    assert "content" in InnovationRecord.model_fields
    assert "progress" in InnovationRecord.model_fields
    assert "error" in InnovationRecord.model_fields


async def test_innovation_chat_sets_request_timeout(monkeypatch):
    created = {}

    class FakeMessage:
        content = "[]"

    class FakeChatModel:
        def __init__(self, **kwargs):
            created.update(kwargs)

        async def ainvoke(self, messages):
            return FakeMessage()

    def fake_chat(**kwargs):
        return FakeChatModel(**kwargs)

    monkeypatch.setattr(innovation, "ChatOpenAI", fake_chat)
    monkeypatch.setattr(innovation, "get_effective_config", lambda: {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "model": "gpt-4o-mini",
    })

    result = await innovation._chat([("system", "x"), ("human", "y")])
    assert result == "[]"
    assert created["request_timeout"] == innovation.LLM_REQUEST_TIMEOUT_SECONDS
