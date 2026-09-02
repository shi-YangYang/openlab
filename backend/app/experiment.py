"""Experiment plan design: innovation/analyses -> LLM -> SQLite.

Design notes:

- **Input (FR-1/FR-2)**: ``source_type=innovation`` uses the stored innovation
  point ``content`` as input; ``source_type=papers`` uses the stored ``analyses``
  of the selected papers (or title+abstract fallback), mirroring
  ``analysis.generate_review``.
- **Structured output (NFR-3)**: the LLM is asked to return a raw JSON array of
  experiment plans, which is parsed and validated with pydantic. On failure the
  request is retried; if it still fails the job is marked ``failed``.
- **LLM config (NFR-1)**: reuses ``llm_config.get_effective_config`` via
  LangChain ``ChatOpenAI`` (OpenAI-compatible), the same as spec-001/spec-002.
- **Timeout (NFR-4)**: ``ChatOpenAI`` is created with ``request_timeout``.
- **Secrets (NFR-2)**: the API key is only read from ``get_effective_config``
  and passed to ``ChatOpenAI``; it is never persisted, logged or returned.
"""
import json
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI

from . import database
from .llm import ainvoke_with_retry
from .llm_config import get_effective_config
from .llm_json import parse_llm_json
from .schemas import ExperimentPlan

MAX_RETRIES = 2
LLM_REQUEST_TIMEOUT_SECONDS = 120.0

_LANGUAGE_LABEL = {"zh": "中文", "en": "English"}

_EXPERIMENT_SCHEMA = {
    "hypothesis": "string",
    "goal": "string",
    "datasets": ["string"],
    "baselines": ["string"],
    "metrics": ["string"],
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


def _experiment_system_prompt(language: str, count: int) -> str:
    lang = _LANGUAGE_LABEL.get(language, "中文")
    schema = json.dumps(_EXPERIMENT_SCHEMA, ensure_ascii=False, indent=2)
    return (
        "You are a research experiment design assistant. Based on the provided "
        "innovation point(s) or paper analysis, design concrete, executable "
        f"experiment plans in {lang}.\n\n"
        f"Return ONLY a JSON array of exactly {count} objects, each matching this "
        f"exact structure:\n{schema}\n\n"
        "Rules:\n"
        "- Output only the JSON array, no markdown code fences, no extra text.\n"
        '- "datasets", "baselines" and "metrics" must be arrays of strings; '
        '"hypothesis" and "goal" are strings.\n'
        "- Each plan must be specific, executable, and consistent with the source "
        "input (do not invent unrelated facts).\n"
        "- Write all text in the requested language."
    )


def _assemble_papers_inputs(arxiv_ids: List[str]) -> List[Dict[str, Any]]:
    """Assemble paper inputs from stored analyses (or title+abstract fallback)."""
    inputs: List[Dict[str, Any]] = []
    for arxiv_id in arxiv_ids:
        paper = database.get_paper(arxiv_id)
        analysis = database.get_analysis(arxiv_id)
        entry: Dict[str, Any] = {"arxiv_id": arxiv_id}
        if paper:
            entry["title"] = paper.get("title") or ""
        if analysis and analysis.get("content"):
            entry["analysis"] = analysis["content"]
        elif paper:
            entry["abstract"] = paper.get("abstract") or ""
        if "analysis" in entry or "abstract" in entry or paper:
            inputs.append(entry)
    return inputs


async def generate_experiments(
    source_type: str,
    innovation_id: Optional[int],
    arxiv_ids: List[str],
    language: str,
    count: int,
) -> List[ExperimentPlan]:
    """Design experiment plans from an innovation point or paper analyses.

    The input is assembled from already-stored data to avoid pushing full texts
    into the model context (FR-1/FR-2, NFR-2).
    """
    if source_type == "innovation":
        innovation = database.get_innovation(innovation_id) if innovation_id else None
        if innovation is None:
            raise ValueError(f"Innovation not found: {innovation_id}")
        content = innovation.get("content")
        if not content:
            raise ValueError(f"Innovation has no content: {innovation_id}")
        payload = json.dumps(content, ensure_ascii=False)
    elif source_type == "papers":
        inputs = _assemble_papers_inputs(arxiv_ids)
        if not inputs:
            raise ValueError("no paper analysis available for the provided arxiv_ids")
        payload = json.dumps(inputs, ensure_ascii=False)
    else:
        raise ValueError(f"unknown source_type: {source_type}")

    messages = [
        ("system", _experiment_system_prompt(language, count)),
        ("human", payload),
    ]
    for attempt in range(MAX_RETRIES + 1):
        raw = await _chat(messages, temperature=0.3)
        try:
            items = parse_llm_json(raw, container="array")
            plans = [ExperimentPlan.model_validate(item) for item in items]
            if not plans:
                raise ValueError("empty experiment plan list")
            return plans[:count]
        except Exception:
            if attempt >= MAX_RETRIES:
                raise
    raise RuntimeError("unreachable")


async def run_experiment_job(
    experiment_id: int,
    source_type: str,
    innovation_id: Optional[int],
    arxiv_ids: List[str],
    language: str,
    count: int,
) -> None:
    """Run experiment design in the background, updating progress + result.

    The experiment record is already inserted with status ``pending`` by the API
    route; this task advances progress (0 -> 50 -> 100), stores the result and
    records failures with ``error``.
    """
    database.set_experiment_progress(experiment_id, 0)
    try:
        database.set_experiment_progress(experiment_id, 50)
        result = await generate_experiments(
            source_type, innovation_id, arxiv_ids, language, count
        )
        database.update_experiment(
            experiment_id,
            json.dumps([p.model_dump() for p in result], ensure_ascii=False),
            "done",
        )
        database.set_experiment_progress(experiment_id, 100)
    except Exception as exc:
        database.update_experiment(experiment_id, None, "failed", error=repr(exc))
        database.set_experiment_progress(experiment_id, 100)
