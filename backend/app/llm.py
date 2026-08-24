"""LLM helpers: decompose a research topic into an arXiv search query.

Uses LangChain's ``ChatOpenAI`` pointed at any OpenAI-compatible endpoint via
``base_url``. The base URL, API key and model come from the effective LLM
configuration (see ``llm_config.get_effective_config``).
"""
import json
from typing import Any, List

from langchain_openai import ChatOpenAI

from .llm_config import get_effective_config

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
    )
    resp = await llm.ainvoke(
        [
            ("system", _SYSTEM_PROMPT),
            ("human", topic),
        ]
    )
    return _parse_content(_content_to_str(resp.content))
