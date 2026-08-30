"""Analysis routes: analysis jobs and analysis records."""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response

from .. import analysis, database, export
from ..schemas import (
    AnalysisRecord,
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)

router = APIRouter()
analyze_router = APIRouter()


def _is_downloaded(arxiv_id: str) -> bool:
    paper = database.get_paper(arxiv_id)
    return bool(
        paper and paper.get("local_pdf_path") and paper.get("status") == "downloaded"
    )


@router.get("", response_model=List[AnalysisRecord])
async def list_analyses(arxiv_ids: Optional[str] = Query(default=None)) -> List[dict]:
    ids = arxiv_ids.split(",") if arxiv_ids else None
    return database.list_analyses(ids)


@router.get("/{arxiv_id}", response_model=AnalysisRecord)
async def get_analysis(arxiv_id: str) -> dict:
    record = database.get_analysis(arxiv_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No analysis for {arxiv_id}")
    return record


@router.get("/{arxiv_id}/export")
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


@analyze_router.post("/batch", response_model=AnalyzeBatchResponse)
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


@analyze_router.post("/{arxiv_id}", response_model=AnalyzeResponse)
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
