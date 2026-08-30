"""Manual tool-calling agent loop.

Rather than using an automatic agent executor, the loop is driven by hand so it
can pause before executing dangerous tools (``run_command`` / ``deploy_code``)
and wait for user approval (FR-2/FR-8/FR-9).

Flow:

1. ``run_chat`` appends the user message, then runs the loop.
2. Each iteration calls the tool-bound LLM with the full message history,
   streaming text deltas through the optional ``emit(type, payload)`` callback
   as ``token`` events.
3. Non-dangerous tool calls are executed immediately and their results are fed
   back as ``ToolMessage`` entries (surfaced live via ``tool_call`` events).
4. When a dangerous tool call is reached, the loop stops, stores the pending
   calls on the session, and reports a ``pending_approval`` event/payload.
5. ``run_approve`` executes (or skips) the pending calls and resumes the loop.
6. Before every LLM call the loop auto-compacts history when the last call's
   input tokens approach the model's context window (FR-5).

The loop runs inside an ``asyncio.Task`` managed by ``app.agent.ws.AgentRunner``
in production; cancelling it persists the partial reply and marks the session
as ``interrupted`` (FR-4).
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from .. import database
from ..llm_config import get_effective_config, get_model_context_length
from ..redact import redact_secrets as _redact_secrets
from . import permissions as agent_permissions
from . import tools as agent_tools
from .compaction import compact_messages, should_compact
from .sessions import (
    Session,
    get_or_create,
    get_session,
    normalize_history,
    save_messages,
    set_running,
    set_status,
    update_title,
)

MAX_STEPS = 20
LLM_REQUEST_TIMEOUT_SECONDS = 120.0
AUTO_TITLE_MAX_LEN = 30

# Optional async callback: emit("token" | "status" | ..., payload_dict)
EmitFn = Callable[..., Awaitable[None]]

SYSTEM_PROMPT = (
    "你是 openlab 科研 agent，能够调用工具自主完成科研流程，覆盖：文献挖掘（检索/下载）、"
    "论文分析、文献综述、创新点生成、实验方案设计，以及 SSH 服务器部署与监控。\n"
    "工作方式：\n"
    "- 根据用户目标，自主规划步骤，逐步调用工具并把结果串联起来，直到产出最终回答。\n"
     "- 可多轮调用工具；下载、分析、综述、创新、实验设计等较慢的操作请等待其完成后再继续。\n"
     "- 危险操作（服务器命令 run_command、部署代码 deploy_code、SFTP 上传 deploy_upload、服务器增删改、"
     "本地执行 Python 代码 run_python_code、执行 shell 命令 run_shell_command）可能需要用户确认后才执行"
     "（取决于当前权限模式设置），请只在必要时调用。\n"
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


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _stamp_message(message: BaseMessage, model: Optional[str]) -> None:
    """Attach persistence metadata (spec-030) to a user/assistant message.

    ``ts`` is the local ``YYYY-MM-DD HH:MM:SS`` timestamp; ``model`` is the
    model name actually in effect for this message (``None`` keeps the field
    absent-compatible for the frontend's ``-`` placeholder).
    """
    kwargs = dict(message.additional_kwargs or {})
    kwargs["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kwargs["model"] = model
    message.additional_kwargs = kwargs


def _generate_title(message: str, max_len: int = AUTO_TITLE_MAX_LEN) -> str:
    """Derive a session title from the first user message (truncated)."""
    text = " ".join(message.split())
    if not text:
        return "新会话"
    return text[:max_len]


def build_llm(
    model: Optional[str] = None, reasoning_effort: Optional[str] = None
) -> ChatOpenAI:
    cfg = get_effective_config()
    if not cfg["api_key"]:
        raise AgentError("LLM_API_KEY is not configured", 400)
    model_kwargs = {}
    effort = reasoning_effort if reasoning_effort else cfg.get("reasoning_effort")
    if effort:
        model_kwargs["reasoning_effort"] = effort
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=model or cfg["model"],
        temperature=0.2,
        request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        model_kwargs=model_kwargs,
    )


def _build_bound_llm(
    model: Optional[str] = None, reasoning_effort: Optional[str] = None
):
    return build_llm(model=model, reasoning_effort=reasoning_effort).bind_tools(
        agent_tools.get_tools()
    )


def _tool_call_to_dict(tool_call: Any) -> Dict[str, Any]:
    return {
        "id": tool_call.get("id"),
        "name": tool_call.get("name"),
        "args": tool_call.get("args") or {},
    }


async def _noop_emit(event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    return None


def _resolve_emit(emit: Optional[EmitFn]) -> EmitFn:
    return emit if callable(emit) else _noop_emit


async def _safe_emit(
    emit: EmitFn, event_type: str, payload: Optional[Dict[str, Any]] = None
) -> None:
    """Emit an event; transport failures must never break the agent loop."""
    try:
        await emit(event_type, payload or {})
    except Exception:  # noqa: BLE001 - emit is best-effort by design
        pass


def _record_usage(session_id: str, input_tokens: int, output_tokens: int) -> None:
    if input_tokens or output_tokens:
        database.add_agent_session_usage(session_id, int(input_tokens), int(output_tokens))
        database.set_agent_session_last_usage(session_id, int(input_tokens), int(output_tokens))


def _last_input_tokens(session_id: str) -> int:
    try:
        record = database.get_agent_session(session_id)
        return int((record or {}).get("last_input_tokens") or 0)
    except Exception:
        return 0


async def _set_status_emit(
    session_id: str, text: str, emit: EmitFn
) -> None:
    set_status(session_id, text)
    await _safe_emit(emit, "status", {"text": text})


async def _stream_reply(
    llm: Any, messages: List[Any], emit: EmitFn
):
    """Run one LLM call, streaming text deltas via ``token`` events.

    Returns ``(AIMessage, usage_dict)``. Falls back to a single ``ainvoke``
    when the LLM does not implement streaming (fakes/tests). Streaming chunks
    may each carry ``usage_metadata``; their values are accumulated per call,
    defaulting to zeros when the provider omits them.
    """
    astream = getattr(llm, "astream", None)
    if not callable(astream):
        response: AIMessage = await llm.ainvoke(messages)
        content = _content_to_str(response.content)
        if content:
            await _safe_emit(emit, "token", {"delta": content})
        return response, dict(getattr(response, "usage_metadata", None) or {})

    agg = None
    prev_text = ""
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    async for chunk in astream(messages):
        meta = getattr(chunk, "usage_metadata", None)
        if meta:
            usage["input_tokens"] += int(meta.get("input_tokens") or 0)
            usage["output_tokens"] += int(meta.get("output_tokens") or 0)
            usage["total_tokens"] += int(meta.get("total_tokens") or 0)
        agg = chunk if agg is None else agg + chunk
        text = _content_to_str(getattr(agg, "content", ""))
        if len(text) > len(prev_text):
            await _safe_emit(emit, "token", {"delta": text[len(prev_text):]})
            prev_text = text

    content = _content_to_str(getattr(agg, "content", "")) if agg is not None else ""
    response = AIMessage(
        content=content,
        additional_kwargs=getattr(agg, "additional_kwargs", {}) if agg else {},
        response_metadata=getattr(agg, "response_metadata", {}) if agg else {},
        id=getattr(agg, "id", None),
        tool_calls=list(getattr(agg, "tool_calls", []) or []) if agg else [],
    )
    return response, usage


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


def _needs_approval(session: Session, name: str, args: Dict[str, Any]) -> bool:
    """Evaluate the tool call against the global permission mode (spec-032).

    Only tools in ``DANGEROUS_TOOLS`` reach this check; the other 22 tools keep
    executing directly. The permission state is re-read on every call so a mode
    change applies to the very next tool call (FR-14). Session-level allows
    (FR-7) participate with lower priority than the safety floor.
    """
    state = agent_permissions.load()
    verdict = agent_permissions.evaluate(
        name,
        args,
        mode=state["mode"],
        whitelist=state["command_whitelist"],
        session_allows=session.allowed_tools,
    )
    return verdict == agent_permissions.ASK


async def _run_loop(
    session: Session,
    llm: Any,
    log: List[Dict[str, Any]],
    max_steps: int = MAX_STEPS,
    steps_used: int = 0,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    emit: Optional[EmitFn] = None,
    context_length: Optional[int] = None,
) -> Dict[str, Any]:
    emit_fn = _resolve_emit(emit)
    effective_model = model or get_effective_config()["model"]
    steps = steps_used
    call_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    while steps < max_steps:
        if should_compact(_last_input_tokens(session.session_id), context_length):
            if await compact_messages(session, llm):
                await _safe_emit(emit_fn, "compacted")

        await _set_status_emit(session.session_id, "thinking", emit_fn)
        response, usage = await _stream_reply(llm, session.messages, emit_fn)
        _stamp_message(response, effective_model)
        session.messages.append(response)

        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        call_usage["input_tokens"] += input_tokens
        call_usage["output_tokens"] += output_tokens
        call_usage["total_tokens"] += input_tokens + output_tokens
        _record_usage(session.session_id, input_tokens, output_tokens)

        tool_calls = response.tool_calls or []
        if not tool_calls:
            return {
                "reply": _content_to_str(response.content),
                "tool_calls": log,
                "pending_approval": None,
                "usage": dict(call_usage),
            }

        steps += 1
        for index, tool_call in enumerate(tool_calls):
            name = tool_call.get("name")
            args = tool_call.get("args") or {}
            if agent_tools.is_dangerous(name) and _needs_approval(session, name, args):
                session.pending = {
                    "tool_calls": [
                        _tool_call_to_dict(tc) for tc in tool_calls[index:]
                    ],
                    "model": model,
                    "reasoning_effort": reasoning_effort,
                }
                await _safe_emit(
                    emit_fn, "pending_approval", {"tool": name, "args": args}
                )
                return {
                    "reply": None,
                    "tool_calls": log,
                    "pending_approval": {"tool": name, "args": args},
                    "usage": dict(call_usage),
                }

            await _set_status_emit(
                session.session_id, f"executing:{name} (第{steps}步)", emit_fn
            )
            entry = await _execute_feedback(session, name, args, tool_call.get("id"))
            log.append(entry)
            await _safe_emit(emit_fn, "tool_call", {"entry": entry})

    return {
        "reply": "已达到最大执行步数，任务可能尚未完成，请继续追问或缩小目标。",
        "tool_calls": log,
        "pending_approval": None,
        "usage": dict(call_usage),
    }


def _conversation_message_count(messages: List[Any]) -> int:
    return len(normalize_history(messages))


async def run_chat(
    session_id: Optional[str],
    message: str,
    max_steps: int = MAX_STEPS,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    emit: Optional[EmitFn] = None,
) -> Dict[str, Any]:
    session = get_or_create(session_id)
    if session.pending is not None:
        raise AgentError("存在待确认的危险操作，请先处理确认或拒绝。", 409)

    is_first = not session.messages
    if is_first:
        session.messages.append(SystemMessage(content=SYSTEM_PROMPT))

    user_message = HumanMessage(content=message)
    # Record the model actually in effect for this request (FR-10).
    _stamp_message(user_message, model or get_effective_config()["model"])
    session.messages.append(user_message)
    if is_first and not session.title:
        session.title = _generate_title(message)
        update_title(session.session_id, session.title)
    save_messages(session)  # persist user message + title before the long loop

    emit_fn = _resolve_emit(emit)
    context_length = get_model_context_length(model)

    interrupted = False
    set_running(session.session_id, True)
    try:
        llm = _build_bound_llm(model=model, reasoning_effort=reasoning_effort)
        result = await _run_loop(
            session,
            llm,
            [],
            max_steps=max_steps,
            model=model,
            reasoning_effort=reasoning_effort,
            emit=emit_fn,
            context_length=context_length,
        )
    except asyncio.CancelledError:
        interrupted = True
        raise
    finally:
        set_running(session.session_id, False)
        if interrupted:
            # Partial reply / tool records are preserved (FR-4).
            set_status(session.session_id, "interrupted")
            save_messages(session)
        else:
            set_status(session.session_id, "")

    if not interrupted:
        save_messages(session)  # persist assistant reply + tool results

    result["session_id"] = session.session_id
    if not interrupted and result.get("pending_approval") is None:
        usage = dict(result.get("usage") or {})
        usage["message_count"] = _conversation_message_count(session.messages)
        await _safe_emit(
            emit_fn, "done", {"reply": result.get("reply") or "", "usage": usage}
        )
    return result


async def run_approve(
    session_id: str,
    approve: bool,
    max_steps: int = MAX_STEPS,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    emit: Optional[EmitFn] = None,
    scope: str = agent_permissions.ONCE_SCOPE,
) -> Dict[str, Any]:
    """Resume after an approval decision.

    ``scope`` is ``"once"`` (default, backwards compatible: execute just this
    pending call) or ``"session"`` (execute and add the tool to the session's
    allow set so later non-forbidden calls auto-execute; FR-9/FR-7).
    """
    session = get_session(session_id)
    if session is None:
        raise AgentError("会话不存在。", 404)
    if session.pending is None:
        raise AgentError("当前没有待确认的操作。", 400)

    log: List[Dict[str, Any]] = []
    pending_calls = session.pending["tool_calls"]
    model = model or session.pending.get("model")
    reasoning_effort = reasoning_effort or session.pending.get("reasoning_effort")
    session.pending = None

    if approve and scope == agent_permissions.SESSION_SCOPE:
        for tool_call in pending_calls:
            name = tool_call.get("name")
            if name:
                session.allowed_tools.add(name)

    emit_fn = _resolve_emit(emit)
    context_length = get_model_context_length(model)

    interrupted = False
    set_running(session_id, True)
    try:
        for tool_call in pending_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]
            if approve:
                await _set_status_emit(
                    session_id, f"executing:{name} (第1步)", emit_fn
                )
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
            await _safe_emit(emit_fn, "tool_call", {"entry": entry})

        llm = _build_bound_llm(model=model, reasoning_effort=reasoning_effort)
        result = await _run_loop(
            session,
            llm,
            log,
            max_steps=max_steps,
            model=model,
            reasoning_effort=reasoning_effort,
            emit=emit_fn,
            context_length=context_length,
        )
    except asyncio.CancelledError:
        interrupted = True
        raise
    finally:
        set_running(session_id, False)
        if interrupted:
            set_status(session_id, "interrupted")
            save_messages(session)
        else:
            set_status(session_id, "")
    if not interrupted:
        save_messages(session)
    result["session_id"] = session.session_id
    if not interrupted and result.get("pending_approval") is None:
        usage = dict(result.get("usage") or {})
        usage["message_count"] = _conversation_message_count(session.messages)
        await _safe_emit(
            emit_fn, "done", {"reply": result.get("reply") or "", "usage": usage}
        )
    return result
