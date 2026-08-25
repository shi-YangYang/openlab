"""Manual tool-calling agent loop.

Rather than using an automatic agent executor, the loop is driven by hand so it
can pause before executing dangerous tools (``run_command`` / ``deploy_code``)
and wait for user approval (FR-2/FR-8/FR-9).

Flow:

1. ``run_chat`` appends the user message, then runs the loop.
2. Each iteration calls the tool-bound LLM with the full message history.
3. Non-dangerous tool calls are executed immediately and their results are fed
   back as ``ToolMessage`` entries.
4. When a dangerous tool call is reached, the loop stops, stores the pending
   calls on the session, and returns a ``pending_approval`` payload.
5. ``run_approve`` executes (or skips) the pending calls and resumes the loop.
"""
import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ..llm_config import get_effective_config
from . import tools as agent_tools
from .sessions import (
    Session,
    get_or_create,
    get_session,
    save_messages,
    set_running,
    set_status,
    update_title,
)

MAX_STEPS = 20
LLM_REQUEST_TIMEOUT_SECONDS = 120.0
AUTO_TITLE_MAX_LEN = 30

SYSTEM_PROMPT = (
    "你是 openlab 科研 agent，能够调用工具自主完成科研流程，覆盖：文献挖掘（检索/下载）、"
    "论文分析、文献综述、创新点生成、实验方案设计，以及 SSH 服务器部署与监控。\n"
    "工作方式：\n"
    "- 根据用户目标，自主规划步骤，逐步调用工具并把结果串联起来，直到产出最终回答。\n"
    "- 可多轮调用工具；下载、分析、综述、创新、实验设计等较慢的操作请等待其完成后再继续。\n"
    "- 危险操作（服务器命令 run_command、部署代码 deploy_code、SFTP 上传 deploy_upload、服务器增删改、"
    "本地执行 Python 代码 run_python_code、执行 shell 命令 run_shell_command）会先暂停并交由用户确认，"
    "请只在必要时调用。\n"
    "- 最后请用简洁、清晰的语言（默认中文）向用户总结你完成的工作与结论。"
)


