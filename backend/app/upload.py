"""Local PDF upload: extract paper metadata from text via LLM.

The LLM is asked to return raw JSON (title / authors / abstract / published),
which is parsed and validated with a pydantic model. Reuses
``llm_config.get_effective_config`` (OpenAI-compatible via LangChain), the same
as spec-001/002.
"""
from typing import Any, List

from langchain_openai import ChatOpenAI

from .llm import ainvoke_with_retry
from .llm_config import get_effective_config
from .llm_json import parse_llm_json
from .schemas import PaperMetadata

_SYSTEM_PROMPT = (
    "You are a research paper metadata extraction assistant. "
    "Given the text extracted from a research paper PDF, extract the paper's "
    "bibliographic metadata. Respond with ONLY a JSON object containing the "
    'keys "title" (string), "authors" (array of strings), "abstract" (string), '
    '"published" (string, publication date in YYYY-MM-DD or YYYY format, '
    'empty string if unknown) and "url" (string, the paper\'s source URL such '
    "as an arxiv.org/abs/xxx link, empty string if unknown). "
    "Do not include any other text."
)


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


async def extract_metadata(text: str) -> dict:
    """Extract ``{title, authors, abstract, published}`` from PDF text via LLM."""
    cfg = get_effective_config()
    if not cfg["api_key"]:
        raise ValueError("LLM_API_KEY is not configured")

    excerpt = text[:12000]
    llm = ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.0,
        request_timeout=120.0,
        reasoning_effort=cfg.get("reasoning_effort") or None,
    )
    resp = await ainvoke_with_retry(llm, [("system", _SYSTEM_PROMPT), ("human", excerpt)])
    raw = _content_to_str(resp.content)
    return parse_llm_json(raw, PaperMetadata, container="object").model_dump()
