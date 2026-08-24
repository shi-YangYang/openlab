import json

from app import config, database, innovation
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


def _register_paper(arxiv_id):
    database.upsert_paper(make_paper(arxiv_id))
    database.upsert_analysis(
        arxiv_id, json.dumps(ANALYSIS_JSON, ensure_ascii=False), "zh"
    )


def _fake_chat(response):
    async def fake_chat(messages, temperature=0.3):
        return response

    return fake_chat


def test_innovation_list_excludes_content(client, monkeypatch):
    monkeypatch.setattr(
        innovation,
        "_chat",
        _fake_chat(json.dumps(_innovation_points(3), ensure_ascii=False)),
    )
    _register_paper("1")
    _register_paper("2")

    client.post(
        "/api/innovations",
        json={"arxiv_ids": ["1", "2"], "count": 3, "language": "zh"},
    )

    items = client.get("/api/innovations").json()
    assert len(items) == 1
    assert "content" not in items[0]
    assert "error" not in items[0]
    assert items[0]["paper_count"] == 2
    assert items[0]["innovation_count"] == 3
    assert items[0]["arxiv_ids"] == ["1", "2"]
    assert items[0]["status"] == "done"


def test_innovation_list_empty_content_counts_zero(client):
    database.insert_innovation(["1"], None, "zh", status="pending")
    items = client.get("/api/innovations").json()
    assert len(items) == 1
    assert items[0]["paper_count"] == 1
    assert items[0]["innovation_count"] == 0


def test_innovation_detail_contains_content(client, monkeypatch):
    monkeypatch.setattr(
        innovation,
        "_chat",
        _fake_chat(json.dumps(_innovation_points(2), ensure_ascii=False)),
    )
    _register_paper("1706.03762")

    resp = client.post(
        "/api/innovations",
        json={"arxiv_ids": ["1706.03762"], "count": 2, "language": "zh"},
    )
    innovation_id = resp.json()["id"]

    detail = client.get(f"/api/innovations/{innovation_id}").json()
    assert detail["status"] == "done"
    assert len(detail["content"]) == 2
    assert detail["content"][0]["title"] == "创新点1"


def test_innovation_history_migration_preserves_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")

    database.init_db()
    database.insert_innovation(
        ["1", "2"],
        json.dumps(_innovation_points(3), ensure_ascii=False),
        "zh",
        status="done",
    )

    database.init_db()
    history = database.list_innovation_history()
    assert len(history) == 1
    assert history[0]["paper_count"] == 2
    assert history[0]["innovation_count"] == 3
    assert "content" not in history[0]
