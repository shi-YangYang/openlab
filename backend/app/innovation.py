"""Research innovation point generation: analyses -> LLM -> SQLite.

Design notes:

- **Input (FR-1/FR-2)**: single-paper innovation is based on that paper's
  stored ``analyses`` (or title+abstract fallback); multi-paper innovation is
  based on the stored ``analyses`` of all selected papers (or abstract
  fallback), mirroring ``analysis.generate_review``.
- **Structured output (NFR-3)**: the LLM is asked to return a raw JSON array of
  innovation points, which is parsed and validated with pydantic. On failure
  the request is retried; if it still fails the job is marked ``failed``.
- **LLM config (NFR-1)**: reuses ``llm_config.get_effective_config`` via
  LangChain ``ChatOpenAI`` (OpenAI-compatible), the same as spec-001/spec-002.
- **Timeout (NFR-4)**: ``ChatOpenAI`` is created with ``request_timeout``.
- **Secrets (NFR-2)**: the API key is only read from ``get_effective_config``
  and passed to ``ChatOpenAI``; it is never persisted, logged or returned.
"""
import json
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI

from . import database
from .llm import ainvoke_with_retry
from .llm_config import get_effective_config
from .schemas import InnovationPoint

MAX_RETRIES = 2
LLM_REQUEST_TIMEOUT_SECONDS = 120.0

_LANGUAGE_LABEL = {"zh": "中文", "en": "English"}

_INNOVATION_SCHEMA = {
    "title": "string",
    "description": "string",
    "basis": ["string"],
    "expected_contribution": "string",
}


def _content_to_str(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.lstrip("json").strip()
    return text


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse an LLM response into a list of JSON objects, tolerating fences."""
    text = _strip_fences(text)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("LLM response is not a valid JSON array")


async def _chat(messages: List[tuple], temperature: float = 0.3) -> str:
    cfg = get_effective_config()
    if not cfg["api_key"]:
        raise ValueError("LLM_API_KEY is not configured")

    llm = ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=temperature,
        request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        reasoning_effort=cfg.get("reasoning_effort") or None,
    )
    resp = await ainvoke_with_retry(llm, messages)
    return _content_to_str(resp.content)


def _innovation_system_prompt(language: str, count: int) -> str:
    lang = _LANGUAGE_LABEL.get(language, "中文")
    schema = json.dumps(_INNOVATION_SCHEMA, ensure_ascii=False, indent=2)
    return (
        "You are a research innovation assistant. Based on the provided paper "
        "analysis (single paper) or the comparative analyses (multiple papers), "
        f"propose exactly {count} research innovation points in {lang}.\n\n"
        f"Return ONLY a JSON array of {count} objects, each matching this exact "
        f"structure:\n{schema}\n\n"
        "Rules:\n"
        "- Output only the JSON array, no markdown code fences, no extra text.\n"
        '- "basis" must be an array of strings, each citing the source paper(s) '
        "and the research gap the innovation addresses.\n"
        "- Every innovation point must be evidence-based, traceable to the source "
        "papers, and specific (not vague).\n"
        "- Write all text in the requested language."
    )


async def generate_innovations(
    arxiv_ids: List[str], language: str, count: int
) -> List[InnovationPoint]:
    """Propose innovation points from stored analyses (or abstract fallback).

    Inputs are assembled from already-stored analyses to avoid pushing multiple
    full texts into the model context at once (FR-1/FR-2, NFR-2).
    """
    inputs: List[Dict[str, Any]] = []
    for arxiv_id in arxiv_ids:
        paper = database.get_paper(arxiv_id)
        analysis = database.get_analysis(arxiv_id)
        entry: Dict[str, Any] = {"arxiv_id": arxiv_id}
        if paper:
            entry["title"] = paper.get("title", "")
        if analysis and analysis.get("content"):
            entry["analysis"] = analysis["content"]
        elif paper:
            entry["abstract"] = paper.get("abstract", "")
        if "analysis" in entry or "abstract" in entry or paper:
            inputs.append(entry)

    payload = json.dumps(inputs, ensure_ascii=False)
    messages = [
        ("system", _innovation_system_prompt(language, count)),
        ("human", payload),
    ]
    for attempt in range(MAX_RETRIES + 1):
        raw = await _chat(messages, temperature=0.3)
        try:
            items = _parse_json_array(raw)
            points = [InnovationPoint.model_validate(item) for item in items]
            if not points:
                raise ValueError("empty innovation list")
            return points[:count]
        except Exception:
            if attempt >= MAX_RETRIES:
                raise
    raise RuntimeError("unreachable")


async def run_innovation_job(
    innovation_id: int, arxiv_ids: List[str], language: str, count: int
) -> None:
    """Run innovation generation in the background, updating progress + result.

    The innovation record is already inserted with status ``pending`` by the API
    route; this task advances progress (0 -> 50 -> 100), stores the result and
    records failures with ``error``.
    """
    database.set_innovation_progress(innovation_id, 0)
    try:
        database.set_innovation_progress(innovation_id, 50)
        result = await generate_innovations(arxiv_ids, language, count)
        database.update_innovation(
            innovation_id,
            json.dumps([p.model_dump() for p in result], ensure_ascii=False),
            "done",
        )
        database.set_innovation_progress(innovation_id, 100)
    except Exception as exc:
        database.update_innovation(innovation_id, None, "failed", error=repr(exc))
        database.set_innovation_progress(innovation_id, 100)
