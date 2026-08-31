import json

import pytest
from langchain_core.messages import AIMessage

from app import config, database
from app.agent import agent as agent_module
from app.agent import permissions, sessions
from app.agent.tools import DANGEROUS_TOOLS


@pytest.fixture(autouse=True)
def _setup_env(tmp_path, monkeypatch):
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


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        return self.responses.pop(0)


def _reply(text):
    return AIMessage(content=text)


def _tool_call(name, args, call_id):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )


def _recv_until(ws, event_type, limit=100):
    events = []
    for _ in range(limit):
        event = ws.receive_json()
        events.append(event)
        if event.get("type") == event_type:
            return events
    raise AssertionError(f"did not receive {event_type}; got {events}")


def _eval(tool, args, mode, session_allows=None):
    return permissions.evaluate(
        tool,
        args,
        mode=mode,
        whitelist=permissions.DEFAULT_COMMAND_WHITELIST,
        session_allows=session_allows,
    )


ALL_MODES = ["conservative", "standard", "full"]


# ---------------------------------------------------------------------------
# AC-1: evaluation matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ALL_MODES)
def test_delete_server_always_ask(mode):
    assert _eval("delete_server", {}, mode) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf /data",
        "rm -rf ~/work",
        "RM -RF /tmp/x",
        "shutdown now",
        "dd if=/dev/zero of=/dev/sda",
    ],
)
@pytest.mark.parametrize("mode", ALL_MODES)
def test_forbidden_commands_always_ask(mode, command):
    assert _eval("run_command", {"command": command}, mode) == "ask"


@pytest.mark.parametrize(
    "command",
    ["rm -rf /", "shutdown now", "dd if=/dev/zero of=/dev/sda"],
)
def test_run_shell_command_forbidden_in_standard(command):
    assert _eval("run_shell_command", {"command": command}, "standard") == "ask"


def test_standard_mode_matrix():
    assert _eval("run_python_code", {"code": "print(1)"}, "standard") == "allow"
    assert _eval("run_shell_command", {"command": "echo hi"}, "standard") == "allow"
    assert _eval("run_command", {"command": "nvidia-smi"}, "standard") == "allow"
    assert _eval("run_command", {"command": "pip install x"}, "standard") == "ask"
    assert _eval("deploy_code", {}, "standard") == "ask"
    assert _eval("create_server", {}, "standard") == "ask"


def test_conservative_all_dangerous_tools_ask():
    for tool in DANGEROUS_TOOLS:
        args = {"command": "nvidia-smi"} if tool in permissions.COMMAND_TOOLS else {}
        assert _eval(tool, args, "conservative") == "ask", tool


def test_full_mode_allows_all_except_safety_floor():
    for tool in DANGEROUS_TOOLS:
        args = {"command": "nvidia-smi"} if tool in permissions.COMMAND_TOOLS else {}
        expected = "ask" if tool in permissions.FORBIDDEN_TOOLS else "allow"
        assert _eval(tool, args, "full") == expected, tool
    assert _eval("run_command", {"command": "rm -rf /"}, "full") == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "nvidia-smi",
        "nvidia-smi -L",
        "pwd",
        "whoami",
        "ls",
        "ls -la /tmp",
        "cat /etc/hostname",
        "head -n 5 f.txt",
        "tail -n 5 f.txt",
        "df -h",
        "free -g",
        "du -sh .",
        "ps aux",
        "which python",
        "echo hello",
        "python train.py --version",
        "pip list",
        "pip show torch",
        "pip freeze",
        "git status",
        "git log --oneline",
        "git diff HEAD~1",
        "git branch",
        "git show abc123",
        "git remote -v",
    ],
)
def test_standard_whitelist_allows_read_only_commands(command):
    assert _eval("run_command", {"command": command}, "standard") == "allow"


@pytest.mark.parametrize(
    "command",
    [
        "pip install torch",
        "apt update",
        "rm file.txt",
        "git push origin main",
        "nvidiasmi",
    ],
)
def test_standard_whitelist_deny_cases(command):
    assert _eval("run_command", {"command": command}, "standard") == "ask"


# ---------------------------------------------------------------------------
# AC-3: composite operators never match the whitelist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "nvidia-smi; ls",
        "ls && nvidia-smi",
        "ls || whoami",
        "cat /etc/passwd | wc -l",
    ],
)
def test_composite_commands_never_match_whitelist(command):
    assert not permissions.matches_whitelist(
        command, permissions.DEFAULT_COMMAND_WHITELIST
    )
    assert _eval("run_command", {"command": command}, "standard") == "ask"


