"""Paper analysis: PDF -> LLM structured analysis -> SQLite.

Design notes:

- **Long text (NFR-2)**: full text is split into fixed-size character chunks;
  each chunk is analyzed into a *partial* structured result, then the partial
  results are merged by a final LLM call into the complete analysis. Short
  texts (a single chunk) skip the merge step.
- **Structured output (NFR-4)**: the LLM is asked to return raw JSON, which is
  parsed and validated with pydantic. On validation failure the request is
  retried; if it still fails the job is marked ``failed``.
- **LLM config (NFR-1)**: reuses ``llm_config.get_effective_config`` via
  LangChain ``ChatOpenAI`` (OpenAI-compatible), the same as spec-001.
- **Secrets (NFR-3)**: the API key is only read from ``get_effective_config``
  and passed to ``ChatOpenAI``; it is never persisted, logged or returned.
"""
import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain_openai import ChatOpenAI

from . import database
from .config import settings
from .llm import ainvoke_with_retry
from .llm_config import get_effective_config
from .llm_json import parse_llm_json
from .pdf import extract_text
from .schemas import PaperAnalysis, ReviewResult

CHUNK_SIZE_CHARS = 12000
CHUNK_OVERLAP_CHARS = 200
MAX_RETRIES = 2
LLM_REQUEST_TIMEOUT_SECONDS = 120.0

_LANGUAGE_LABEL = {"zh": "中文", "en": "English"}

_ANALYSIS_SCHEMA = {
    "summary": {
        "research_problem": "string",
        "method": "string",
        "contributions": ["string"],
        "conclusion": "string",
    },
    "experiments": {
        "datasets": ["string"],
        "baselines": ["string"],
        "metrics": ["string"],
        "key_results": "string",
    },
    "limitations": "string",
    "future_work": "string",
    "keywords": ["string"],
    "tags": ["string"],
}

