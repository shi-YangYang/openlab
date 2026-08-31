"""SQLite-backed agent session storage.

A session holds the LangChain message history (persisted to the ``agent_sessions``
table) and any pending (dangerous) tool call awaiting user approval. The pending
approval state is persisted to the ``agent_sessions.pending`` column (spec-035
FR-2) so it survives a restart; the in-process cache keeps it handy across
requests (chat -> approve), while the conversation history lives in the DB.
"""
import json
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)

from .. import database
from .sandbox import clear_all_sandboxes, delete_sandbox


class Session:
    def __init__(self, session_id: str, title: str = "") -> None:
        self.session_id = session_id
        self.title = title
        self.messages: List[BaseMessage] = []
        self.pending: Optional[Dict[str, Any]] = None
        # Session-scoped tool allowlist (spec-032 FR-7): filled when the user
        # picks "allow for this session" in the approval modal. In-memory only,
        # so it resets on restart and is isolated per session.
        self.allowed_tools: set = set()


# In-process cache so the transient ``pending`` state survives across requests
# (chat -> approve). The persisted message history is the DB's responsibility.
_cache: Dict[str, Session] = {}


def _serialize(messages: List[BaseMessage]) -> str:
    return json.dumps([message_to_dict(m) for m in messages], ensure_ascii=False)


def _deserialize(raw: Optional[str]) -> List[BaseMessage]:
    if not raw:
        return []
    try:
        return messages_from_dict(json.loads(raw))
    except (ValueError, TypeError, KeyError, AttributeError):
        return []


def _to_session(record: Dict[str, Any]) -> Session:
    session = Session(record["id"], record.get("title") or "")
    session.messages = _deserialize(record.get("messages"))
    session.pending = _deserialize_pending(record.get("pending"))
    return session


def _deserialize_pending(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) and data.get("tool_calls") else None


def set_pending(session: Session, pending: Optional[Dict[str, Any]]) -> None:
    """Update the session's pending approval state and persist it (FR-2)."""
    session.pending = pending
    database.set_agent_session_pending(session.session_id, pending)


def create_session(session_id: Optional[str] = None, title: Optional[str] = None) -> Session:
    new_id = session_id or uuid.uuid4().hex
    record = database.create_agent_session(new_id, title or "")
    session = _to_session(record)
    _cache[session.session_id] = session
    return session


def get_or_create(session_id: Optional[str] = None) -> Session:
    if session_id and session_id in _cache:
        return _cache[session_id]
    if session_id:
        record = database.get_agent_session(session_id)
        if record is not None:
            session = _to_session(record)
            _cache[session_id] = session
            return session
    return create_session(session_id)


def get_session(session_id: str) -> Optional[Session]:
    if session_id in _cache:
        return _cache[session_id]
    record = database.get_agent_session(session_id)
    if record is None:
        return None
    session = _to_session(record)
    _cache[session_id] = session
    return session


def list_sessions() -> List[Dict[str, Any]]:
    return database.list_agent_sessions()


def update_title(session_id: str, title: str) -> Optional[Dict[str, Any]]:
    record = database.update_agent_session_title(session_id, title)
    if record is not None and session_id in _cache:
        _cache[session_id].title = record["title"]
    return record


def delete_session(session_id: str) -> bool:
    _cache.pop(session_id, None)
    deleted = database.delete_agent_session(session_id)
    if deleted:
        delete_sandbox(session_id)
    return deleted


def save_messages(session: Session) -> None:
    database.save_agent_messages(session.session_id, _serialize(session.messages))


def set_running(session_id: str, running: bool) -> None:
    database.set_agent_session_running(session_id, running)


def set_status(session_id: str, status: str) -> None:
    database.set_agent_session_status(session_id, status)


def reset_running_states() -> None:
    """Clear zombie running/status flags of all sessions (spec-033 FR-1).

    Called once during application startup: a restart means any previously
    running task is gone, so residual ``running=1`` rows are stale state left
    by a crash or kill, not live work.
    """
    database.reset_agent_session_running()


def _content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _tool_status(result: str) -> str:
    """Infer tool call status from the persisted ToolMessage content.

    ``agent.py`` stores failures as ``执行失败: ...`` and user-rejected calls
    as ``用户拒绝了该操作，未执行。``; anything else counts as done.
    """
    if result.startswith("执行失败") or result.startswith("用户拒绝"):
        return "error"
    return "done"