# ---------------------------------------------------------------------------
# AC-2: session-level allows
# ---------------------------------------------------------------------------


def test_session_allow_overrides_mode_but_not_safety_floor():
    assert (
        _eval(
            "run_command",
            {"command": "pip install x"},
            "standard",
            session_allows={"run_command"},
        )
        == "allow"
    )
    assert (
        _eval("deploy_code", {}, "conservative", session_allows={"deploy_code"})
        == "allow"
    )
    assert (
        _eval("deploy_code", {}, "conservative", session_allows={"run_command"})
        == "ask"
    )
    assert (
        _eval("delete_server", {}, "standard", session_allows={"delete_server"})
        == "ask"
    )
    assert (
        _eval(
            "run_command",
            {"command": "shutdown now"},
            "conservative",
            session_allows={"run_command"},
        )
        == "ask"
    )


def test_session_allow_isolated_between_sessions():
    first = sessions.create_session()
    second = sessions.create_session()
    first.allowed_tools.add("run_command")
    assert (
        _eval(
            "run_command",
            {"command": "pip install x"},
            "standard",
            session_allows=first.allowed_tools,
        )
        == "allow"
    )
    assert (
        _eval(
            "run_command",
            {"command": "pip install x"},
            "standard",
            session_allows=second.allowed_tools,
        )
        == "ask"
    )


