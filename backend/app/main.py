"""FastAPI application entry point."""
import json
import re
import shlex
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, List, Optional

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from . import analysis, database, downloader, experiment, export, innovation, monitor, pdf, servers, ssh, terminal, upload
from .agent import (
    create_session,
    delete_session,
    get_raw_messages,
    get_session_detail,
    list_sessions,
    update_title,
)
from .agent.agent import _redact_secrets
from .agent.ws import runner as agent_runner
from .arxiv import ArxivClient
from .config import settings
from .llm import decompose_topic
from .llm_config import load_config, save_config
from .pdf import PdfExtractionError
from .presets import LLM_PRESETS
from .reasoning_efforts import guess_reasoning_efforts
from .platforms import browser, sessions
from .search.aggregator import search as aggregate_search
from .schemas import (
    AgentSessionCreate,
    AgentSessionDetail,
    AgentSessionItem,
    AgentSessionUpdate,
    AnalysisRecord,
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    CloneRequest,
    CloneResponse,
    DownloadRequest,
    DownloadResponse,
    ExecRequest,
    ExecResponse,
    ExperimentRecord,
    ExperimentHistoryItem,
    ExperimentRequest,
    LLMConfigResponse,
    LLMModelInfo,
    LLMModelsRequest,
    LLMModelsResponse,
    LLMPreset,
    LLMTestRequest,
    LLMTestResponse,
    InnovationHistoryItem,
    InnovationRecord,
    InnovationRequest,
    MonitorResponse,
    PaperRecord,
    PaperUploadResponse,
    PlatformStatus,
    ReviewRecord,
    ReviewRequest,
    SearchHistoryDetail,
    SearchHistoryItem,
    SearchRequest,
    SearchResponse,
    ServerInput,
    ServerOutput,
    ServerUpdate,
    TestConnectionResponse,
    TopicSearchRequest,
    TopicSearchResponse,
    UploadConfirmRequest,
    UploadResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    app.state.arxiv_client = ArxivClient(
        interval=settings.arxiv_request_interval,
        max_retries=settings.arxiv_max_retries,
    )
    yield
    await app.state.arxiv_client.aclose()


app = FastAPI(title="openlab backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_arxiv_client(request: Request) -> ArxivClient:
    return request.app.state.arxiv_client


def _filter_by_date(
    papers: List[dict], date_from: Optional[str], date_to: Optional[str]
) -> List[dict]:
    if not date_from and not date_to:
        return papers
    result = []
    for paper in papers:
        published = (paper.get("published") or "")[:10]
        if date_from and published < date_from:
            continue
        if date_to and published > date_to:
            continue
        result.append(paper)
    return result


def _is_downloaded(arxiv_id: str) -> bool:
    paper = database.get_paper(arxiv_id)
    return bool(
        paper and paper.get("local_pdf_path") and paper.get("status") == "downloaded"
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    arxiv_client: ArxivClient = Depends(get_arxiv_client),
) -> dict:
    result = await aggregate_search(
        req.query,
        platforms=req.platforms,
        max_results=req.max_results,
        arxiv_client=arxiv_client,
        category=req.category,
    )
    papers = _filter_by_date(result["papers"], req.date_from, req.date_to)[
        : req.max_results
    ]
    database.save_search_history(req.query, "keyword", papers)
    return {"papers": papers, "fallbacks": result["fallbacks"]}


@app.post("/api/search/topic", response_model=TopicSearchResponse)
async def search_topic(
    req: TopicSearchRequest,
    arxiv_client: ArxivClient = Depends(get_arxiv_client),
) -> dict:
    try:
        query = await decompose_topic(req.topic)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")

    result = await aggregate_search(
        query,
        platforms=req.platforms,
        max_results=req.max_results,
        arxiv_client=arxiv_client,
        category=req.category,
    )
    papers = _filter_by_date(result["papers"], req.date_from, req.date_to)[
        : req.max_results
    ]
    database.save_search_history(req.topic, "topic", papers)
    return {"query": query, "papers": papers, "fallbacks": result["fallbacks"]}


@app.get("/api/search/history", response_model=List[SearchHistoryItem])
async def list_search_history() -> List[dict]:
    return database.list_search_history()


@app.get("/api/search/history/{history_id}", response_model=SearchHistoryDetail)
async def get_search_history(history_id: int) -> dict:
    record = database.get_search_history(history_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"History not found: {history_id}")
    return record


@app.delete("/api/search/history/{history_id}")
async def delete_search_history(history_id: int) -> dict:
    if not database.delete_search_history(history_id):
        raise HTTPException(status_code=404, detail=f"History not found: {history_id}")
    return {"status": "ok"}


@app.delete("/api/search/history")
async def clear_search_history() -> dict:
    database.clear_search_history()
    return {"status": "ok"}


def _require_platform(platform: str) -> None:
    if platform not in sessions.SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")


@app.get("/api/platforms", response_model=List[PlatformStatus])
async def list_platforms() -> List[dict]:
    return sessions.list_states()


@app.post("/api/platforms/{platform}/login", response_model=PlatformStatus)
async def login_platform(platform: str) -> dict:
    _require_platform(platform)
    if sessions.get_state(platform) == sessions.LOGGING_IN:
        return {"platform": platform, "state": sessions.LOGGING_IN}
    sessions.set_state(platform, sessions.LOGGING_IN)
    threading.Thread(target=browser.run_login, args=(platform,), daemon=True).start()
    return {"platform": platform, "state": sessions.LOGGING_IN}


@app.get("/api/platforms/{platform}/status", response_model=PlatformStatus)
async def get_platform_status(platform: str) -> dict:
    _require_platform(platform)
    return {"platform": platform, "state": sessions.get_state(platform)}


@app.post("/api/platforms/{platform}/logout", response_model=PlatformStatus)
async def logout_platform(platform: str) -> dict:
    _require_platform(platform)
    sessions.delete_state(platform)
    sessions.set_state(platform, sessions.NOT_LOGGED_IN)
    return {"platform": platform, "state": sessions.NOT_LOGGED_IN}


@app.post("/api/platforms/{platform}/login/complete", response_model=PlatformStatus)
async def complete_platform_login(platform: str) -> dict:
    _require_platform(platform)
    browser.complete_login(platform)
    return {"platform": platform, "state": sessions.get_state(platform)}


@app.post("/api/platforms/{platform}/login/cancel", response_model=PlatformStatus)
async def cancel_platform_login(platform: str) -> dict:
    _require_platform(platform)
    browser.cancel_login(platform)
    return {"platform": platform, "state": sessions.get_state(platform)}


@app.post("/api/download", response_model=DownloadResponse)
async def download(req: DownloadRequest, background_tasks: BackgroundTasks) -> dict:
    accepted: List[dict] = []
    skipped: List[str] = []

    for paper in req.papers:
        data = paper.model_dump()
        database.upsert_paper(data)
        if downloader.is_downloaded(paper.arxiv_id):
            skipped.append(paper.arxiv_id)
        else:
            database.set_status(paper.arxiv_id, "pending")
            accepted.append(data)

    if accepted:
        background_tasks.add_task(downloader.run_download_job, accepted)

    return DownloadResponse(
        accepted=[p["arxiv_id"] for p in accepted], skipped=skipped
    )


@app.get("/api/papers", response_model=List[PaperRecord])
async def list_papers(arxiv_ids: Optional[str] = Query(default=None)) -> List[dict]:
    ids = arxiv_ids.split(",") if arxiv_ids else None
    return database.list_papers(ids)


@app.get("/api/papers/{arxiv_id:path}/pdf")
async def get_paper_pdf(arxiv_id: str) -> FileResponse:
    paper = database.get_paper(arxiv_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    path = Path(paper.get("local_pdf_path") or (settings.papers_dir / f"{arxiv_id}.pdf"))
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"PDF not found: {arxiv_id}")
    return FileResponse(path, media_type="application/pdf")


_ARXIV_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@app.delete("/api/papers/{arxiv_id:path}")
async def delete_paper(arxiv_id: str) -> dict:
    paper = database.get_paper(arxiv_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    if not database.delete_paper(arxiv_id):
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    local_pdf = paper.get("local_pdf_path")
    if local_pdf:
        Path(local_pdf).unlink(missing_ok=True)
    elif _ARXIV_ID_SAFE_RE.match(arxiv_id):
        (settings.papers_dir / f"{arxiv_id}.pdf").unlink(missing_ok=True)
    return {"status": "ok"}


_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _valid_upload_token(token: str) -> bool:
    return bool(_TOKEN_RE.match(token))


_UPLOAD_ID_SAFE_RE = re.compile(r"[^0-9a-zA-Z._-]+")


def _slugify_upload_name(filename: str) -> str:
    stem = Path(filename).stem.strip()
    slug = _UPLOAD_ID_SAFE_RE.sub("-", stem)
    slug = re.sub(r"-{2,}", "-", slug).strip(".-_")
    return slug.lower()


def _write_upload_meta(token: str, filename: str) -> None:
    meta_path = settings.uploads_dir / f"{token}.json"
    meta_path.write_text(json.dumps({"filename": filename}), encoding="utf-8")


def _read_upload_filename(token: str) -> str:
    meta_path = settings.uploads_dir / f"{token}.json"
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return str(data.get("filename") or "")
    except (OSError, ValueError):
        return ""


def _cleanup_upload(token: str) -> None:
    (settings.uploads_dir / f"{token}.pdf").unlink(missing_ok=True)
    (settings.uploads_dir / f"{token}.json").unlink(missing_ok=True)


def _build_upload_arxiv_id(filename: str) -> str:
    slug = _slugify_upload_name(filename)
    if not slug:
        slug = uuid.uuid4().hex[:8]
    return f"upload-{slug}"


def _ensure_unique_arxiv_id(base: str) -> str:
    candidate = base
    suffix = 0
    while database.get_paper(candidate) is not None:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


@app.post("/api/papers/upload", response_model=PaperUploadResponse)
async def upload_paper_pdf(file: UploadFile = File(...)) -> dict:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    token = uuid.uuid4().hex
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = settings.uploads_dir / f"{token}.pdf"
    tmp_path.write_bytes(await file.read())
    _write_upload_meta(token, filename)

    try:
        text = pdf.extract_text(tmp_path)
    except PdfExtractionError as exc:
        _cleanup_upload(token)
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        metadata = await upload.extract_metadata(text)
    except ValueError as exc:
        _cleanup_upload(token)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        _cleanup_upload(token)
        raise HTTPException(status_code=502, detail=f"LLM 提取失败: {exc}")

    return {"pdf_token": token, "paper": metadata}


@app.post("/api/papers/upload/confirm", response_model=PaperRecord)
async def confirm_paper_pdf(req: UploadConfirmRequest) -> dict:
    token = req.pdf_token.strip()
    if not _valid_upload_token(token):
        raise HTTPException(status_code=400, detail="无效的上传 token")

    tmp_path = settings.uploads_dir / f"{token}.pdf"
    if not tmp_path.is_file():
        raise HTTPException(status_code=404, detail="上传已失效或不存在，请重新上传")

    arxiv_id = _ensure_unique_arxiv_id(_build_upload_arxiv_id(_read_upload_filename(token)))
    dest = settings.papers_dir / f"{arxiv_id}.pdf"
    settings.papers_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_path), str(dest))
    (settings.uploads_dir / f"{token}.json").unlink(missing_ok=True)

    database.upsert_paper(
        {
            "arxiv_id": arxiv_id,
            "title": req.paper.title,
            "authors": req.paper.authors,
            "abstract": req.paper.abstract,
            "published": req.paper.published,
            "categories": [],
            "pdf_url": "",
            "source": "upload",
            "url": req.paper.url or "",
        }
    )
    database.set_status(arxiv_id, "downloaded", str(dest))
    return database.get_paper(arxiv_id)


@app.get("/api/llm/presets", response_model=List[LLMPreset])
async def llm_presets() -> List[dict]:
    return LLM_PRESETS


@app.get("/api/llm/config", response_model=LLMConfigResponse)
async def get_llm_config() -> dict:
    return load_config()


@app.put("/api/llm/config", response_model=LLMConfigResponse)
async def update_llm_config(req: LLMConfigResponse) -> dict:
    try:
        return save_config(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _extract_error_body(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:200]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:200]
    if isinstance(error, str):
        return error[:200]
    return (resp.text or "").strip()[:200]


def _extract_content_summary(data: Any) -> str:
    try:
        choices = data.get("choices") if isinstance(data, dict) else None
        content = choices[0].get("message", {}).get("content", "")
    except (IndexError, AttributeError, TypeError):
        content = ""
    if isinstance(content, str) and content.strip():
        return content.strip()[:200]
    return "连接成功"


@app.post("/api/llm/test", response_model=LLMTestResponse)
async def test_llm_connection(req: LLMTestRequest) -> dict:
    base_url = (req.base_url or "").strip()
    api_key = (req.api_key or "").strip()
    model = (req.model or "").strip()

    if not base_url or not api_key or not model:
        return LLMTestResponse(ok=False, message="请先填写完整配置")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        latency_ms = int((time.perf_counter() - start) * 1000)
    except httpx.TimeoutException:
        return LLMTestResponse(ok=False, message="请求超时（15 秒）")
    except httpx.HTTPError as exc:
        message = _redact(str(exc), api_key)
        return LLMTestResponse(ok=False, message=f"请求失败：{message}")
    except Exception as exc:
        message = _redact(str(exc), api_key)
        return LLMTestResponse(ok=False, message=f"请求失败：{message}")

    if resp.status_code >= 400:
        detail = _redact(_extract_error_body(resp), api_key)
        return LLMTestResponse(
            ok=False,
            message=f"HTTP {resp.status_code}: {detail}" if detail else f"HTTP {resp.status_code}",
            latency_ms=latency_ms,
        )

    try:
        summary = _extract_content_summary(resp.json())
    except ValueError:
        summary = "连接成功"
    return LLMTestResponse(ok=True, message=summary, latency_ms=latency_ms)


_CONTEXT_LENGTH_KEYS = (
    "max_context_length",
    "context_length",
    "context_window",
    "context_window_tokens",
    "max_context_tokens",
    "contextwindow",
    "max_tokens",
)


def _to_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def _find_key(node: Any, target: str) -> Optional[Any]:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.lower() == target:
                return value
        for value in node.values():
            found = _find_key(value, target)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_key(value, target)
            if found is not None:
                return found
    return None


def _extract_context_length(item: Any) -> Optional[int]:
    if not isinstance(item, dict):
        return None
    for key in _CONTEXT_LENGTH_KEYS:
        value = _find_key(item, key)
        parsed = _to_int(value)
        if parsed is not None:
            return parsed
    return None


_REASONING_EFFORT_KEYS = (
    "reasoning_efforts",
    "supported_reasoning_efforts",
    "reasoning_effort_options",
    "reasoning_effort",
)


def _as_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return parts if parts else [text]


def _extract_reasoning_efforts(item: Any) -> List[str]:
    if not isinstance(item, dict):
        return []
    for key in _REASONING_EFFORT_KEYS:
        value = _find_key(item, key)
        result = _as_string_list(value)
        if result:
            return result
    return []


@app.post("/api/llm/models", response_model=LLMModelsResponse)
async def llm_models(req: LLMModelsRequest) -> dict:
    base_url = (req.base_url or "").strip()
    api_key = (req.api_key or "").strip()

    if not base_url:
        raise HTTPException(status_code=400, detail="请先填写 Base URL")

    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="获取模型列表超时（15 秒）")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=_redact(str(exc), api_key))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_redact(str(exc), api_key))

    if resp.status_code >= 400:
        detail = _redact(_extract_error_body(resp), api_key)
        raise HTTPException(
            status_code=resp.status_code,
            detail=detail or f"HTTP {resp.status_code}",
        )

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="返回内容不是有效 JSON")

    items = data.get("data") if isinstance(data, dict) else None
    models: List[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                efforts = _extract_reasoning_efforts(item) or guess_reasoning_efforts(item["id"])
                models.append(
                    {
                        "id": item["id"],
                        "context_length": _extract_context_length(item),
                        "reasoning_efforts": efforts,
                    }
                )
            elif isinstance(item, str):
                models.append(
                    {
                        "id": item,
                        "context_length": None,
                        "reasoning_efforts": guess_reasoning_efforts(item),
                    }
                )
    return {"models": models}


@app.post("/api/analyze/batch", response_model=AnalyzeBatchResponse)
async def analyze_batch(
    req: AnalyzeBatchRequest, background_tasks: BackgroundTasks
) -> dict:
    arxiv_ids = list(dict.fromkeys(req.arxiv_ids))
    if not arxiv_ids:
        raise HTTPException(status_code=400, detail="arxiv_ids must not be empty")
    not_downloaded = [
        arxiv_id
        for arxiv_id in arxiv_ids
        if not _is_downloaded(arxiv_id)
    ]
    if not_downloaded:
        raise HTTPException(
            status_code=409,
            detail=f"论文尚未下载，请先下载: {', '.join(not_downloaded)}",
        )
    for arxiv_id in arxiv_ids:
        database.set_analysis_status(arxiv_id, "pending", req.language)
    background_tasks.add_task(analysis.run_analysis_job, arxiv_ids, req.language)
    return {"arxiv_ids": arxiv_ids, "status": "pending"}


@app.post("/api/analyze/{arxiv_id}", response_model=AnalyzeResponse)
async def analyze_paper(
    arxiv_id: str, req: AnalyzeRequest, background_tasks: BackgroundTasks
) -> dict:
    if database.get_paper(arxiv_id) is None:
        raise HTTPException(status_code=404, detail=f"该论文尚未下载，请先下载后再分析: {arxiv_id}")
    if not _is_downloaded(arxiv_id):
        raise HTTPException(
            status_code=409, detail=f"论文尚未下载，请先下载: {arxiv_id}"
        )
    database.set_analysis_status(arxiv_id, "pending", req.language)
    background_tasks.add_task(analysis.run_analysis_job, [arxiv_id], req.language)
    return {"arxiv_id": arxiv_id, "status": "pending"}


@app.get("/api/analyses", response_model=List[AnalysisRecord])
async def list_analyses(arxiv_ids: Optional[str] = Query(default=None)) -> List[dict]:
    ids = arxiv_ids.split(",") if arxiv_ids else None
    return database.list_analyses(ids)


@app.get("/api/analyses/{arxiv_id}", response_model=AnalysisRecord)
async def get_analysis(arxiv_id: str) -> dict:
    record = database.get_analysis(arxiv_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No analysis for {arxiv_id}")
    return record


@app.get("/api/analyses/{arxiv_id}/export")
async def export_analysis(arxiv_id: str) -> Response:
    record = database.get_analysis(arxiv_id)
    if record is None or record.get("content") is None:
        raise HTTPException(status_code=404, detail=f"No analysis for {arxiv_id}")
    paper = database.get_paper(arxiv_id) or {"arxiv_id": arxiv_id, "title": arxiv_id}
    markdown = export.analysis_to_markdown(
        record["content"], paper, record.get("language", "zh")
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{arxiv_id}-analysis.md"'
        },
    )


@app.post("/api/review", response_model=ReviewRecord)
async def create_review(req: ReviewRequest, background_tasks: BackgroundTasks) -> dict:
    arxiv_ids = list(dict.fromkeys(req.arxiv_ids))
    if len(arxiv_ids) < 2:
        raise HTTPException(status_code=400, detail="at least two arxiv_ids required")
    review_id = database.insert_review(arxiv_ids, None, req.language, status="pending")
    background_tasks.add_task(analysis.run_review_job, review_id, arxiv_ids, req.language)
    record = database.get_review(review_id)
    if record is None:
        raise HTTPException(status_code=500, detail="review record not found")
    return record


@app.get("/api/reviews/{review_id}", response_model=ReviewRecord)
async def get_review(review_id: int) -> dict:
    record = database.get_review(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No review {review_id}")
    return record


@app.get("/api/reviews/{review_id}/export")
async def export_review(review_id: int) -> Response:
    record = database.get_review(review_id)
    if record is None or record.get("content") is None:
        raise HTTPException(status_code=404, detail=f"No review {review_id}")
    papers = [
        database.get_paper(arxiv_id)
        for arxiv_id in record.get("arxiv_ids", [])
    ]
    papers = [p for p in papers if p is not None]
    markdown = export.review_to_markdown(
        record["content"], papers, record.get("language", "zh")
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="review-{review_id}.md"'
        },
    )


@app.post("/api/innovations", response_model=InnovationRecord)
async def create_innovation(
    req: InnovationRequest, background_tasks: BackgroundTasks
) -> dict:
    arxiv_ids = list(dict.fromkeys(req.arxiv_ids))
    if not arxiv_ids:
        raise HTTPException(status_code=400, detail="arxiv_ids must not be empty")
    if not 1 <= req.count <= 10:
        raise HTTPException(status_code=400, detail="count must be between 1 and 10")
    innovation_id = database.insert_innovation(
        arxiv_ids, None, req.language, status="pending"
    )
    background_tasks.add_task(
        innovation.run_innovation_job, innovation_id, arxiv_ids, req.language, req.count
    )
    record = database.get_innovation(innovation_id)
    if record is None:
        raise HTTPException(status_code=500, detail="innovation record not found")
    return record


@app.get("/api/innovations", response_model=List[InnovationHistoryItem])
async def list_innovations() -> List[dict]:
    return database.list_innovation_history()


@app.delete("/api/innovations")
async def clear_innovations() -> dict:
    database.clear_innovations()
    return {"status": "ok"}


@app.get("/api/innovations/{innovation_id}", response_model=InnovationRecord)
async def get_innovation(innovation_id: int) -> dict:
    record = database.get_innovation(innovation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No innovation {innovation_id}")
    return record


@app.delete("/api/innovations/{innovation_id}")
async def delete_innovation(innovation_id: int) -> dict:
    if not database.delete_innovation(innovation_id):
        raise HTTPException(status_code=404, detail=f"No innovation {innovation_id}")
    return {"status": "ok"}


@app.get("/api/innovations/{innovation_id}/export")
async def export_innovation(innovation_id: int) -> Response:
    record = database.get_innovation(innovation_id)
    if record is None or record.get("content") is None:
        raise HTTPException(status_code=404, detail=f"No innovation {innovation_id}")
    papers = [
        database.get_paper(arxiv_id)
        for arxiv_id in record.get("arxiv_ids", [])
    ]
    papers = [p for p in papers if p is not None]
    markdown = export.innovations_to_markdown(
        record["content"], papers, record.get("language", "zh")
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="innovations-{innovation_id}.md"'
        },
    )


def _experiment_source_label(record: dict) -> str:
    if record.get("source_type") == "innovation":
        return f"创新点 #{record.get('innovation_id')}"
    arxiv_ids = record.get("arxiv_ids", [])
    return "论文: " + (", ".join(arxiv_ids) if arxiv_ids else "-")


def _experiment_history_item(record: dict) -> dict:
    record["source_label"] = (
        f"创新点 #{record.get('innovation_id')}"
        if record.get("source_type") == "innovation"
        else f"论文: {len(record.get('arxiv_ids', []))} 篇"
    )
    return record


@app.get("/api/experiments", response_model=List[ExperimentHistoryItem])
async def list_experiments() -> List[dict]:
    return [_experiment_history_item(r) for r in database.list_experiment_history()]


@app.post("/api/experiments", response_model=ExperimentRecord)
async def create_experiment(
    req: ExperimentRequest, background_tasks: BackgroundTasks
) -> dict:
    if req.source_type not in ("innovation", "papers"):
        raise HTTPException(
            status_code=400, detail="source_type must be 'innovation' or 'papers'"
        )
    if not 1 <= req.count <= 3:
        raise HTTPException(status_code=400, detail="count must be between 1 and 3")

    arxiv_ids = list(dict.fromkeys(req.arxiv_ids or []))
    innovation_id = req.innovation_id

    if req.source_type == "innovation":
        if innovation_id is None:
            raise HTTPException(
                status_code=400,
                detail="innovation_id is required for source_type=innovation",
            )
        innovation = database.get_innovation(innovation_id)
        if innovation is None:
            raise HTTPException(
                status_code=404, detail=f"Innovation not found: {innovation_id}"
            )
        arxiv_ids = innovation.get("arxiv_ids", [])
    else:
        if not arxiv_ids:
            raise HTTPException(
                status_code=400,
                detail="arxiv_ids must not be empty for source_type=papers",
            )

    experiment_id = database.insert_experiment(
        req.source_type, innovation_id, arxiv_ids, None, req.language, status="pending"
    )
    background_tasks.add_task(
        experiment.run_experiment_job,
        experiment_id,
        req.source_type,
        innovation_id,
        arxiv_ids,
        req.language,
        req.count,
    )
    record = database.get_experiment(experiment_id)
    if record is None:
        raise HTTPException(status_code=500, detail="experiment record not found")
    return record


@app.get("/api/experiments/{experiment_id}", response_model=ExperimentRecord)
async def get_experiment(experiment_id: int) -> dict:
    record = database.get_experiment(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No experiment {experiment_id}")
    return record


@app.delete("/api/experiments/{experiment_id}")
async def delete_experiment(experiment_id: int) -> dict:
    if not database.delete_experiment(experiment_id):
        raise HTTPException(status_code=404, detail=f"No experiment {experiment_id}")
    return {"status": "ok"}


@app.delete("/api/experiments")
async def clear_experiments() -> dict:
    database.clear_experiments()
    return {"status": "ok"}


@app.get("/api/experiments/{experiment_id}/export")
async def export_experiment(experiment_id: int) -> Response:
    record = database.get_experiment(experiment_id)
    if record is None or record.get("content") is None:
        raise HTTPException(status_code=404, detail=f"No experiment {experiment_id}")
    markdown = export.experiments_to_markdown(
        record["content"],
        _experiment_source_label(record),
        record.get("language", "zh"),
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="experiments-{experiment_id}.md"'
        },
    )


def _require_server(server_id: str) -> dict:
    server = servers.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return server


@app.get("/api/servers", response_model=List[ServerOutput])
async def list_servers() -> List[dict]:
    return [servers.redact(s) for s in servers.list_servers()]


@app.post("/api/servers", response_model=ServerOutput)
async def create_server(req: ServerInput) -> dict:
    return servers.redact(servers.add_server(req.model_dump()))


@app.put("/api/servers/{server_id}", response_model=ServerOutput)
async def update_server(server_id: str, req: ServerUpdate) -> dict:
    updated = servers.update_server(server_id, req.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return servers.redact(updated)


@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: str) -> dict:
    if not servers.delete_server(server_id):
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return {"status": "ok"}


@app.post("/api/servers/{server_id}/test", response_model=TestConnectionResponse)
async def test_server(server_id: str) -> dict:
    server = _require_server(server_id)
    return ssh.test_connection(server)


@app.post("/api/servers/{server_id}/deploy/clone", response_model=CloneResponse)
async def deploy_clone(server_id: str, req: CloneRequest) -> dict:
    server = _require_server(server_id)
    if not req.repo_url.strip():
        raise HTTPException(status_code=400, detail="repo_url must not be empty")
    command = f"git clone {shlex.quote(req.repo_url)} {shlex.quote(req.target_dir)}"
    try:
        output = ssh.exec_command(server, command)
    except ssh.SSHError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"output": output}


