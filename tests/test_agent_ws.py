import asyncio
import threading
import time

import pytest
from langchain_core.messages import AIMessageChunk

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


class SingleChunkLLM:
    def __init__(self, reply):
        self.reply = reply
        self.invocations = []

    async def astream(self, messages):
        self.invocations.append(list(messages))
        yield AIMessageChunk(content=self.reply)


class GatedStreamLLM:
    """Blocks inside astream until the release gate opens (cross-thread)."""

    def __init__(self, started: threading.Event, release: threading.Event):
        self.started = started
        self.release = release

    async def astream(self, messages):
        self.started.set()
        while not self.release.is_set():
            await asyncio.sleep(0.02)
        yield AIMessageChunk(content="gate reply")


def _recv_until(ws, event_type, limit=100):
    events = []
    for _ in range(limit):
        event = ws.receive_json()
        events.append(event)
        if event.get("type") == event_type:
            return events
    raise AssertionError(f"did not receive {event_type}; got {events}")


def _wait_gate(event: threading.Event, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not event.is_set():
        if time.monotonic() > deadline:
            raise AssertionError("timeout waiting for agent task to reach the gate")
        time.sleep(0.02)


def test_chat_without_session_emits_session_then_done(client, monkeypatch):
    llm = SingleChunkLLM("你好，我准备好了。")
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "你好"})
        session_event = ws.receive_json()
        assert session_event["type"] == "session"
        assert session_event["session_id"]
        sid = session_event["session_id"]

        events = _recv_until(ws, "done")
        assert any(e["type"] == "status" and e["text"] == "thinking" for e in events)
        token_text = "".join(e["delta"] for e in events if e["type"] == "token")
        done = events[-1]
        assert done["reply"] == "你好，我准备好了。"
        assert token_text == done["reply"]

    listing = client.get("/api/agent/sessions").json()
    assert any(item["id"] == sid for item in listing)


def test_duplicate_chat_while_running_emits_error(client, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(
        agent_module,
        "_build_bound_llm",
        lambda *a, **k: GatedStreamLLM(started, release),
    )

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "第一问"})
        session_event = ws.receive_json()
        assert session_event["type"] == "session"
        sid = session_event["session_id"]
        try:
            _wait_gate(started)

            ws.send_json({"type": "chat", "message": "第二问"})
            error_round = _recv_until(ws, "error")
            assert "正在运行" in error_round[-1]["message"]
        finally:
            release.set()
        tail = _recv_until(ws, "done")
        assert tail[-1]["reply"] == "gate reply"

    detail = client.get(f"/api/agent/sessions/{sid}").json()
    assert detail["running"] is False


def test_stop_interrupts_running_task(client, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(
        agent_module,
        "_build_bound_llm",
        lambda *a, **k: GatedStreamLLM(started, release),
    )

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "长任务"})
        session_event = ws.receive_json()
        assert session_event["type"] == "session"
        sid = session_event["session_id"]

        _wait_gate(started)
        ws.send_json({"type": "stop"})
        stopped_round = _recv_until(ws, "stopped")
        assert stopped_round[-1] == {"type": "stopped"}
        release.set()

    detail = client.get(f"/api/agent/sessions/{sid}").json()
    assert detail["running"] is False
    assert detail["status"] == "interrupted"

    roles = [m["role"] for m in detail["messages"]]
    assert roles[0] == "user"