_REVIEW_SCHEMA = {
    "common_themes": ["string"],
    "differences": ["string"],
    "research_gaps": ["string"],
    "summary": "string",
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


async def _chat(messages: List[tuple], temperature: float = 0.2) -> str:
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


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> List[str]:
    """Split text into fixed-size character chunks with a small overlap.

    This is the long-text strategy required by NFR-2: each chunk stays within
    a safe token budget so the model context is never exceeded.
    """
    if not text:
        return []
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _analysis_system_prompt(language: str, partial: bool = False) -> str:
    lang = _LANGUAGE_LABEL.get(language, "中文")
    scope = "the provided paper excerpt" if partial else "the provided paper full text"
    schema = json.dumps(_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2)
    return (
        f"You are a research paper analysis assistant. Analyze {scope} and produce "
        f"a structured JSON summary. You must respond in {lang}.\n\n"
        f"Return ONLY a JSON object matching this exact structure:\n{schema}\n\n"
        "Rules:\n"
        "- Output only the JSON object. No markdown code fences, no extra text.\n"
        '- "contributions", "datasets", "baselines", "metrics", "keywords" and '
        '"tags" must be arrays of strings; all other values are strings.\n'
        "- If a field is not mentioned in the paper, use an empty string or empty array."
    )


def _merge_system_prompt(language: str) -> str:
    lang = _LANGUAGE_LABEL.get(language, "中文")
    schema = json.dumps(_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2)
    return (
        "You are a research paper analysis assistant. You will receive several "
        "partial structured analyses of different chunks of the same paper. Merge "
        f"them into one coherent, complete structured analysis in {lang}.\n\n"
        f"Return ONLY a JSON object matching this exact structure:\n{schema}\n\n"
        "Rules:\n"
        "- Output only the JSON object, no code fences, no extra text.\n"
        "- Deduplicate and merge overlapping information; do not invent facts."
    )


def _review_system_prompt(language: str) -> str:
    lang = _LANGUAGE_LABEL.get(language, "中文")
    schema = json.dumps(_REVIEW_SCHEMA, ensure_ascii=False, indent=2)
    return (
        "You are a research literature review assistant. Given summaries/analyses of "
        "several papers, produce a comparative review identifying common themes, "
        f"differences and research gaps. You must respond in {lang}.\n\n"
        f"Return ONLY a JSON object matching this exact structure:\n{schema}\n\n"
        "Rules:\n"
        "- Output only the JSON object, no code fences, no extra text.\n"
        '- "common_themes", "differences" and "research_gaps" are arrays of strings; '
        '"summary" is a string.'
    )


async def _analyze_chunk(text: str, language: str) -> PaperAnalysis:
    messages = [
        ("system", _analysis_system_prompt(language, partial=True)),
        ("human", text),
    ]
    for attempt in range(MAX_RETRIES + 1):
        raw = await _chat(messages, temperature=0.2)
        try:
            return parse_llm_json(raw, PaperAnalysis, container="object")
        except Exception:
            if attempt >= MAX_RETRIES:
                raise
    raise RuntimeError("unreachable")


async def analyze_paper_text(
    text: str,
    language: str,
    on_progress: Optional[Callable[[int, str], Awaitable[None]]] = None,
) -> PaperAnalysis:
    """Analyze full text into a structured :class:`PaperAnalysis`.

    Splits long text into chunks, analyzes each chunk, then merges the partial
    results. Single-chunk texts are analyzed directly (no merge step).

    ``on_progress(progress, message)``, when provided, is awaited at each stage
    (before chunking, before each chunk, before merging, and on completion) so
    callers can persist chunk-level progress (FR-13).
    """
    async def report(progress: int, message: str) -> None:
        if on_progress is not None:
            await on_progress(progress, message)

    chunks = chunk_text(text)
    await report(5, "开始分析")

    if len(chunks) == 1:
        await report(10, "分析分块 1/1")
        result = await _analyze_chunk(chunks[0], language)
        await report(100, "分析完成")
        return result

    partials: List[PaperAnalysis] = []
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        await report(10 + int(75 * (idx - 1) / total), f"分析分块 {idx}/{total}")
        partials.append(await _analyze_chunk(chunk, language))

    await report(85, "合并结果")
    payload = json.dumps([p.model_dump() for p in partials], ensure_ascii=False)
    messages = [
        ("system", _merge_system_prompt(language)),
        ("human", payload),
    ]
    for attempt in range(MAX_RETRIES + 1):
        raw = await _chat(messages, temperature=0.2)
        try:
            result = parse_llm_json(raw, PaperAnalysis, container="object")
            await report(100, "分析完成")
            return result
        except Exception:
            if attempt >= MAX_RETRIES:
                raise
    raise RuntimeError("unreachable")


async def run_analysis_job(arxiv_ids: List[str], language: str) -> None:
    """Analyze a batch of papers sequentially, updating status in the database.

    Each paper is analyzed one at a time (FR-4). Progress and message are
    written per paper via ``set_analysis_progress`` (FR-13/FR-14). Failures are
    recorded with status ``failed``; success stores the result with status
    ``done`` (overwriting any previous result, FR-6).
    """
    for arxiv_id in arxiv_ids:
        database.set_analysis_status(arxiv_id, "running", language)
        database.set_analysis_progress(arxiv_id, 0, "开始分析")

        async def on_progress(progress: int, message: str, _id: str = arxiv_id) -> None:
            database.set_analysis_progress(_id, progress, message)

        try:
            paper = database.get_paper(arxiv_id)
            if paper is None:
                raise ValueError(f"Paper not found: {arxiv_id}")
            path = paper.get("local_pdf_path") or str(
                settings.papers_dir / f"{arxiv_id}.pdf"
            )
            text = extract_text(path)
            result = await analyze_paper_text(text, language, on_progress=on_progress)
            database.upsert_analysis(
                arxiv_id,
                json.dumps(result.model_dump(), ensure_ascii=False),
                language,
                status="done",
            )
        except Exception as exc:
            database.set_analysis_status(arxiv_id, "failed", language, error=repr(exc))
            database.set_analysis_progress(arxiv_id, 100, "分析失败")


async def generate_review(arxiv_ids: List[str], language: str) -> ReviewResult:
    """Produce a comparative review of multiple papers.

    The review is based on already-stored analyses (or title+abstract fallback)
    to avoid pushing multiple full texts into the model context at once (FR-5,
    NFR-2).
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
        ("system", _review_system_prompt(language)),
        ("human", payload),
    ]
    for attempt in range(MAX_RETRIES + 1):
        raw = await _chat(messages, temperature=0.2)
        try:
            return parse_llm_json(raw, ReviewResult, container="object")
        except Exception:
            if attempt >= MAX_RETRIES:
                raise
    raise RuntimeError("unreachable")


async def run_review_job(review_id: int, arxiv_ids: List[str], language: str) -> None:
    """Run a comparative review in the background, updating progress + result.

    The review record is already inserted with status ``pending`` by the API
    route; this task advances progress (0 -> 50 -> 100), stores the result and
    records failures with ``error`` (FR-16 / FR-10).
    """
    database.set_review_progress(review_id, 0)
    try:
        database.set_review_progress(review_id, 50)
        result = await generate_review(arxiv_ids, language)
        database.update_review(
            review_id, json.dumps(result.model_dump(), ensure_ascii=False), "done"
        )
        database.set_review_progress(review_id, 100)
    except Exception as exc:
        database.update_review(review_id, None, "failed", error=repr(exc))
        database.set_review_progress(review_id, 100)
