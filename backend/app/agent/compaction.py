"""Context-window auto-compaction for agent sessions.

When the last LLM call consumed close to the selected model's context window,
older history (everything except the system prompt and the most recent
messages) is summarized into a single message and persisted (FR-5). A failed
summary never blocks the conversation: ``compact_messages`` returns ``False``
and leaves the session untouched.
"""
from typing import Any, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .sessions import Session, save_messages

KEEP_RECENT = 6
_COMPACT_RATIO = 0.8
_SUMMARY_MAX_TOKENS = 512
_TRANSCRIPT_MAX_CHARS = 20000

_SUMMARY_PROMPT = (
    "请把以下科研 agent 会话历史压缩成一份简洁摘要，作为后续对话的上下文。"
    "必须保留：关键结论、文件路径、命令、数据事实（数字/参数/结果）、未完成的任务与下一步计划。\n"
    "用条目化中文输出，不要添加原文没有的信息。\n\n会话历史：\n{transcript}"
)


def should_compact(
    last_input_tokens: Optional[int], context_length: Optional[int]
) -> bool:
    """True when last input usage reached ``context_length`` * 80%."""
    if not context_length or context_length <= 0:
        return False
    return int(last_input_tokens or 0) >= context_length * _COMPACT_RATIO


def _message_text(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, HumanMessage):
        return "user"
    return type(message).__name__.lower()


async def compact_messages(session: Session, llm: Any) -> bool:
    """Replace older history with one summary message; returns success."""
    try:
        messages = list(session.messages)
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]
        if len(non_system) <= KEEP_RECENT:
            return False
        compactable = non_system[:-KEEP_RECENT]

        transcript = "\n\n".join(
            f"{_message_role(m)}: {_message_text(m)}" for m in compactable
        )
        prompt = HumanMessage(
            content=_SUMMARY_PROMPT.format(transcript=transcript[:_TRANSCRIPT_MAX_CHARS])
        )
        bind = getattr(llm, "bind", None)
        runnable = bind(max_tokens=_SUMMARY_MAX_TOKENS) if callable(bind) else llm
        response = await runnable.ainvoke([prompt])
        summary = _message_text(response).strip()
        if not summary:
            return False

        result: List[BaseMessage] = []
        replaced = False
        remaining = len(compactable)
        for message in messages:
            if isinstance(message, SystemMessage):
                result.append(message)
                continue
            if remaining > 0:
                remaining -= 1
                if not replaced:
                    result.append(HumanMessage(content=f"[历史摘要]\n{summary}"))
                    replaced = True
                continue
            result.append(message)
        if not replaced:
            return False

        session.messages = result
        save_messages(session)
        return True
    except Exception:
        return False
