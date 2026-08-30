"""Innovation routes."""
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response

from .. import database, export, innovation
from ..schemas import InnovationHistoryItem, InnovationRecord, InnovationRequest

router = APIRouter()


@router.get("", response_model=List[InnovationHistoryItem])
async def list_innovations() -> List[dict]:
    return database.list_innovation_history()


@router.get("/{innovation_id}", response_model=InnovationRecord)
async def get_innovation(innovation_id: int) -> dict:
    record = database.get_innovation(innovation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No innovation {innovation_id}")
    return record


@router.get("/{innovation_id}/export")
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


@router.post("", response_model=InnovationRecord)
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


@router.delete("")
async def clear_innovations() -> dict:
    database.clear_innovations()
    return {"status": "ok"}


@router.delete("/{innovation_id}")
async def delete_innovation(innovation_id: int) -> dict:
    if not database.delete_innovation(innovation_id):
        raise HTTPException(status_code=404, detail=f"No innovation {innovation_id}")
    return {"status": "ok"}
