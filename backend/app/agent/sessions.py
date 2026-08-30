"""SQLite-backed agent session storage.

A session holds the LangChain message history (persisted to the ``agent_sessions``
table) and any pending (dangerous) tool call awaiting user approval. The pending
approval state is transient and kept in an in-process cache only, while the
conversation history survives a restart.
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
    return session


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


def _content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def normalize_history(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert stored LangChain messages into a compact UI-friendly history.

    System and tool messages are omitted; assistant messages with empty content
    (e.g. an intermediate tool-call turn) are dropped so the history shows only
    the user/assistant conversation text. Each item also carries the optional
    ``time`` (derived from the persisted ``ts`` kwarg, ``YYYY-MM-DD HH:mm``) and
    ``model`` metadata; both are ``None`` when absent so old sessions and
    compacted summary messages stay compatible.
    """
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
                {"role": "user", "content": content, "time": time_str, "model": model}
            )
        elif isinstance(message, AIMessage) and content:
            items.append(
                {"role": "assistant", "content": content, "time": time_str, "model": model}
            )
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
    return {
        "id": record["id"],
        "title": record["title"] or "",
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "running": bool(record.get("running")),
        "status": record.get("status") or "",
        "messages": history,
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
