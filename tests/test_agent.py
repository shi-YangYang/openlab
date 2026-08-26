import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app import config, database
from app.agent import agent as agent_module
from app.agent import sessions
from app.agent.tools import get_tools, is_dangerous


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
        self.invocations = []

    def _take(self, messages):
        self.invocations.append(list(messages))
        return self.responses.pop(0)

    async def ainvoke(self, messages):
        return self._take(messages)

    async def astream(self, messages):
        response = self._take(messages)
        yield AIMessageChunk(
            content=response.content,
            tool_calls=list(getattr(response, "tool_calls", []) or []),
            usage_metadata=getattr(response, "usage_metadata", None),
        )


def _recv_until(ws, event_type, limit=100):
    events = []
    for _ in range(limit):
        event = ws.receive_json()
        events.append(event)
        if event.get("type") == event_type:
            return events
    raise AssertionError(f"did not receive {event_type}; got {events}")


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
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

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
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

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
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

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
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    first = await agent_module.run_chat(None, "你好")
    session_id = first["session_id"]
    await agent_module.run_chat(session_id, "搜索注意力机制")

    second_messages = llm.invocations[1]
    human_texts = [m.content for m in second_messages if isinstance(m, HumanMessage)]
    assert "你好" in human_texts
    assert "搜索注意力机制" in human_texts


async def test_ws_chat_returns_tool_log(client, monkeypatch):
    async def fake_execute(name, args):
        return {"count": 1, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("search_papers", {"query": "attention"}, "c1"),
        AIMessage(content="找到 1 篇论文。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "搜索 attention"})
        session_event = ws.receive_json()
        assert session_event["type"] == "session"
        assert session_event["session_id"]

        events = _recv_until(ws, "done")
        assert not any(e["type"] == "error" for e in events)
        assert any(e["type"] == "status" for e in events)
        tool_events = [e for e in events if e["type"] == "tool_call"]
        assert len(tool_events) == 1
        entry = tool_events[0]["entry"]
        assert entry["tool"] == "search_papers"
        assert entry["status"] == "done"
        assert entry["result"] == {"count": 1, "papers": []}

        token_text = "".join(e["delta"] for e in events if e["type"] == "token")
        done = events[-1]
        assert done["reply"] == "找到 1 篇论文。"
        assert token_text == done["reply"]
        assert done["usage"]["message_count"] == 2


async def test_ws_pending_and_approve_endpoint(client, monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "ls"}, "c1"),
        AIMessage(content="执行完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "运行 ls"})
        assert ws.receive_json()["type"] == "session"

        first_round = _recv_until(ws, "pending_approval")
        pending = first_round[-1]
        assert pending["tool"] == "run_command"
        assert pending["args"] == {"server_id": "s1", "command": "ls"}
        assert executed == []
        assert not any(e["type"] == "done" for e in first_round)

        ws.send_json({"type": "approve", "approve": True})
        second_round = _recv_until(ws, "done")
        approve_done = second_round[-1]
        assert approve_done["reply"] == "执行完成。"
        approve_tools = [e for e in second_round if e["type"] == "tool_call"]
        assert approve_tools[0]["entry"]["status"] == "done"
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


async def test_ws_chat_without_api_key_emits_error(client, monkeypatch):
    def fake_build(model=None, reasoning_effort=None):
        raise agent_module.AgentError("LLM_API_KEY is not configured", 400)

    monkeypatch.setattr(agent_module, "_build_bound_llm", fake_build)

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "你好"})
        session_event = ws.receive_json()
        assert session_event["type"] == "session"
        session_id = session_event["session_id"]

        error = _recv_until(ws, "error")[-1]
        assert "LLM_API_KEY" in error["message"]

    detail = client.get(f"/api/agent/sessions/{session_id}").json()
    assert detail["running"] is False


async def test_run_chat_passes_model_and_reasoning_effort(monkeypatch):
    captured = {}

    def fake_bound(model=None, reasoning_effort=None):
        captured["model"] = model
        captured["reasoning_effort"] = reasoning_effort
        return FakeLLM([AIMessage(content="ok")])

    monkeypatch.setattr(agent_module, "_build_bound_llm", fake_bound)

    await agent_module.run_chat(None, "hi", model="m1", reasoning_effort="high")
    assert captured == {"model": "m1", "reasoning_effort": "high"}


async def test_approve_reuses_chat_model_and_effort(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)

    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "ls"}, "c1"),
        AIMessage(content="命令执行完成。"),
    ])
    captured = []

    def fake_bound(model=None, reasoning_effort=None):
        captured.append((model, reasoning_effort))
        return llm

    monkeypatch.setattr(agent_module, "_build_bound_llm", fake_bound)

    first = await agent_module.run_chat(None, "运行 ls", model="m1", reasoning_effort="high")
    assert first["pending_approval"] is not None

    second = await agent_module.run_approve(first["session_id"], True)
    assert second["reply"] == "命令执行完成。"
    assert captured == [("m1", "high"), ("m1", "high")]


class ShardStreamLLM:
    """Streams one reply in two text chunks; usage metadata on the last chunk."""

    def __init__(self):
        self.invocations = []

    async def astream(self, messages):
        self.invocations.append(list(messages))
        yield AIMessageChunk(content="找到 ")
        yield AIMessageChunk(
            content="1 篇论文。",
            usage_metadata={"input_tokens": 11, "output_tokens": 4, "total_tokens": 15},
        )


def test_usage_recorded_from_response_metadata(client, monkeypatch):
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: ShardStreamLLM())

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "hello"})
        session_id = ws.receive_json()["session_id"]
        done = _recv_until(ws, "done")[-1]

    assert done["reply"] == "找到 1 篇论文。"
    assert done["usage"]["input_tokens"] == 11
    assert done["usage"]["output_tokens"] == 4
    assert done["usage"]["total_tokens"] == 15

    detail = client.get(f"/api/agent/sessions/{session_id}").json()
    assert detail["usage"]["input_tokens"] == 11
    assert detail["usage"]["output_tokens"] == 4
    assert detail["usage"]["total_tokens"] == 15
    assert detail["usage"]["message_count"] == 2
    assert detail["usage"]["last_input_tokens"] == 11
    assert detail["usage"]["last_output_tokens"] == 4
