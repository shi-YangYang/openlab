"""Paper routes: library, download, PDF serving, and uploads."""
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, Response

from .. import database, downloader, pdf, upload
from ..arxiv import ArxivClient
from ..citations import build_bibtex, build_gbt7714
from ..config import settings
from ..pdf import PdfExtractionError
from ..schemas import (
    CitationExportRequest,
    DownloadRequest,
    DownloadResponse,
    PaperRecord,
    PaperUploadResponse,
    UploadConfirmRequest,
    UploadConfirmResponse,
)

router = APIRouter()
download_router = APIRouter()


def get_arxiv_client(request: Request) -> ArxivClient:
    return request.app.state.arxiv_client


@router.get("", response_model=List[PaperRecord])
async def list_papers(arxiv_ids: Optional[str] = Query(default=None)) -> List[dict]:
    ids = arxiv_ids.split(",") if arxiv_ids else None
    return database.list_papers(ids)


@router.get("/search")
async def search_library(
    q: str = Query(default=""), limit: int = Query(default=50, ge=1, le=200)
) -> List[dict]:
    """Full-text search inside the local library (spec-037 FR-3)."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="检索词 q 不能为空")
    if not database.fts_available():
        raise HTTPException(
            status_code=503,
            detail="库内全文检索不可用：当前 SQLite 不支持 FTS5/trigram",
        )
    return database.search_paper_fts(q.strip(), limit)


@router.post("/search/rebuild")
async def rebuild_library_index() -> dict:
    """Rebuild the whole FTS index; returns the number of indexed papers."""
    if not database.fts_available():
        raise HTTPException(
            status_code=503,
            detail="库内全文检索不可用：当前 SQLite 不支持 FTS5/trigram",
        )
    return {"rebuilt": database.rebuild_paper_fts()}


@router.post("/export/citations")
async def export_citations(req: CitationExportRequest) -> Response:
    """Export selected papers as BibTeX / GB/T 7714 (spec-038 FR-6)."""
    ids = [str(arxiv_id).strip() for arxiv_id in req.arxiv_ids if str(arxiv_id).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="arxiv_ids 不能为空")
    fmt = str(req.format or "").strip().lower()
    if fmt not in ("bibtex", "gbt7714"):
        raise HTTPException(status_code=400, detail="format 必须为 bibtex 或 gbt7714")
    papers = []
    for arxiv_id in ids:
        paper = database.get_paper(arxiv_id)
        if paper is None:
            raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
        papers.append(paper)
    if fmt == "bibtex":
        content, filename = build_bibtex(papers), "papers.bib"
    else:
        content, filename = build_gbt7714(papers), "references.txt"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{arxiv_id:path}/pdf")
async def get_paper_pdf(arxiv_id: str) -> FileResponse:
    paper = database.get_paper(arxiv_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    path = Path(paper.get("local_pdf_path") or (settings.papers_dir / f"{arxiv_id}.pdf"))
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"PDF not found: {arxiv_id}")
    return FileResponse(path, media_type="application/pdf")


@download_router.post("", response_model=DownloadResponse)
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


@router.post("/upload", response_model=PaperUploadResponse)
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


@router.post("/upload/confirm", response_model=UploadConfirmResponse)
async def confirm_paper_pdf(req: UploadConfirmRequest) -> dict:
    token = req.pdf_token.strip()
    if not _valid_upload_token(token):
        raise HTTPException(status_code=400, detail="无效的上传 token")

    tmp_path = settings.uploads_dir / f"{token}.pdf"
    if not tmp_path.is_file():
        raise HTTPException(status_code=404, detail="上传已失效或不存在，请重新上传")

    duplicate_of: Optional[str] = None
    new_title = req.paper.title.strip()
    for existing in database.list_papers():
        if existing.get("source") != "upload":
            continue
        if (existing.get("title") or "").strip() == new_title:
            duplicate_of = existing.get("arxiv_id")
            break

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
    result = database.get_paper(arxiv_id)
    result["duplicate_of"] = duplicate_of
    return result


@router.delete("/{arxiv_id:path}")
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
    from ..translation import delete_translation

    delete_translation(arxiv_id)
    return {"status": "ok"}


_ARXIV_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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