async def test_approve_scope_session_allows_rest_of_session(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c1"),
        _reply("第一次完成。"),
        _tool_call("run_command", {"server_id": "s1", "command": "apt install y"}, "c2"),
        _reply("第二次完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    first = await agent_module.run_chat(None, "安装 x")
    assert first["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s1", "command": "pip install x"},
        "forbidden": False,
    }
    assert sessions.get_session(first["session_id"]).allowed_tools == set()

    second = await agent_module.run_approve(first["session_id"], True, scope="session")
    assert second["pending_approval"] is None
    assert sessions.get_session(first["session_id"]).allowed_tools == {"run_command"}

    third = await agent_module.run_chat(first["session_id"], "再装 y")
    assert third["pending_approval"] is None
    assert executed[-1] == ("run_command", {"server_id": "s1", "command": "apt install y"})


async def test_approve_scope_session_isolated_and_not_persisted(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c1"),
        _reply("完成。"),
        _tool_call("run_command", {"server_id": "s2", "command": "pip install x"}, "c2"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    first = await agent_module.run_chat(None, "安装 x")
    await agent_module.run_approve(first["session_id"], True, scope="session")

    other = await agent_module.run_chat(None, "另一个会话安装 x")
    assert other["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s2", "command": "pip install x"},
        "forbidden": False,
    }
    assert sessions.get_session(other["session_id"]).allowed_tools == set()
    assert len(executed) == 1

    sessions._cache.clear()
    revived = sessions.get_session(first["session_id"])
    assert revived is not None
    assert revived.allowed_tools == set()


async def test_session_scope_cannot_bypass_safety_floor(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "rm -rf /"}, "c1"),
        _reply("已执行。"),
        _tool_call("run_command", {"server_id": "s1", "command": "shutdown now"}, "c2"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    first = await agent_module.run_chat(None, "删库")
    session_id = first["session_id"]
    await agent_module.run_approve(session_id, True, scope="session")
    assert sessions.get_session(session_id).allowed_tools == {"run_command"}

    second = await agent_module.run_chat(session_id, "关机")
    assert second["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s1", "command": "shutdown now"},
        "forbidden": True,
    }
    assert len(executed) == 1


async def test_approve_default_scope_is_once_only(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c1"),
        _reply("完成。"),
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c2"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    first = await agent_module.run_chat(None, "安装 x")
    session_id = first["session_id"]
    await agent_module.run_approve(session_id, True)
    assert sessions.get_session(session_id).allowed_tools == set()

    second = await agent_module.run_chat(session_id, "再装一次")
    assert second["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s1", "command": "pip install x"},
        "forbidden": False,
    }
    assert len(executed) == 1


async def test_ws_approve_scope_session_and_invalid_scope_ignored(client, monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c1"),
        _reply("完成。"),
        _tool_call("deploy_code", {}, "c2"),
        _reply("部署完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    with client.websocket_connect("/api/agent/ws") as ws:
        ws.send_json({"type": "chat", "message": "安装 x"})
        session_id = ws.receive_json()["session_id"]
        _recv_until(ws, "pending_approval")
        ws.send_json({"type": "approve", "approve": True, "scope": "session"})
        _recv_until(ws, "done")
        assert sessions.get_session(session_id).allowed_tools == {"run_command"}

        ws.send_json({"type": "chat", "message": "部署"})
        _recv_until(ws, "pending_approval")
        ws.send_json({"type": "approve", "approve": True, "scope": "forever"})
        _recv_until(ws, "done")

    allowed = sessions.get_session(session_id).allowed_tools
    assert allowed == {"run_command"}
    assert "deploy_code" not in allowed


# ---------------------------------------------------------------------------
# AC-4: persistence fallback
# ---------------------------------------------------------------------------


def test_missing_permissions_file_defaults_and_creates():
    path = permissions._permissions_path()
    assert not path.exists()
    state = permissions.load()
    assert state["mode"] == "standard"
    assert state["command_whitelist"] == permissions.DEFAULT_COMMAND_WHITELIST
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["mode"] == "standard"


def test_corrupt_permissions_file_falls_back_and_rebuilds():
    path = permissions._permissions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{corrupt json!!", encoding="utf-8")
    state = permissions.load()
    assert state["mode"] == "standard"
    assert state["command_whitelist"] == permissions.DEFAULT_COMMAND_WHITELIST
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["mode"] == "standard"


def test_invalid_mode_in_file_normalizes_to_default():
    path = permissions._permissions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"mode": "yolo", "command_whitelist": "not-a-list"}),
        encoding="utf-8",
    )
    state = permissions.load()
    assert state["mode"] == "standard"
    assert state["command_whitelist"] == permissions.DEFAULT_COMMAND_WHITELIST


def test_save_normalizes_whitelist_and_validates_mode():
    state = permissions.save("full", [123, None, " nvidia-smi* ", "nvidia-smi*", ""])
    assert state["command_whitelist"] == ["nvidia-smi*"]
    assert permissions.load()["mode"] == "full"
    with pytest.raises(ValueError):
        permissions.save("yolo", [])


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / AC-7: permissions API
# ---------------------------------------------------------------------------


def test_api_get_permissions_defaults(client):
    resp = client.get("/api/agent/permissions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "standard"
    assert data["command_whitelist"] == permissions.DEFAULT_COMMAND_WHITELIST


def test_api_put_permissions_validation(client):
    resp = client.put(
        "/api/agent/permissions", json={"mode": "yolo", "command_whitelist": []}
    )
    assert resp.status_code == 400

    resp = client.put(
        "/api/agent/permissions",
        json={
            "mode": "conservative",
            "command_whitelist": [123, None, "nvidia-smi*", "nvidia-smi*", ""],
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"mode": "conservative", "command_whitelist": ["nvidia-smi*"]}

    assert client.get("/api/agent/permissions").json() == {
        "mode": "conservative",
        "command_whitelist": ["nvidia-smi*"],
    }


def test_api_reset_permissions(client):
    client.put(
        "/api/agent/permissions", json={"mode": "full", "command_whitelist": ["x*"]}
    )
    resp = client.post("/api/agent/permissions/reset")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "standard"
    assert resp.json()["command_whitelist"] == permissions.DEFAULT_COMMAND_WHITELIST
    assert client.get("/api/agent/permissions").json() == resp.json()


async def test_api_mode_change_takes_effect_next_tool_call(client, monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c1"),
        _reply("第一次完成。"),
        _tool_call("run_command", {"server_id": "s1", "command": "pip install x"}, "c2"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    resp = client.put(
        "/api/agent/permissions", json={"mode": "full", "command_whitelist": []}
    )
    assert resp.status_code == 200
    first = await agent_module.run_chat(None, "安装 x")
    assert first["pending_approval"] is None
    assert executed == [("run_command", {"server_id": "s1", "command": "pip install x"})]

    client.put(
        "/api/agent/permissions", json={"mode": "conservative", "command_whitelist": []}
    )
    second = await agent_module.run_chat(first["session_id"], "再装一次")
    assert second["pending_approval"] == {
        "tool": "run_command",
        "args": {"server_id": "s1", "command": "pip install x"},
        "forbidden": False,
    }
    assert len(executed) == 1
