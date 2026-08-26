"""Per-session asyncio task management behind the agent WebSocket channel.

Only one task may run per session at a time; duplicate ``chat`` requests are
rejected with an ``error`` event. Tasks survive client disconnects — a
reconnecting client re-attaches its sender (``attach``) and keeps receiving
subsequent events. Cancelling a task lets the agent layer persist the partial
reply and mark the session ``interrupted``; the runner then emits ``stopped``
and re-raises so the task ends cancelled.
"""
import asyncio
from typing import Any, Callable, Dict, Optional

from . import agent as agent_module
from .sessions import get_session

# Coroutine taking a JSON-serializable payload dict, e.g. the WS endpoint's
# bounded ``send`` closure.
Sender = Callable[[Dict[str, Any]], Any]


class AgentRunner:
    """Holds one asyncio.Task plus the live sender per session."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._senders: Dict[str, Sender] = {}

    # ------------------------------------------------------------------ state

    def is_running(self, session_id: str) -> bool:
        task = self._tasks.get(session_id)
        return task is not None and not task.done()

    def running_sessions(self):
        return [sid for sid in list(self._tasks) if self.is_running(sid)]

    # -------------------------------------------------------------- plumbing

    def attach(self, session_id: str, send: Sender) -> None:
        """Bind a sender to the session; latest connection wins."""
        self._senders[session_id] = send

    def detach(self, session_id: str, send: Sender) -> None:
        if self._senders.get(session_id) is send:
            del self._senders[session_id]

    async def _emit(
        self, session_id: str, event_type: str, payload: Optional[dict] = None
    ) -> None:
        send = self._senders.get(session_id)
        if send is None:
            return
        body: Dict[str, Any] = {"type": event_type}
        if payload:
            body.update(payload)
        try:
            await send(body)
        except Exception:  # noqa: BLE001 - broken pipes must never crash tasks
            self.detach(session_id, send)

    def _emit_soon(self, session_id: str, event_type: str, payload: dict) -> None:
        asyncio.ensure_future(self._emit(session_id, event_type, payload))

    # ---------------------------------------------------------------- actions

    def start_chat(
        self,
        session_id: str,
        message: str,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> bool:
        if self.is_running(session_id):
            self._emit_soon(session_id, "error", {"message": "当前会话正在运行"})
            return False
        task = asyncio.create_task(
            self._run_chat(
                session_id,
                message,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )
        self._tasks[session_id] = task
        return True

    def start_approve(
        self,
        session_id: str,
        approve: bool = True,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> bool:
        if self.is_running(session_id):
            self._emit_soon(session_id, "error", {"message": "当前会话正在运行"})
            return False
        session = get_session(session_id)
        if session is None or getattr(session, "pending", None) is None:
            self._emit_soon(session_id, "error", {"message": "当前没有待确认的操作。"})
            return False
        task = asyncio.create_task(
            self._run_approve(
                session_id,
                approve,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )
        self._tasks[session_id] = task
        return True

    def stop(self, session_id: str) -> bool:
        task = self._tasks.get(session_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    # ------------------------------------------------------------- coroutines

    async def _finalize_task(self, session_id: str) -> None:
        self._tasks.pop(session_id, None)

    async def _run_chat(
        self,
        session_id: str,
        message: str,
        model: Optional[str],
        reasoning_effort: Optional[str],
    ) -> None:
        try:
            await agent_module.run_chat(
                session_id,
                message,
                model=model,
                reasoning_effort=reasoning_effort,
                emit=lambda event_type, payload=None: self._emit(
                    session_id, event_type, payload
                ),
            )
        except asyncio.CancelledError:
            await self._emit(session_id, "stopped")
            raise
        except agent_module.AgentError as exc:
            await self._emit(session_id, "error", {"message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface as an error event
            message_text = agent_module._redact_secrets(str(exc)) or "执行失败"
            await self._emit(session_id, "error", {"message": message_text})
        finally:
            await self._finalize_task(session_id)

    async def _run_approve(
        self,
        session_id: str,
        approve: bool,
        model: Optional[str],
        reasoning_effort: Optional[str],
    ) -> None:
        try:
            await agent_module.run_approve(
                session_id,
                approve,
                model=model,
                reasoning_effort=reasoning_effort,
                emit=lambda event_type, payload=None: self._emit(
                    session_id, event_type, payload
                ),
            )
        except asyncio.CancelledError:
            await self._emit(session_id, "stopped")
            raise
        except agent_module.AgentError as exc:
            await self._emit(session_id, "error", {"message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface as an error event
            message_text = agent_module._redact_secrets(str(exc)) or "执行失败"
            await self._emit(session_id, "error", {"message": message_text})
        finally:
            await self._finalize_task(session_id)


runner = AgentRunner()
