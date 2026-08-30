"""Review routes."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response

from .. import analysis, database, export
from ..schemas import ReviewRecord, ReviewRequest

router = APIRouter()
review_router = APIRouter()


@router.get("/{review_id}", response_model=ReviewRecord)
async def get_review(review_id: int) -> dict:
    record = database.get_review(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No review {review_id}")
    return record


@router.get("/{review_id}/export")
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


@review_router.post("", response_model=ReviewRecord)
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
