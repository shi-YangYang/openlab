import json

from app import config, database, experiment
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


def _experiment_plans(count=2):
    return [
        {
            "hypothesis": f"假设{i}",
            "goal": f"目标{i}",
            "datasets": [f"数据集{i}"],
            "baselines": [f"基线{i}"],
            "metrics": [f"指标{i}"],
        }
        for i in range(1, count + 1)
    ]


def _innovation_points(count=2):
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


def _register_innovation(arxiv_ids=("1", "2")):
    return database.insert_innovation(
        list(arxiv_ids),
        json.dumps(_innovation_points(2), ensure_ascii=False),
        "zh",
        status="done",
    )


def _fake_chat(response, captured=None):
    async def fake_chat(messages, temperature=0.3):
        if captured is not None:
            captured.append(messages)
        return response

    return fake_chat


def test_experiments_table_migration_idempotent(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()
    database.init_db()

    conn = database._connect()
    try:
        rows = conn.execute("PRAGMA table_info(experiments)").fetchall()
    finally:
        conn.close()
    columns = [r["name"] for r in rows]
    for required in ("id", "source_type", "innovation_id", "arxiv_ids", "content",
                     "language", "status", "error", "progress", "created_at"):
        assert required in columns
    assert not any("key" in c.lower() for c in columns)


def test_experiment_from_innovation(client, monkeypatch):
    monkeypatch.setattr(
        experiment, "_chat", _fake_chat(json.dumps(_experiment_plans(2), ensure_ascii=False))
    )
    innovation_id = _register_innovation(["1", "2"])

    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id, "count": 2, "language": "zh"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["source_type"] == "innovation"
    assert data["innovation_id"] == innovation_id
    experiment_id = data["id"]

    record = client.get(f"/api/experiments/{experiment_id}").json()
    assert record["status"] == "done"
    assert record["progress"] == 100
    assert record["arxiv_ids"] == ["1", "2"]
    content = record["content"]
    assert len(content) == 2
    plan = content[0]
    assert plan["hypothesis"] == "假设1"
    assert plan["goal"] == "目标1"
    assert plan["datasets"] == ["数据集1"]
    assert plan["baselines"] == ["基线1"]
    assert plan["metrics"] == ["指标1"]


def test_experiment_from_papers(client, monkeypatch):
    monkeypatch.setattr(
        experiment, "_chat", _fake_chat(json.dumps(_experiment_plans(1), ensure_ascii=False))
    )
    _register_paper("1")
    _register_paper("2")

    resp = client.post(
        "/api/experiments",
        json={"source_type": "papers", "arxiv_ids": ["1", "2"], "count": 1, "language": "zh"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_type"] == "papers"
    record = client.get(f"/api/experiments/{data['id']}").json()
    assert record["status"] == "done"
    assert record["arxiv_ids"] == ["1", "2"]
    assert len(record["content"]) == 1


def test_experiment_count_validation(client):
    innovation_id = _register_innovation(["1"])
    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id, "count": 0, "language": "zh"},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id, "count": 4, "language": "zh"},
    )
    assert resp.status_code == 400


def test_experiment_source_validation(client):
    resp = client.post(
        "/api/experiments",
        json={"source_type": "unknown", "arxiv_ids": ["1"], "count": 1, "language": "zh"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "count": 1, "language": "zh"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/api/experiments",
        json={"source_type": "papers", "arxiv_ids": [], "count": 1, "language": "zh"},
    )
    assert resp.status_code == 400


def test_experiment_innovation_not_found(client):
    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": 99999, "count": 1, "language": "zh"},
    )
    assert resp.status_code == 404


def test_experiment_language_controls_prompt(client, monkeypatch):
    captured = []
    monkeypatch.setattr(
        experiment, "_chat", _fake_chat(json.dumps(_experiment_plans(1), ensure_ascii=False), captured)
    )
    innovation_id = _register_innovation(["1"])

    client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id, "count": 1, "language": "en"},
    )
    system_prompt = captured[0][0][1]
    assert "English" in system_prompt
    assert "中文" not in system_prompt


def test_experiment_default_count_is_1(client, monkeypatch):
    captured = []
    monkeypatch.setattr(
        experiment, "_chat", _fake_chat(json.dumps(_experiment_plans(1), ensure_ascii=False), captured)
    )
    innovation_id = _register_innovation(["1"])

    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id},
    )
    assert resp.status_code == 200
    system_prompt = captured[0][0][1]
    assert "exactly 1" in system_prompt


def test_experiment_export_markdown(client, monkeypatch):
    monkeypatch.setattr(
        experiment, "_chat", _fake_chat(json.dumps(_experiment_plans(2), ensure_ascii=False))
    )
    innovation_id = _register_innovation(["1"])

    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id, "count": 2, "language": "zh"},
    )
    experiment_id = resp.json()["id"]

    export_resp = client.get(f"/api/experiments/{experiment_id}/export")
    assert export_resp.status_code == 200
    assert "text/markdown" in export_resp.headers["content-type"]
    assert "实验方案" in export_resp.text
    assert "假设1" in export_resp.text
    assert "attachment" in export_resp.headers["content-disposition"]


def test_experiment_failure_records_error(client, monkeypatch):
    async def fail_chat(messages, temperature=0.3):
        raise RuntimeError("boom")

    monkeypatch.setattr(experiment, "_chat", fail_chat)
    innovation_id = _register_innovation(["1"])

    resp = client.post(
        "/api/experiments",
        json={"source_type": "innovation", "innovation_id": innovation_id, "count": 1, "language": "zh"},
    )
    assert resp.status_code == 200

    experiments = database.list_experiments()
    assert len(experiments) == 1
    assert experiments[0]["status"] == "failed"
    assert experiments[0]["progress"] == 100
    assert "boom" in experiments[0]["error"]


def test_experiment_not_found_returns_404(client):
    assert client.get("/api/experiments/99999").status_code == 404


def test_experiment_record_schema_fields():
    from app.schemas import ExperimentPlan, ExperimentRecord

    assert "hypothesis" in ExperimentPlan.model_fields
    assert "goal" in ExperimentPlan.model_fields
    assert "datasets" in ExperimentPlan.model_fields
    assert "baselines" in ExperimentPlan.model_fields
    assert "metrics" in ExperimentPlan.model_fields
    assert "source_type" in ExperimentRecord.model_fields
    assert "innovation_id" in ExperimentRecord.model_fields
    assert "arxiv_ids" in ExperimentRecord.model_fields
    assert "content" in ExperimentRecord.model_fields
    assert "progress" in ExperimentRecord.model_fields
    assert "error" in ExperimentRecord.model_fields


async def test_experiment_chat_sets_request_timeout(monkeypatch):
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

    monkeypatch.setattr(experiment, "ChatOpenAI", fake_chat)
    monkeypatch.setattr(experiment, "get_effective_config", lambda: {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "model": "gpt-4o-mini",
    })

    result = await experiment._chat([("system", "x"), ("human", "y")])
    assert result == "[]"
    assert created["request_timeout"] == experiment.LLM_REQUEST_TIMEOUT_SECONDS
