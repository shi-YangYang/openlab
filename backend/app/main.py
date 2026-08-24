"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from . import database, downloader
from .arxiv import ArxivClient
from .config import settings
from .llm import decompose_topic
from .llm_config import get_effective_config, save_config
from .presets import LLM_PRESETS
from .schemas import (
    DownloadRequest,
    DownloadResponse,
    LLMConfig,
    LLMConfigUpdate,
    LLMPreset,
    Paper,
    PaperRecord,
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
