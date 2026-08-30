"""Paper translation routes: start, progress, fetch, PDF serving, and deletion."""
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from .. import database
from ..schemas import TranslationStartRequest

router = APIRouter()

# in-memory progress for running translations (module-level, single process)
translation_progress_state: dict[str, int] = {}
translation_progress_message: dict[str, str] = {}


@router.get("/{arxiv_id:path}/translation/pdf")
async def get_translation_pdf(arxiv_id: str) -> FileResponse:
    from ..translation import translated_pdf_path

    pdf_path = translated_pdf_path(arxiv_id)
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"翻译 PDF 不存在（路径: {pdf_path}，请先执行翻译）",
        )
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", arxiv_id)[:60] or "paper"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}-translated.pdf"'},
    )


@router.get("/{arxiv_id:path}/translation")
async def get_translation(arxiv_id: str) -> dict:
    from ..translation import has_translation, read_translation

    paper = database.get_paper(arxiv_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    translated = has_translation(arxiv_id)
    content = read_translation(arxiv_id) if translated else None
    return {"translated": translated, "content": content}


@router.get("/{arxiv_id:path}/translate/progress")
async def translation_progress_endpoint(arxiv_id: str) -> dict:
    from ..translation import has_translation, read_translation

    translated = has_translation(arxiv_id)
    return {
        "translated": translated,
        "progress": 100 if translated else translation_progress_state.get(arxiv_id, 0),
        "message": "翻译完成" if translated else translation_progress_message.get(arxiv_id, ""),
        "content": read_translation(arxiv_id) if translated else None,
    }


@router.post("/{arxiv_id:path}/translate")
async def start_translation(
    arxiv_id: str, req: TranslationStartRequest, background_tasks: BackgroundTasks
) -> dict:
    from ..translation import extract_pdf_text, has_translation, translate_paper

    if database.get_paper(arxiv_id) is None:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    if has_translation(arxiv_id):
        return {"status": "done", "progress": 100, "message": "已有翻译"}

    # Pre-check: LLM must be configured
    from ..llm_config import get_effective_config

    cfg = get_effective_config()
    if not cfg.get("api_key"):
        raise HTTPException(
            status_code=400, detail="LLM 未配置，请先到设置页配置 API Key"
        )

    # Pre-check: extract text and detect source language
    try:
        text = extract_pdf_text(arxiv_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if _is_mostly_chinese(text):
        raise HTTPException(
            status_code=400, detail="该论文已经是中文，无需翻译"
        )

    async def on_progress(pct: int, msg: str) -> None:
        translation_progress_state[arxiv_id] = pct
        translation_progress_message[arxiv_id] = msg

    async def job() -> None:
        try:
            await translate_paper(arxiv_id, req.language, on_progress=on_progress)
        except Exception as exc:  # noqa: BLE001 - surface to progress poll
            translation_progress_state[arxiv_id] = -1
            translation_progress_message[arxiv_id] = _redact(str(exc), cfg.get("api_key", ""))

    background_tasks.add_task(job)
    return {"status": "started", "progress": 0, "message": "排队中"}


@router.delete("/{arxiv_id:path}/translation")
async def delete_translation_endpoint(arxiv_id: str) -> dict:
    from ..translation import delete_translation

    delete_translation(arxiv_id)
    translation_progress_state.pop(arxiv_id, None)
    translation_progress_message.pop(arxiv_id, None)
    return {"status": "ok"}


def _redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _is_mostly_chinese(text: str) -> bool:
    """Return True when CJK chars dominate the text (already a Chinese paper)."""
    sample = text[:8000]
    cjk = sum(1 for ch in sample if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in sample if ch.isascii() and ch.isalpha())
    return cjk > letters and cjk > 200
