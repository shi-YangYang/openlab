import json

import pytest
from langchain_core.messages import AIMessage

from app import config, database
from app.agent import agent as agent_module
from app.agent import sessions, tools as agent_tools


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
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

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        return self.responses.pop(0)


def _tool_call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


# ---------------------------------------------------------------------------
# History query tools (FR-1)
# ---------------------------------------------------------------------------


async def test_list_search_history_tool():
    database.save_search_history("attention", "keyword", [{"arxiv_id": "1"}])
    res = await agent_tools.execute_tool("list_search_history", {})
    assert isinstance(res, list)
    assert res[0]["query"] == "attention"
    assert res[0]["mode"] == "keyword"
    assert res[0]["paper_count"] == 1


async def test_list_innovations_tool():
    content = json.dumps(
        [{"title": "t", "description": "d", "basis": [], "expected_contribution": ""}]
    )
    database.insert_innovation(["1"], content, "zh", status="done")
    res = await agent_tools.execute_tool("list_innovations", {})
    assert isinstance(res, list)
    assert res[0]["innovation_count"] == 1
    assert res[0]["status"] == "done"
    assert "content" not in res[0]


async def test_list_reviews_tool():
    database.insert_review(["1", "2"], json.dumps({"summary": "s"}), "zh", status="done")
    res = await agent_tools.execute_tool("list_reviews", {})
    assert isinstance(res, list)
    assert res[0]["arxiv_ids"] == ["1", "2"]
    assert res[0]["status"] == "done"


async def test_list_experiments_tool():
    database.insert_experiment("papers", None, ["1"], json.dumps([]), "zh", status="done")
    res = await agent_tools.execute_tool("list_experiments", {})
    assert isinstance(res, list)
    assert res[0]["source_type"] == "papers"
    assert res[0]["status"] == "done"


# ---------------------------------------------------------------------------
# Server CRUD + deploy upload tools (FR-2/FR-3)
# ---------------------------------------------------------------------------


async def test_server_crud_tools_redacted():
    created = await agent_tools.execute_tool(
        "create_server",
        {"name": "gpu01", "host": "10.0.0.1", "username": "root", "password": "secret-pw"},
    )
    assert created["id"]
    assert created["name"] == "gpu01"
    assert created["has_password"] is True
    assert created["has_key"] is False
    assert "password" not in created
    assert "secret-pw" not in json.dumps(created)

    updated = await agent_tools.execute_tool(
        "update_server", {"server_id": created["id"], "name": "gpu02", "port": 2222}
    )
    assert updated["name"] == "gpu02"
    assert updated["port"] == 2222
    assert "password" not in updated

    deleted = await agent_tools.execute_tool("delete_server", {"server_id": created["id"]})
    assert deleted["status"] == "deleted"

    not_found = await agent_tools.execute_tool("delete_server", {"server_id": created["id"]})
    assert "error" in not_found


async def test_deploy_upload_tool(monkeypatch):
    created = await agent_tools.execute_tool(
        "create_server", {"name": "s", "host": "h", "username": "u"}
    )
    captured = {}

    def fake_upload(server, local_path, remote_path, timeout=60.0):
        captured["local"] = local_path
        captured["remote"] = remote_path
        return {"message": "上传完成", "files": 1}

    monkeypatch.setattr("app.ssh.upload", fake_upload)

    res = await agent_tools.execute_tool(
        "deploy_upload",
        {"server_id": created["id"], "local_path": "C:/code/app", "remote_path": "/home/u/app"},
    )
    assert res["files"] == 1
    assert captured["local"] == "C:/code/app"
    assert captured["remote"] == "/home/u/app"


# ---------------------------------------------------------------------------
# Dynamic tools (FR-4/FR-5)
# ---------------------------------------------------------------------------


async def test_run_python_code_tool():
    agent_tools.set_session_context("s1")
    res = await agent_tools.execute_tool("run_python_code", {"code": "print('py-ok')"})
    assert res["returncode"] == 0
    assert "py-ok" in res["stdout"]


async def test_run_shell_command_tool():
    agent_tools.set_session_context("s1")
    res = await agent_tools.execute_tool("run_shell_command", {"command": "echo sh-ok"})
    assert res["returncode"] == 0
    assert "sh-ok" in res["stdout"]


def test_dangerous_tools_include_new_ones():
    for name in (
        "run_python_code",
        "run_shell_command",
        "create_server",
        "update_server",
        "delete_server",
        "deploy_upload",
    ):
        assert agent_tools.is_dangerous(name)
    for name in ("list_search_history", "list_innovations", "list_reviews", "list_experiments"):
        assert not agent_tools.is_dangerous(name)


def test_new_tools_are_registered():
    names = {t.name for t in agent_tools.get_tools()}
    for expected in (
        "list_search_history",
        "list_innovations",
        "list_reviews",
        "list_experiments",
        "create_server",
        "update_server",
        "delete_server",
        "deploy_upload",
        "run_python_code",
        "run_shell_command",
    ):
        assert expected in names


# ---------------------------------------------------------------------------
# Status subdivision (FR-8)
# ---------------------------------------------------------------------------


async def test_status_thinking_executing_cleared(monkeypatch):
    statuses = []
    monkeypatch.setattr(agent_module, "set_status", lambda sid, s: statuses.append(s))

    async def fake_execute(name, args):
        return {"count": 1, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)

    llm = FakeLLM([
        _tool_call("search_papers", {"query": "x"}, "c1"),
        AIMessage(content="完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda: llm)

    await agent_module.run_chat(None, "搜索")

    assert "thinking" in statuses
    assert any(s.startswith("executing:search_papers") for s in statuses)
    assert statuses[-1] == ""


def test_set_status_persists_and_detail_returns_it(client):
    created = client.post("/api/agent/sessions", json={}).json()

    sessions.set_status(created["id"], "thinking")
    detail = client.get(f"/api/agent/sessions/{created['id']}").json()
    assert detail["status"] == "thinking"

    sessions.set_status(created["id"], "executing:search_papers (第2步)")
    detail = client.get(f"/api/agent/sessions/{created['id']}").json()
    assert detail["status"] == "executing:search_papers (第2步)"

    sessions.set_status(created["id"], "")
    detail = client.get(f"/api/agent/sessions/{created['id']}").json()
    assert detail["status"] == ""


def test_list_sessions_includes_status(client):
    created = client.post("/api/agent/sessions", json={}).json()
    sessions.set_status(created["id"], "thinking")
    listing = client.get("/api/agent/sessions").json()
    item = next(x for x in listing if x["id"] == created["id"])
    assert item["status"] == "thinking"


def test_migrate_adds_status_column(tmp_path, monkeypatch):
    import sqlite3

    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    data_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(data_dir / "openlab.db"))
    conn.execute("DROP TABLE IF EXISTS agent_sessions")
    conn.execute(
        "CREATE TABLE agent_sessions ("
        "id TEXT PRIMARY KEY, title TEXT DEFAULT '', created_at TEXT, updated_at TEXT, "
        "messages TEXT DEFAULT '[]', running INTEGER DEFAULT 0)"
    )
    conn.commit()
    conn.close()

    database.init_db()

    conn = database._connect()
    try:
        names = [
            r["name"] for r in conn.execute("PRAGMA table_info(agent_sessions)").fetchall()
        ]
    finally:
        conn.close()
    assert "status" in names
