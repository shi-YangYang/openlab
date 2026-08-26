import pytest
from langchain_core.messages import AIMessage

from app import config, database
from app.agent import agent as agent_module
from app.agent import sessions


@pytest.fixture(autouse=True)
def _setup_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    database.init_db()
    sessions.clear_sessions()
    yield
    sessions.clear_sessions()


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, messages):
        return self.responses.pop(0)


def _tool_call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_export_unknown_session_returns_404(client):
    resp = client.get("/api/agent/sessions/does-not-exist/export")
    assert resp.status_code == 404


async def test_export_contains_messages_and_redacts_secrets(client, monkeypatch):
    async def fake_execute(name, args):
        return {"count": 1, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("search_papers", {"query": "密码是 pw-secret 检索"}, "c1"),
        AIMessage(content="分析完成，密钥是 sk-export-key。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)
    monkeypatch.setattr(
        agent_module,
        "get_effective_config",
        lambda: {"base_url": "https://x", "api_key": "sk-export-key", "model": "m"},
    )
    monkeypatch.setattr(
        "app.servers.list_servers",
        lambda: [{"id": "1", "password": "pw-secret"}],
    )

    created = client.post("/api/agent/sessions", json={}).json()
    result = await agent_module.run_chat(created["id"], "搜索 attention")
    assert result["pending_approval"] is None

    resp = client.get(f"/api/agent/sessions/{created['id']}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.headers["content-disposition"] == (
        f'attachment; filename="agent-{created["id"]}.md"'
    )

    body = resp.text
    assert body.startswith("# 搜索 attention")
    assert "**user**:" in body and "搜索 attention" in body
    assert "**assistant**:" in body and "分析完成" in body
    assert "<details><summary>工具调用</summary>" in body
    assert "`search_papers`" in body and "（完成）" in body
    assert "`run_command`" not in body
    assert "sk-export-key" not in body
    assert "pw-secret" not in body
    assert body.count("***") >= 2
