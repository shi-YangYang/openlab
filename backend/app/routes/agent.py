"""Agent routes: WebSocket channel, session CRUD, and sandbox attachments."""
import json
import shutil
import time
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, Response
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ..agent import (
    create_session,
    delete_session,
    get_raw_messages,
    get_session_detail,
    list_sessions,
    update_title,
)
from ..agent.agent import _redact_secrets
from ..agent.ws import runner as agent_runner
from ..config import settings
from ..schemas import (
    AgentSessionCreate,
    AgentSessionDetail,
    AgentSessionItem,
    AgentSessionUpdate,
)
from .servers import _safe_rel_path

router = APIRouter()


def _agent_ws_send(websocket: WebSocket, state: dict):
    """Bounded sender for one connection; failures flip ``state["active"]``."""

    async def send(payload: dict) -> None:
        if not state.get("active"):
            raise RuntimeError("connection closed")
        try:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            state["active"] = False
            raise

    return send


@router.get("/sessions", response_model=List[AgentSessionItem])
async def list_agent_sessions() -> List[dict]:
    return list_sessions()


@router.get("/sessions/{session_id}", response_model=AgentSessionDetail)
async def get_agent_session(session_id: str) -> dict:
    detail = get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return detail


@router.get("/sessions/{session_id}/export")
async def export_agent_session(session_id: str) -> Response:
    markdown = _build_agent_export_markdown(session_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="agent-{session_id}.md"'
        },
    )


