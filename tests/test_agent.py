import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import agent as agent_module
from app.agent import sessions
from app.agent.tools import get_tools, is_dangerous


@pytest.fixture(autouse=True)
def _clear_sessions():
    sessions.clear_sessions()
    yield
    sessions.clear_sessions()


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        return self.responses.pop(0)


def _tool_call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_tools_encapsulated():
    names = {t.name for t in get_tools()}
    for expected in (
        "search_papers",
        "search_by_topic",
        "download_papers",
        "list_downloaded_papers",
        "analyze_paper",
        "review_papers",
        "generate_innovation_points",
        "design_experiment",
        "list_servers",
        "test_server_connection",
        "deploy_code",
        "run_command",
        "monitor_server",
    ):
        assert expected in names

    for tool in get_tools():
        assert tool.name
        assert tool.description
        assert tool.args_schema is not None

    assert is_dangerous("run_command")
    assert is_dangerous("deploy_code")
    assert not is_dangerous("search_papers")
    assert not is_dangerous("analyze_paper")


async def test_manual_loop_calls_tool_then_finishes(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"count": 2, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)

    llm = FakeLLM([
        _tool_call("search_papers", {"query": "attention"}, "c1"),
        AIMessage(content="共找到 2 篇相关论文。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    result = await agent_module.run_chat(None, "搜索 attention")

    assert result["reply"] == "共找到 2 篇相关论文。"
    assert result["pending_approval"] is None
    assert executed == [("search_papers", {"query": "attention"})]
    assert result["tool_calls"][0]["tool"] == "search_papers"
    assert result["tool_calls"][0]["status"] == "done"
    assert result["tool_calls"][0]["result"] == {"count": 2, "papers": []}
    assert result["session_id"]


async def test_dangerous_tool_pauses_then_approve_executes(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)

    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "ls"}, "c1"),
        AIMessage(content="命令执行完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    first = await agent_module.run_chat(None, "运行 ls")
    assert first["reply"] is None
    assert first["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s1", "command": "ls"},
    }
    assert executed == []

    second = await agent_module.run_approve(first["session_id"], True)
    assert executed == [("run_command", {"server_id": "s1", "command": "ls"})]
    assert second["reply"] == "命令执行完成。"
    assert second["pending_approval"] is None
    assert second["tool_calls"][0]["tool"] == "run_command"
    assert second["tool_calls"][0]["status"] == "done"


async def test_dangerous_tool_pauses_then_reject_skips(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)

    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "rm -rf /"}, "c1"),
        AIMessage(content="好的，已跳过该操作。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    first = await agent_module.run_chat(None, "删库")
    assert first["pending_approval"]["tool"] == "run_command"

    second = await agent_module.run_approve(first["session_id"], False)
    assert executed == []
    assert second["reply"] == "好的，已跳过该操作。"
    assert second["tool_calls"][0]["tool"] == "run_command"
    assert second["tool_calls"][0]["status"] == "rejected"


async def test_session_history_preserved_across_turns(monkeypatch):
    llm = FakeLLM([
        AIMessage(content="你好，请问需要我做什么？"),
        AIMessage(content="正在搜索。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    first = await agent_module.run_chat(None, "你好")
    session_id = first["session_id"]
    await agent_module.run_chat(session_id, "搜索注意力机制")

    second_messages = llm.invocations[1]
    human_texts = [m.content for m in second_messages if isinstance(m, HumanMessage)]
    assert "你好" in human_texts
    assert "搜索注意力机制" in human_texts


async def test_chat_api_returns_tool_log(client, monkeypatch):
    async def fake_execute(name, args):
        return {"count": 1, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("search_papers", {"query": "attention"}, "c1"),
        AIMessage(content="找到 1 篇论文。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    resp = client.post("/api/agent/chat", json={"message": "搜索 attention"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"]
    assert data["reply"] == "找到 1 篇论文。"
    assert data["tool_calls"][0]["tool"] == "search_papers"
    assert data["tool_calls"][0]["status"] == "done"
    assert data["pending_approval"] is None


async def test_chat_api_pending_and_approve_endpoint(client, monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "ls"}, "c1"),
        AIMessage(content="执行完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    resp = client.post("/api/agent/chat", json={"message": "运行 ls"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s1", "command": "ls"},
    }
    assert executed == []

    approve_resp = client.post(
        "/api/agent/approve", json={"session_id": data["session_id"], "approve": True}
    )
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["reply"] == "执行完成。"
    assert executed == [("run_command", {"server_id": "s1", "command": "ls"})]


def test_redact_secrets(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "get_effective_config",
        lambda: {"base_url": "https://x", "api_key": "sk-abc123", "model": "m"},
    )
    monkeypatch.setattr(
        "app.servers.list_servers",
        lambda: [{"id": "1", "password": "pw-secret"}],
    )
    out = agent_module._redact_secrets("key sk-abc123 and pw-secret present")
    assert "sk-abc123" not in out
    assert "pw-secret" not in out
    assert "***" in out


def test_redact_secrets_noop_without_secrets():
    out = agent_module._redact_secrets("plain text")
    assert out == "plain text"


async def test_chat_without_api_key_returns_400(client, monkeypatch):
    def fake_build():
        raise agent_module.AgentError("LLM_API_KEY is not configured", 400)

    monkeypatch.setattr(agent_module, "_build_bound_llm", fake_build)

    resp = client.post("/api/agent/chat", json={"message": "你好"})
    assert resp.status_code == 400
    assert "LLM_API_KEY" in resp.json()["detail"]