def _rebuild_tool_calls(
    tool_calls: Any, tool_messages: Dict[Any, ToolMessage]
) -> List[Dict[str, Any]]:
    """Rebuild UI-facing tool call entries from an AIMessage's ``tool_calls``.

    Each entry is ``{tool, args, result, status}``; ``args`` keeps the original
    dict. The result comes from the ToolMessage matching ``tool_call_id`` — a
    missing result (crash mid-run) or a rejected call yields ``status=error``.
    """
    rebuilt: List[Dict[str, Any]] = []
    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        tool_message = tool_messages.get(call.get("id"))
        if tool_message is None:
            result, status = "", "error"
        else:
            result = _content_to_str(tool_message.content)
            status = _tool_status(result)
        args = call.get("args")
        rebuilt.append(
            {
                "tool": call.get("name"),
                "args": args if isinstance(args, dict) else {},
                "result": result,
                "status": status,
            }
        )
    return rebuilt


def normalize_history(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert stored LangChain messages into a compact UI-friendly history.

    System and tool messages are omitted as standalone items; tool activity is
    re-attached to the AI message that issued it via ``toolCalls`` entries
    (spec-033 FR-4). AI messages that carry tool calls but no text are kept so
    tool cards survive a reload. Each item carries ``intermediate`` (True for
    process turns: any AI message with tool calls, or a non-final AI message
    following the same user message) plus the optional ``time`` (from the
    persisted ``ts`` kwarg, ``YYYY-MM-DD HH:mm``) and ``model`` metadata; both
    are ``None`` when absent so old sessions and compacted summary messages
    stay compatible.
    """
    tool_messages: Dict[Any, ToolMessage] = {}
    for message in messages:
        if isinstance(message, ToolMessage):
            tool_messages[getattr(message, "tool_call_id", None)] = message

    items: List[Dict[str, Any]] = []
    for message in messages:
        if isinstance(message, (SystemMessage, ToolMessage)):
            continue
        content = _content_to_str(getattr(message, "content", "")).strip()
        kwargs = getattr(message, "additional_kwargs", None)
        kwargs = kwargs if isinstance(kwargs, dict) else {}
        ts = kwargs.get("ts")
        time_str = ts[:16] if isinstance(ts, str) and len(ts) >= 16 else None
        model = kwargs.get("model")
        if not isinstance(model, str) or not model:
            model = None
        if isinstance(message, HumanMessage):
            items.append(
                {
                    "role": "user",
                    "content": content,
                    "time": time_str,
                    "model": model,
                    "intermediate": False,
                    "toolCalls": [],
                }
            )
        elif isinstance(message, AIMessage):
            tool_calls = _rebuild_tool_calls(
                getattr(message, "tool_calls", None), tool_messages
            )
            if not content and not tool_calls:
                continue
            items.append(
                {
                    "role": "assistant",
                    "content": content,
                    "time": time_str,
                    "model": model,
                    "intermediate": bool(tool_calls),
                    "toolCalls": tool_calls,
                }
            )

    # The last AI message of each user segment is the final reply; the earlier
    # AI messages of that segment are process turns (spec-033 FR-4).
    segment_positions: List[int] = []
    for index, item in enumerate(items):
        if item["role"] == "user":
            for pos in segment_positions[:-1]:
                items[pos]["intermediate"] = True
            segment_positions = []
        else:
            segment_positions.append(index)
    for pos in segment_positions[:-1]:
        items[pos]["intermediate"] = True
    return items


def get_raw_messages(session_id: str) -> Optional[List[BaseMessage]]:
    """Return the raw LangChain messages (incl. tool calls) or ``None``."""
    record = database.get_agent_session(session_id)
    if record is None:
        return None
    return _deserialize(record.get("messages"))


def get_session_detail(session_id: str) -> Optional[Dict[str, Any]]:
    record = database.get_agent_session(session_id)
    if record is None:
        return None
    messages = _deserialize(record.get("messages"))
    history = normalize_history(messages)
    input_tokens = int(record.get("input_tokens") or 0)
    output_tokens = int(record.get("output_tokens") or 0)
    last_input_tokens = int(record.get("last_input_tokens") or 0)
    last_output_tokens = int(record.get("last_output_tokens") or 0)
    pending_raw = _deserialize_pending(record.get("pending"))
    pending = None
    if pending_raw is not None:
        first = pending_raw["tool_calls"][0]
        args = first.get("args")
        pending = {
            "tool": first.get("name"),
            "args": args if isinstance(args, dict) else {},
            "forbidden": bool(pending_raw.get("forbidden")),
        }
    return {
        "id": record["id"],
        "title": record["title"] or "",
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "running": bool(record.get("running")),
        "status": record.get("status") or "",
        "messages": history,
        "pending": pending,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "message_count": len(history),
            "last_input_tokens": last_input_tokens,
            "last_output_tokens": last_output_tokens,
        },
    }


def clear_sessions() -> None:
    _cache.clear()
    database.clear_agent_sessions()
    clear_all_sandboxes()