@app.post("/api/servers/{server_id}/deploy/upload", response_model=UploadResponse)
async def deploy_upload(server_id: str, request: Request) -> dict:
    server = _require_server(server_id)
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        return await _deploy_upload_files(server, request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 或 multipart 表单")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
    local_path = (body.get("local_path") or "").strip()
    remote_path = (body.get("remote_path") or "").strip()
    if not local_path:
        raise HTTPException(status_code=400, detail="local_path must not be empty")
    try:
        return ssh.upload(server, local_path, remote_path)
    except ssh.SSHError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


_DRIVE_PREFIX_RE = re.compile(r"^[a-zA-Z]:$")


def _safe_rel_path(name: str) -> str:
    parts = [
        part
        for part in name.replace("\\", "/").split("/")
        if part not in ("", ".", "..") and not _DRIVE_PREFIX_RE.match(part)
    ]
    return "/".join(parts) if parts else "upload"


def _resolve_upload_target(tmpdir: Path, rel: str) -> Path:
    root = tmpdir.resolve()
    target = (tmpdir / rel).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail=f"非法文件名: {rel}")
    return target


async def _deploy_upload_files(server: dict, request: Request) -> dict:
    form = await request.form()
    remote_path = str(form.get("remote_path") or "").strip()
    files = form.getlist("files")
    if not remote_path:
        raise HTTPException(status_code=400, detail="remote_path must not be empty")
    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")
    tmpdir = Path(tempfile.mkdtemp(prefix="openlab-upload-"))
    try:
        for item in files:
            if not hasattr(item, "read"):
                continue
            rel = _safe_rel_path(getattr(item, "filename", "") or "upload")
            target = _resolve_upload_target(tmpdir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(await item.read())
        try:
            return ssh.upload(server, str(tmpdir), remote_path)
        except ssh.SSHError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.post("/api/servers/{server_id}/exec", response_model=ExecResponse)
async def exec_server(server_id: str, req: ExecRequest) -> dict:
    server = _require_server(server_id)
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="command must not be empty")
    try:
        output = ssh.exec_command(server, req.command)
    except ssh.SSHError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"output": output}


