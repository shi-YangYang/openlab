"""spec-033 backend tests: startup running-state recovery + history rebuild."""
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app import database
from app.agent import sessions
from app.app import app


def _multi_turn_messages():
    """Human -> AI(text+tools) -> Tool -> AI(text+tools) -> Tool -> AI(text)."""
    return [
        HumanMessage("查一下注意力机制相关论文"),
        AIMessage(
            "我先搜索相关论文",
            additional_kwargs={"ts": "2026-08-30 10:00:00", "model": "deepseek-chat"},
            tool_calls=[
                {"name": "search_papers", "args": {"query": "attention"}, "id": "call_1"}
            ],
        ),
        ToolMessage("找到 3 篇论文", tool_call_id="call_1"),
        AIMessage(
            "我继续下载第一篇",
            tool_calls=[
                {
                    "name": "download_paper",
                    "args": {"arxiv_id": "2401.00001"},
                    "id": "call_2",
                }
            ],
        ),
        ToolMessage("执行失败: 网络超时", tool_call_id="call_2"),
        AIMessage(
            "已为你整理 3 篇论文，第一篇下载失败。",
            additional_kwargs={"ts": "2026-08-30 10:02:30", "model": "deepseek-chat"},
        ),
    ]


def test_startup_resets_stale_running_state(client):
    first = client.post("/api/agent/sessions", json={}).json()
    second = client.post("/api/agent/sessions", json={}).json()
    database.set_agent_session_running(first["id"], True)
    database.set_agent_session_status(first["id"], "thinking")
    database.set_agent_session_status(second["id"], "interrupted")

    # Simulate a restart: lifespan startup must clear the zombie state (AC-1).
    with TestClient(app) as restarted:
        for session_id in (first["id"], second["id"]):
            detail = restarted.get(f"/api/agent/sessions/{session_id}").json()
            assert detail["running"] is False
            assert detail["status"] == ""


def test_normalize_history_intermediate_and_tool_calls():
    items = sessions.normalize_history(_multi_turn_messages())

    assert [item["role"] for item in items] == [
        "user",
        "assistant",
        "assistant",
        "assistant",
    ]
    user, first, second, final = items

    assert user["intermediate"] is False
    assert user["toolCalls"] == []

    assert first["intermediate"] is True
    assert first["content"] == "我先搜索相关论文"
    assert first["toolCalls"] == [
        {
            "tool": "search_papers",
            "args": {"query": "attention"},
            "result": "找到 3 篇论文",
            "status": "done",
        }
    ]
    assert first["time"] == "2026-08-30 10:00"
    assert first["model"] == "deepseek-chat"

    assert second["intermediate"] is True
    assert second["toolCalls"] == [
        {
            "tool": "download_paper",
            "args": {"arxiv_id": "2401.00001"},
            "result": "执行失败: 网络超时",
            "status": "error",
        }
    ]
    assert second["time"] is None
    assert second["model"] is None

    assert final["intermediate"] is False
    assert final["toolCalls"] == []
    assert final["content"] == "已为你整理 3 篇论文，第一篇下载失败。"
    assert final["time"] == "2026-08-30 10:02"


def test_normalize_history_keeps_empty_text_ai_with_tools():
    messages = [
        HumanMessage("看看目录里有什么"),
        AIMessage(
            "",
            tool_calls=[
                {"name": "list_files", "args": {"path": "/tmp"}, "id": "call_a"}
            ],
        ),
        ToolMessage("a.txt, b.txt", tool_call_id="call_a"),
        AIMessage("目录里有两个文件"),
    ]
    items = sessions.normalize_history(messages)

    assert [item["role"] for item in items] == ["user", "assistant", "assistant"]
    tool_only = items[1]
    assert tool_only["content"] == ""
    assert tool_only["intermediate"] is True
    assert tool_only["toolCalls"] == [
        {
            "tool": "list_files",
            "args": {"path": "/tmp"},
            "result": "a.txt, b.txt",
            "status": "done",
        }
    ]
    assert items[2]["intermediate"] is False


def test_normalize_history_missing_tool_result_is_error():
    messages = [
        HumanMessage("q"),
        AIMessage(
            "调用工具", tool_calls=[{"name": "t", "args": {}, "id": "call_missing"}]
        ),
        AIMessage("最终回复"),
    ]
    items = sessions.normalize_history(messages)
    assert items[1]["toolCalls"] == [
        {"tool": "t", "args": {}, "result": "", "status": "error"}
    ]
    assert items[1]["intermediate"] is True
    assert items[2]["intermediate"] is False


def test_normalize_history_rejected_tool_call_is_error():
    messages = [
        HumanMessage("删掉服务器上的文件"),
        AIMessage(
            "需要先确认",
            tool_calls=[{"name": "delete_file", "args": {"path": "x"}, "id": "call_r"}],
        ),
        ToolMessage("用户拒绝了该操作，未执行。", tool_call_id="call_r"),
        AIMessage("好的，已取消。"),
    ]
    items = sessions.normalize_history(messages)
    assert items[1]["toolCalls"] == [
        {
            "tool": "delete_file",
            "args": {"path": "x"},
            "result": "用户拒绝了该操作，未执行。",
            "status": "error",
        }
    ]


def test_normalize_history_legacy_messages_compatible():
    messages = [HumanMessage("你好"), AIMessage("回复内容")]
    items = sessions.normalize_history(messages)
    assert items == [
        {
            "role": "user",
            "content": "你好",
            "time": None,
            "model": None,
            "intermediate": False,
            "toolCalls": [],
        },
        {
            "role": "assistant",
            "content": "回复内容",
            "time": None,
            "model": None,
            "intermediate": False,
            "toolCalls": [],
        },
    ]


def test_normalize_history_intermediate_across_user_segments():
    messages = [
        HumanMessage("第一问"),
        AIMessage("第一答"),
        HumanMessage("第二问"),
        AIMessage("先查一下", tool_calls=[{"name": "t", "args": {}, "id": "c"}]),
        ToolMessage("结果", tool_call_id="c"),
        AIMessage("第二答"),
    ]
    items = sessions.normalize_history(messages)
    # Only the tool-call turn of the last segment is process content; the
    # final reply of each earlier segment stays a normal message.
    assert [item["intermediate"] for item in items] == [
        False,
        False,
        False,
        True,
        False,
    ]


def test_normalize_history_drops_empty_ai_without_tools():
    messages = [HumanMessage("q"), AIMessage(""), AIMessage("回答")]
    items = sessions.normalize_history(messages)
    assert [item["role"] for item in items] == ["user", "assistant"]


def test_session_detail_returns_full_history_structure(client):
    created = client.post("/api/agent/sessions", json={}).json()
    session = sessions.get_session(created["id"])
    assert session is not None
    session.messages = _multi_turn_messages()
    sessions.save_messages(session)

    detail = client.get(f"/api/agent/sessions/{created['id']}").json()
    for key in (
        "id",
        "title",
        "created_at",
        "updated_at",
        "running",
        "status",
        "messages",
        "usage",
    ):
        assert key in detail
    assert detail["running"] is False
    assert detail["status"] == ""
    assert len(detail["messages"]) == 4
    for item in detail["messages"]:
        assert set(item.keys()) == {
            "role",
            "content",
            "time",
            "model",
            "intermediate",
            "toolCalls",
        }
    assert detail["messages"][1]["toolCalls"][0]["tool"] == "search_papers"
    assert detail["usage"]["message_count"] == 4
