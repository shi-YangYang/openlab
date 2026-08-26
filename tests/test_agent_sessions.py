import pytest
from langchain_core.messages import AIMessage

from app import config, database
from app.agent import agent as agent_module
from app.agent import sessions


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        return self.responses.pop(0)


def _reply(text):
    return AIMessage(content=text)


def test_session_crud_api(client):
    resp = client.post("/api/agent/sessions", json={})
    assert resp.status_code == 200
    created = resp.json()
    assert created["id"]
    assert created["title"] == ""

    listing = client.get("/api/agent/sessions").json()
    assert any(item["id"] == created["id"] for item in listing)

    renamed = client.put(
        f"/api/agent/sessions/{created['id']}", json={"title": "新标题"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "新标题"

    assert client.delete(f"/api/agent/sessions/{created['id']}").status_code == 200
    remaining = client.get("/api/agent/sessions").json()
    assert all(item["id"] != created["id"] for item in remaining)

    assert client.delete(f"/api/agent/sessions/{created['id']}").status_code == 404


def test_list_orders_by_updated_at_desc(client):
    first = client.post("/api/agent/sessions", json={}).json()
    second = client.post("/api/agent/sessions", json={}).json()
    client.put(f"/api/agent/sessions/{second['id']}", json={"title": "updated"})

    listing = client.get("/api/agent/sessions").json()
    assert listing[0]["id"] == second["id"]
    assert listing[1]["id"] == first["id"]


async def test_list_excludes_messages(client, monkeypatch):
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: FakeLLM([_reply("你好")]))
    result = await agent_module.run_chat(None, "hello")
    assert result["session_id"]

    listing = client.get("/api/agent/sessions").json()
    assert listing
    assert all("messages" not in item for item in listing)


async def test_chat_auto_generates_title(client, monkeypatch):
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: FakeLLM([_reply("hi")]))
    long_message = "帮我搜索注意力机制相关的论文并下载分析"
    result = await agent_module.run_chat(None, long_message)

    detail = client.get(f"/api/agent/sessions/{result['session_id']}").json()
    assert detail["title"] == long_message[:30]


async def test_chat_persists_history(client, monkeypatch):
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: FakeLLM([_reply("回答内容")]))
    result = await agent_module.run_chat(None, "一个问题")

    detail = client.get(f"/api/agent/sessions/{result['session_id']}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "一个问题"
    assert detail["messages"][1]["content"] == "回答内容"


def test_session_persists_across_restart(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    database.init_db()

    session = sessions.create_session()
    sessions.update_title(session.session_id, "持久化测试")
    session.messages.append(AIMessage(content="已保存的消息"))
    sessions.save_messages(session)

    # Simulate a restart: re-run migration/init and read fresh.
    database.init_db()
    loaded = sessions.get_session(session.session_id)
    assert loaded is not None
    assert loaded.title == "持久化测试"
    assert loaded.messages[0].content == "已保存的消息"

    sessions.clear_sessions()


def test_delete_removes_persisted_row(client):
    created = client.post("/api/agent/sessions", json={}).json()
    client.delete(f"/api/agent/sessions/{created['id']}")
    detail = client.get(f"/api/agent/sessions/{created['id']}")
    assert detail.status_code == 404


def test_update_missing_session_returns_404(client):
    resp = client.put("/api/agent/sessions/does-not-exist", json={"title": "x"})
    assert resp.status_code == 404


async def test_session_detail_includes_usage(client, monkeypatch):
    monkeypatch.setattr(
        agent_module, "_build_bound_llm", lambda *a, **k: FakeLLM([_reply("你好")])
    )
    result = await agent_module.run_chat(None, "hello")

    detail = client.get(f"/api/agent/sessions/{result['session_id']}").json()
    assert detail["usage"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "message_count": 2,
        "last_input_tokens": 0,
        "last_output_tokens": 0,
    }