class AgentError(Exception):
    """Raised for agent-level errors, carrying an HTTP status code."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _redact_secrets(text: str) -> str:
    """Scrub the LLM API key and any server passwords from a string (NFR-2).

    Secrets shorter than ``_MIN_SECRET_LENGTH`` are ignored to avoid
    over-redacting common single characters.
    """
    _min_len = 4
    secrets: List[str] = []
    try:
        api_key = get_effective_config().get("api_key") or ""
    except Exception:
        api_key = ""
    if api_key:
        secrets.append(api_key)
    try:
        from .. import servers

        for server in servers.list_servers():
            password = server.get("password")
            if password:
                secrets.append(str(password))
    except Exception:
        pass
    for secret in secrets:
        if secret and len(secret) >= _min_len and secret in text:
            text = text.replace(secret, "***")
    return text


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _generate_title(message: str, max_len: int = AUTO_TITLE_MAX_LEN) -> str:
    """Derive a session title from the first user message (truncated)."""
    text = " ".join(message.split())
    if not text:
        return "新会话"
    return text[:max_len]


def build_llm() -> ChatOpenAI:
    cfg = get_effective_config()
    if not cfg["api_key"]:
        raise AgentError("LLM_API_KEY is not configured", 400)
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.2,
        request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
    )


def _build_bound_llm():
    return build_llm().bind_tools(agent_tools.get_tools())


def _tool_call_to_dict(tool_call: Any) -> Dict[str, Any]:
    return {
        "id": tool_call.get("id"),
        "name": tool_call.get("name"),
        "args": tool_call.get("args") or {},
    }


async def _execute_feedback(
    session: Session, name: str, args: Dict[str, Any], tool_call_id: str
) -> Dict[str, Any]:
    agent_tools.set_session_context(session.session_id)
    try:
        result = await agent_tools.execute_tool(name, args)
        session.messages.append(
            ToolMessage(content=_redact_secrets(_stringify(result)), tool_call_id=tool_call_id)
        )
        return {"tool": name, "args": args, "result": result, "status": "done"}
    except Exception as exc:  # noqa: BLE001 - keep the loop alive on tool errors
        message = _redact_secrets(str(exc))
        session.messages.append(ToolMessage(content=f"执行失败: {message}", tool_call_id=tool_call_id))
        return {"tool": name, "args": args, "result": message, "status": "error"}


async def _run_loop(
    session: Session,
    llm: Any,
    log: List[Dict[str, Any]],
    max_steps: int = MAX_STEPS,
    steps_used: int = 0,
) -> Dict[str, Any]:
    steps = steps_used
    while steps < max_steps:
        set_status(session.session_id, "thinking")
        response: AIMessage = await llm.ainvoke(session.messages)
        session.messages.append(response)

        tool_calls = response.tool_calls or []
        if not tool_calls:
            return {
                "reply": _content_to_str(response.content),
                "tool_calls": log,
                "pending_approval": None,
            }

        steps += 1
        for index, tool_call in enumerate(tool_calls):
            name = tool_call.get("name")
            args = tool_call.get("args") or {}
            if agent_tools.is_dangerous(name):
                session.pending = {
                    "tool_calls": [
                        _tool_call_to_dict(tc) for tc in tool_calls[index:]
                    ]
                }
                return {
                    "reply": None,
                    "tool_calls": log,
                    "pending_approval": {"tool": name, "args": args},
                }

            set_status(session.session_id, f"executing:{name} (第{steps}步)")
            entry = await _execute_feedback(session, name, args, tool_call.get("id"))
            log.append(entry)

    return {
        "reply": "已达到最大执行步数，任务可能尚未完成，请继续追问或缩小目标。",
        "tool_calls": log,
        "pending_approval": None,
    }


async def run_chat(
    session_id: Optional[str], message: str, max_steps: int = MAX_STEPS
) -> Dict[str, Any]:
    session = get_or_create(session_id)
    if session.pending is not None:
        raise AgentError("存在待确认的危险操作，请先处理确认或拒绝。", 409)

    is_first = not session.messages
    if is_first:
        session.messages.append(SystemMessage(content=SYSTEM_PROMPT))

    session.messages.append(HumanMessage(content=message))
    if is_first and not session.title:
        session.title = _generate_title(message)
        update_title(session.session_id, session.title)
    save_messages(session)  # persist user message + title before the long loop

    set_running(session.session_id, True)
    llm = _build_bound_llm()
    try:
        result = await _run_loop(session, llm, [], max_steps=max_steps)
    finally:
        set_running(session.session_id, False)
        set_status(session.session_id, "")

    save_messages(session)  # persist assistant reply + tool results

    result["session_id"] = session.session_id
    return result


async def run_approve(
    session_id: str, approve: bool, max_steps: int = MAX_STEPS
) -> Dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise AgentError("会话不存在。", 404)
    if session.pending is None:
        raise AgentError("当前没有待确认的操作。", 400)

    log: List[Dict[str, Any]] = []
    pending_calls = session.pending["tool_calls"]
    session.pending = None

    set_running(session_id, True)
    try:
        for tool_call in pending_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]
            if approve:
                entry = await _execute_feedback(session, name, args, tool_call_id)
            else:
                session.messages.append(
                    ToolMessage(content="用户拒绝了该操作，未执行。", tool_call_id=tool_call_id)
                )
                entry = {
                    "tool": name,
                    "args": args,
                    "result": "用户拒绝，未执行",
                    "status": "rejected",
                }
            log.append(entry)

        llm = _build_bound_llm()
        result = await _run_loop(session, llm, log, max_steps=max_steps)
    finally:
        set_running(session_id, False)
        set_status(session_id, "")
    save_messages(session)
    result["session_id"] = session.session_id
    return result
