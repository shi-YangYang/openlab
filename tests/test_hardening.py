"""spec-034 production hardening: LLM retry helper, streaming retry boundary,
global exception handler, request_timeout coverage, and log wiring."""
import ast
import logging
from pathlib import Path

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk

from app import config, database
from app import llm as llm_module
from app.agent import agent as agent_module
from app.agent import sessions
from app.app import app as fastapi_app

BACKEND_APP_DIR = Path(__file__).resolve().parent.parent / "backend" / "app"


@pytest.fixture(autouse=True)
def _setup_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    monkeypatch.setenv(
        "AGENT_PERMISSIONS_PATH", str(data_dir / "agent_permissions.json")
    )
    database.init_db()
    sessions.clear_sessions()
    yield
    sessions.clear_sessions()


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    async def _no_sleep(_attempt):
        return None

    monkeypatch.setattr(llm_module, "backoff_sleep", _no_sleep)


class _Msg:
    def __init__(self, content):
        self.content = content


def _conn_error():
    return openai.APIConnectionError(
        request=httpx.Request("POST", "https://unit.test")
    )


# --------------------------------------------------------------- FR-2 (AC-2)


async def test_ainvoke_with_retry_succeeds_after_transient_failures(caplog):
    class FlakyLLM:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, messages):
            self.calls += 1
            if self.calls <= 2:
                raise _conn_error()
            return _Msg("ok")

    flaky = FlakyLLM()
    with caplog.at_level(logging.WARNING, logger="app.llm"):
        result = await llm_module.ainvoke_with_retry(flaky, [("human", "hi")])

    assert result.content == "ok"
    assert flaky.calls == 3
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("重试" in r.getMessage() for r in warnings)


async def test_ainvoke_with_retry_raises_after_exhausted_retries(caplog):
    class AlwaysFailingLLM:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, messages):
            self.calls += 1
            raise _conn_error()

    failing = AlwaysFailingLLM()
    with caplog.at_level(logging.WARNING, logger="app.llm"):
        with pytest.raises(openai.APIConnectionError):
            await llm_module.ainvoke_with_retry(failing, [("human", "hi")])

    assert failing.calls == llm_module.LLM_MAX_RETRIES + 1
    assert any("仍失败" in r.getMessage() for r in caplog.records)


async def test_ainvoke_with_retry_does_not_retry_non_retryable_errors():
    class AuthFailingLLM:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, messages):
            self.calls += 1
            raise RuntimeError("authentication failed")

    failing = AuthFailingLLM()
    with pytest.raises(RuntimeError):
        await llm_module.ainvoke_with_retry(failing, [("human", "hi")])
    assert failing.calls == 1


# --------------------------------------------------------------- FR-2 (AC-3)


class _Chunk:
    def __init__(self, text):
        self.content = text
        self.usage_metadata = None
        self.additional_kwargs = {}
        self.response_metadata = {}
        self.id = None
        self.tool_calls = []

    def __add__(self, other):
        return _Chunk(self.content + getattr(other, "content", ""))


class _FlakyStreamLLM:
    """First astream call raises before producing any chunk; second succeeds."""

    def __init__(self):
        self.calls = 0

    def astream(self, messages):
        self.calls += 1
        return self._gen(self.calls)

    async def _gen(self, call):
        if call == 1:
            raise _conn_error()
        yield _Chunk("hello ")
        yield _Chunk("world")


async def test_stream_reply_retries_before_first_chunk():
    llm = _FlakyStreamLLM()
    tokens = []

    async def emit(event_type, payload=None):
        if event_type == "token":
            tokens.append(payload["delta"])

    response, usage = await agent_module._stream_reply(llm, [], emit)

    assert response.content == "hello world"
    assert llm.calls == 2
    assert tokens == ["hello ", "world"]
    assert usage == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


class _MidStreamFailLLM:
    """Produces one chunk, then fails with a transient error."""

    def __init__(self):
        self.calls = 0

    def astream(self, messages):
        self.calls += 1
        return self._gen()

    async def _gen(self):
        yield _Chunk("partial")
        raise _conn_error()


async def test_stream_reply_does_not_retry_after_first_chunk():
    llm = _MidStreamFailLLM()

    async def emit(event_type, payload=None):
        return None

    with pytest.raises(openai.APIConnectionError):
        await agent_module._stream_reply(llm, [], emit)
    assert llm.calls == 1


# --------------------------------------------------------------- FR-4 (AC-4)


def test_unhandled_exception_returns_500_with_logged_stack(caplog):
    async def boom():
        raise RuntimeError("boom-spec-034")

    route_path = "/api/__test_boom_spec_034"
    fastapi_app.add_api_route(route_path, boom, methods=["GET"])
    added = [r for r in fastapi_app.routes if getattr(r, "path", None) == route_path]
    try:
        with TestClient(fastapi_app, raise_server_exceptions=False) as client:
            with caplog.at_level(logging.ERROR, logger="app.app"):
                resp = client.get(route_path)
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Internal server error"}
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("未处理异常" in r.getMessage() for r in error_records)
        assert any(r.exc_info for r in caplog.records)
    finally:
        for route in added:
            if route in fastapi_app.routes:
                fastapi_app.routes.remove(route)


# --------------------------------------------------------------- FR-5 (AC-5)


def test_all_chatopenai_constructions_set_request_timeout():
    offenders = []
    for path in BACKEND_APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name != "ChatOpenAI":
                continue
            keywords = {kw.arg for kw in node.keywords}
            if "request_timeout" not in keywords:
                offenders.append(
                    f"{path.relative_to(BACKEND_APP_DIR)}:{node.lineno}"
                )
    assert offenders == []


async def test_build_llm_instance_has_request_timeout(monkeypatch):
    monkeypatch.setattr(agent_module, "get_effective_config", lambda: {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "model": "gpt-4o-mini",
    })
    llm = agent_module.build_llm()
    assert float(llm.request_timeout) == agent_module.LLM_REQUEST_TIMEOUT_SECONDS


# --------------------------------------------------------------- FR-3 (AC-6)


async def test_agent_run_logs_start_and_finish(monkeypatch, caplog):
    class FakeLLM:
        async def ainvoke(self, messages):
            return AIMessage(content="done")

        async def astream(self, messages):
            yield AIMessageChunk(content="done")

    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: FakeLLM())

    with caplog.at_level(logging.INFO, logger="app.agent.agent"):
        result = await agent_module.run_chat(None, "你好")

    assert result["reply"] == "done"
    messages = [r.getMessage() for r in caplog.records]
    assert any("Agent run 开始" in m for m in messages)
    assert any("Agent run 结束" in m for m in messages)
