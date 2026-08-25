"""In-memory agent session storage.

A session holds the LangChain message history and any pending (dangerous) tool
call awaiting user approval. A plain in-process dict is enough for the
single-user local deployment targeted by this spec.
"""
import uuid
from typing import Any, Dict, List, Optional


class Session:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages: List[Any] = []
        self.pending: Optional[Dict[str, Any]] = None


_sessions: Dict[str, Session] = {}


def get_or_create(session_id: Optional[str] = None) -> Session:
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    new_id = session_id or uuid.uuid4().hex
    session = Session(new_id)
    _sessions[new_id] = session
    return session


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)


def clear_sessions() -> None:
    _sessions.clear()
