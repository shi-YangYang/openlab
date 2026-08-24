"""FastAPI application entry point."""
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, List, Optional

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from . import analysis, database, downloader, experiment, export, innovation
from .arxiv import ArxivClient
from .config import settings
from .llm import decompose_topic
from .llm_config import get_effective_config, save_config
from .presets import LLM_PRESETS
from .schemas import (
    AnalysisRecord,
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    DownloadRequest,
    DownloadResponse,
    ExperimentRecord,
    ExperimentRequest,
    LLMConfig,
    LLMConfigUpdate,
    LLMPreset,
    LLMTestRequest,
    LLMTestResponse,
    InnovationHistoryItem,
    InnovationRecord,
    InnovationRequest,
    Paper,
    PaperRecord,
    ReviewRecord,
    ReviewRequest,
    SearchHistoryDetail,
    SearchHistoryItem,
    SearchRequest,
    TopicSearchRequest,
    TopicSearchResponse,
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


@app.post("/api/search", response_model=List[Paper])
async def search(
    req: SearchRequest,
    arxiv_client: ArxivClient = Depends(get_arxiv_client),
) -> List[dict]:
    papers = await arxiv_client.search(
        req.query, max_results=req.max_results, category=req.category
    )
    result = _filter_by_date(papers, req.date_from, req.date_to)[: req.max_results]
    database.save_search_history(req.query, "keyword", result)
    return result


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

    papers = await arxiv_client.search(
        query, max_results=req.max_results, category=req.category
    )
    papers = _filter_by_date(papers, req.date_from, req.date_to)[: req.max_results]
    database.save_search_history(req.topic, "topic", papers)
    return {"query": query, "papers": papers}


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


@app.get("/api/llm/presets", response_model=List[LLMPreset])
async def llm_presets() -> List[dict]:
    return LLM_PRESETS


@app.get("/api/llm/config", response_model=LLMConfig)
async def get_llm_config() -> dict:
    return get_effective_config()


@app.put("/api/llm/config", response_model=LLMConfig)
async def update_llm_config(req: LLMConfigUpdate) -> dict:
    save_config(
        base_url=req.base_url,
        api_key=req.api_key,
        model=req.model,
    )
    return get_effective_config()


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
