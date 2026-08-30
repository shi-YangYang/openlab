"""Search routes: keyword/topic aggregation and search history."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from .. import database
from ..arxiv import ArxivClient
from ..llm import decompose_topic
from ..schemas import (
    SearchHistoryDetail,
    SearchHistoryItem,
    SearchRequest,
    SearchResponse,
    TopicSearchRequest,
    TopicSearchResponse,
)
from ..search.aggregator import search as aggregate_search
from .papers import get_arxiv_client

router = APIRouter()


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


@router.get("/history", response_model=List[SearchHistoryItem])
async def list_search_history() -> List[dict]:
    return database.list_search_history()


@router.get("/history/{history_id}", response_model=SearchHistoryDetail)
async def get_search_history(history_id: int) -> dict:
    record = database.get_search_history(history_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"History not found: {history_id}")
    return record


@router.post("", response_model=SearchResponse)
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


@router.post("/topic", response_model=TopicSearchResponse)
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


@router.delete("/history/{history_id}")
async def delete_search_history(history_id: int) -> dict:
    if not database.delete_search_history(history_id):
        raise HTTPException(status_code=404, detail=f"History not found: {history_id}")
    return {"status": "ok"}


@router.delete("/history")
async def clear_search_history() -> dict:
    database.clear_search_history()
    return {"status": "ok"}
