"""LLM helpers: decompose a research topic into an arXiv search query.

Uses LangChain's ``ChatOpenAI`` pointed at any OpenAI-compatible endpoint via
``base_url``. The base URL, API key and model come from the effective LLM
configuration (see ``llm_config.get_effective_config``).
"""
import asyncio
import json
import logging
from typing import Any, List

from langchain_openai import ChatOpenAI

from .llm_config import get_effective_config

logger = logging.getLogger(__name__)

LLM_MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = (1.0, 2.0)


def _retryable_exception_types() -> tuple:
    """Collect transient network/timeout/rate-limit/5xx exception types.

    Imports are defensive so a missing optional dependency never breaks the
    module. LangChain's OpenAI client rides on ``httpx`` + ``openai``, so these
    two cover the transport layer of every ChatOpenAI call.
    """
    types: list = []
    try:
        import httpx

        types += [httpx.TimeoutException, httpx.ConnectError]
    except ImportError:
        pass
    try:
        import openai

        for name in (
            "APIConnectionError",
            "APITimeoutError",
            "RateLimitError",
            "InternalServerError",
        ):
            cls = getattr(openai, name, None)
            if isinstance(cls, type) and issubclass(cls, Exception):
                types.append(cls)
    except ImportError:
        pass
    return tuple(types)


RETRYABLE_EXCEPTIONS = _retryable_exception_types()


def is_retryable_exception(exc: BaseException) -> bool:
    """True for transient LLM transport errors worth retrying."""
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


def backoff_delay(attempt: int) -> float:
    """Delay before the (attempt+1)-th retry: 1s, 2s, then capped at 2s."""
    if attempt < len(RETRY_BACKOFF_SECONDS):
        return RETRY_BACKOFF_SECONDS[attempt]
    return RETRY_BACKOFF_SECONDS[-1]


async def backoff_sleep(attempt: int) -> None:
    await asyncio.sleep(backoff_delay(attempt))


async def ainvoke_with_retry(llm: Any, messages: Any, max_retries: int = LLM_MAX_RETRIES):
    """``llm.ainvoke`` with exponential backoff on transient errors.

    Retries only connection/timeout/rate-limit/5xx exceptions (1s then 2s);
    anything else (auth failures, bad requests, ...) propagates immediately.
    After ``max_retries`` exhausted, the last exception is raised unchanged so
    existing task failure paths keep working (NFR-2).
    """
    attempt = 0
    while True:
        try:
            return await llm.ainvoke(messages)
        except Exception as exc:
            if not is_retryable_exception(exc) or attempt >= max_retries:
                if is_retryable_exception(exc):
                    logger.warning(
                        "LLM 调用重试 %d 次后仍失败: %r", max_retries, exc
                    )
                raise
            attempt += 1
            delay = backoff_delay(attempt - 1)
            logger.warning(
                "LLM 调用失败，%.1fs 后重试（第 %d/%d 次）: %r",
                delay,
                attempt,
                max_retries,
                exc,
            )
            await backoff_sleep(attempt - 1)

_SYSTEM_PROMPT = (
    "You are a research literature search assistant. "
    "Given a research topic description, produce a concise arXiv search query "
    "(keywords/phrases) that best retrieves relevant papers on arXiv. "
    "Respond with ONLY a JSON object containing a single key \"query\" whose "
    "value is the search query string. Do not include any other text."
)


def _parse_content(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.lstrip("json").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("query"), str):
            return data["query"].strip()
    except json.JSONDecodeError:
        pass
    return text


def _content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


async def decompose_topic(topic: str) -> str:
    cfg = get_effective_config()
    if not cfg["api_key"]:
        raise ValueError("LLM_API_KEY is not configured")

    llm = ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.2,
        request_timeout=120.0,
    )
    resp = await ainvoke_with_retry(
        llm,
        [
            ("system", _SYSTEM_PROMPT),
            ("human", topic),
        ],
    )
    return _parse_content(_content_to_str(resp.content))