@router.get("/sessions/{session_id}/attachments/{attachment_path:path}")
async def get_agent_attachment(session_id: str, attachment_path: str) -> FileResponse:
    """Serve a sandbox attachment file (for the UI file chips in chat)."""
    from ..agent.sandbox import sandbox_dir

    root = sandbox_dir(session_id)
    full = (root / attachment_path).resolve()
    if not full.is_relative_to(root.resolve()):
        raise HTTPException(status_code=403, detail="非法路径")
    if not full.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {attachment_path}")
    media = "application/octet-stream"
    lower = attachment_path.lower()
    if lower.endswith(".png"):
        media = "image/png"
    elif lower.endswith((".jpg", ".jpeg")):
        media = "image/jpeg"
    elif lower.endswith(".gif"):
        media = "image/gif"
    elif lower.endswith(".webp"):
        media = "image/webp"
    elif lower.endswith(".pdf"):
        media = "application/pdf"
    elif lower.endswith((".py", ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log", ".sh")):
        media = "text/plain; charset=utf-8"
    return FileResponse(full, media_type=media, filename=attachment_path.rsplit("/", 1)[-1])


@router.post("/sessions", response_model=AgentSessionItem)
async def create_agent_session(req: AgentSessionCreate) -> dict:
    session = create_session(title=req.title)
    detail = get_session_detail(session.session_id)
    return detail if detail is not None else {"id": session.session_id, "title": session.title}


@router.post("/sessions/{session_id}/attachments")
async def upload_agent_attachment(
    session_id: str,
    file: UploadFile = File(...),
    path: str = Form(""),
) -> dict:
    if get_session_detail(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    rel = _safe_rel_path(path or file.filename or "attachment")
    target = settings.data_dir / "sandbox" / session_id / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": rel, "size": target.stat().st_size}


@router.put("/sessions/{session_id}", response_model=AgentSessionItem)
async def update_agent_session(session_id: str, req: AgentSessionUpdate) -> dict:
    record = update_title(session_id, req.title)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return record


@router.delete("/sessions/{session_id}")
async def delete_agent_session(session_id: str) -> dict:
    agent_runner.stop(session_id)
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"status": "ok"}


@router.websocket("/ws")
async def agent_ws(
    websocket: WebSocket, session_id: Optional[str] = Query(default=None)
) -> None:
    await websocket.accept()
    sid = session_id or None
    state = {"active": True}
    send = _agent_ws_send(websocket, state)
    if sid:
        # Re-attach a reconnecting client so a running task keeps streaming.
        agent_runner.attach(sid, send)

    while True:
        try:
            text = await websocket.receive_text()
        except WebSocketDisconnect:
            break
        try:
            message = json.loads(text)
        except ValueError:
            continue
        if not isinstance(message, dict):
            continue

        msg_type = message.get("type")
        if msg_type == "chat":
            text_body = str(message.get("message") or "").strip()
            if not text_body:
                await send({"type": "error", "message": "消息不能为空"})
                continue
            if sid and get_session_detail(sid) is None:
                await send({"type": "error", "message": f"会话不存在: {sid}"})
                continue
            if not state.get("active"):
                break
            if sid is None:
                created = create_session()
                sid = created.session_id
                agent_runner.attach(sid, send)
                await send({"type": "session", "session_id": sid})
            agent_runner.start_chat(
                sid,
                text_body,
                model=message.get("model") or None,
                reasoning_effort=message.get("reasoning_effort") or None,
            )
        elif msg_type == "approve":
            if sid is None:
                await send({"type": "error", "message": "会话不存在"})
                continue
            agent_runner.start_approve(
                sid,
                bool(message.get("approve")),
                model=message.get("model") or None,
                reasoning_effort=message.get("reasoning_effort") or None,
            )
        elif msg_type == "stop":
            if sid:
                agent_runner.stop(sid)
        # Other message types are ignored.

    # Disconnect: the task keeps running in the background so a reconnect can
    # re-attach; just unbind this socket's sender.
    state["active"] = False
    if sid:
        agent_runner.detach(sid, send)


def _tool_result_first_line(messages: List[Any], tool_call_id: Optional[str]) -> tuple:
    """Return ``(first_line, status)`` of the ToolMessage following a tool call."""
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "tool_call_id", None) != tool_call_id:
            continue
        content = message.content if isinstance(message.content, str) else str(message.content)
        first_line = content.strip().splitlines()[0][:200] if content.strip() else ""
        if content.startswith("执行失败"):
            return first_line, "error"
        if "用户拒绝" in content[:20]:
            return first_line, "rejected"
        return first_line, "done"
    return "", "done"


def _short_args(args: Any, limit: int = 200) -> str:
    try:
        text = json.dumps(args, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(args)
    return text if len(text) <= limit else text[:limit] + "…"


def _build_agent_export_markdown(session_id: str) -> Optional[str]:
    messages = get_raw_messages(session_id)
    detail = get_session_detail(session_id)
    if messages is None or detail is None:
        return None

    lines: List[str] = [
        f"# {detail['title'] or session_id}",
        "",
        f"- 会话 ID：{session_id}",
        f"- 导出时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 消息数：{len(detail['messages'])}",
        "",
        "---",
        "",
    ]
    tool_cache = list(messages)
    for message in messages:
        if isinstance(message, HumanMessage):
            lines.extend(["**user**:", "", message.content.strip(), ""])
        elif isinstance(message, AIMessage):
            content = (
                message.content if isinstance(message.content, str) else str(message.content)
            )
            if content.strip():
                lines.extend(["**assistant**:", "", content.strip(), ""])
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                lines.append("<details><summary>工具调用</summary>")
                lines.append("")
                for tool_call in tool_calls:
                    name = tool_call.get("name")
                    result, status = _tool_result_first_line(
                        tool_cache, tool_call.get("id")
                    )
                    status_label = {"done": "完成", "error": "失败", "rejected": "已拒绝"}.get(
                        status, status
                    )
                    lines.append(f"> - `{name}`（{status_label}）参数：`{_short_args(tool_call.get('args'))}`")
                    if result:
                        lines.append(f">   - 结果：{result}")
                lines.append("")
                lines.append("</details>")
                lines.append("")

    markdown = "\n".join(lines).strip() + "\n"
    return _redact_secrets(markdown)
