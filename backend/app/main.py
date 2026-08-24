"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import analysis, database, downloader, export
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
    LLMConfig,
    LLMConfigUpdate,
    LLMPreset,
    Paper,
    PaperRecord,
    ReviewRecord,
    ReviewRequest,
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
    return _filter_by_date(papers, req.date_from, req.date_to)[: req.max_results]


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
    return {"query": query, "papers": papers}


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
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
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