@app.post("/api/servers/{server_id}/monitor", response_model=MonitorResponse)
async def monitor_server(server_id: str) -> dict:
    server = _require_server(server_id)
    return monitor.collect(server)


@app.websocket("/api/servers/{server_id}/terminal")
async def server_terminal_ws(websocket: WebSocket, server_id: str) -> None:
    await websocket.accept()
    try:
        server = _require_server(server_id)
    except HTTPException as exc:
        await websocket.send_text(
            json.dumps({"type": "error", "message": str(exc.detail)})
        )
        await websocket.close()
        return
    await terminal.ssh_terminal_ws(websocket, server)


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


@app.websocket("/api/agent/ws")
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


@app.get("/api/agent/sessions/{session_id}/export")
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


@app.get("/api/agent/sessions", response_model=List[AgentSessionItem])
async def list_agent_sessions() -> List[dict]:
    return list_sessions()


@app.post("/api/agent/sessions", response_model=AgentSessionItem)
async def create_agent_session(req: AgentSessionCreate) -> dict:
    session = create_session(title=req.title)
    detail = get_session_detail(session.session_id)
    return detail if detail is not None else {"id": session.session_id, "title": session.title}


@app.get("/api/agent/sessions/{session_id}", response_model=AgentSessionDetail)
async def get_agent_session(session_id: str) -> dict:
    detail = get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return detail


@app.put("/api/agent/sessions/{session_id}", response_model=AgentSessionItem)
async def update_agent_session(session_id: str, req: AgentSessionUpdate) -> dict:
    record = update_title(session_id, req.title)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return record


@app.delete("/api/agent/sessions/{session_id}")
async def delete_agent_session(session_id: str) -> dict:
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"status": "ok"}
