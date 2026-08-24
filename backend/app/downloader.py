"""PDF download and background job execution."""
import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx

from . import database
from .config import settings


def is_downloaded(arxiv_id: str) -> bool:
    record = database.get_paper(arxiv_id)
    if record and record.get("status") == "downloaded" and record.get("local_pdf_path"):
        return Path(record["local_pdf_path"]).exists()
    return False


async def download_pdf(
    arxiv_id: str,
    pdf_url: str,
    client: httpx.AsyncClient,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> Path:
    """Stream a PDF to disk, reporting byte progress (0-100) via ``on_progress``.

    The response is streamed (``client.stream`` + ``aiter_bytes``) and progress
    is computed against ``content-length`` so large PDFs no longer require
    loading the whole body into memory (FR-15).
    """
    settings.papers_dir.mkdir(parents=True, exist_ok=True)
    path = settings.papers_dir / f"{arxiv_id}.pdf"
    async with client.stream("GET", pdf_url) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        written = 0
        with path.open("wb") as f:
            async for chunk in resp.aiter_bytes():
                f.write(chunk)
                written += len(chunk)
                if total and on_progress is not None:
                    await on_progress(min(99, int(written * 100 / total)))
    if on_progress is not None:
        await on_progress(100)
    return path


async def run_download_job(papers: List[Dict[str, Any]]) -> None:
    """Download a batch of PDFs, updating status in the database.

    Papers already downloaded are skipped (their status is kept as
    ``downloaded``). Failures are recorded with status ``failed``. Per-paper
    progress is written to ``papers.progress`` (FR-15).
    """
    client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    try:
        for paper in papers:
            arxiv_id = paper["arxiv_id"]
            if is_downloaded(arxiv_id):
                database.set_status(arxiv_id, "downloaded")
                database.set_download_progress(arxiv_id, 100)
                continue

            database.set_status(arxiv_id, "downloading")
            database.set_download_progress(arxiv_id, 0)
            pdf_url = paper.get("pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}"

            async def on_progress(progress: int, _id: str = arxiv_id) -> None:
                database.set_download_progress(_id, progress)

            try:
                path = await _download_with_retry(
                    arxiv_id, pdf_url, client, on_progress=on_progress
                )
                database.set_status(arxiv_id, "downloaded", str(path))
                database.set_download_progress(arxiv_id, 100)
            except Exception:
                database.set_status(arxiv_id, "failed")
                database.set_download_progress(arxiv_id, 0)
    finally:
        await client.aclose()


async def _download_with_retry(
    arxiv_id: str,
    pdf_url: str,
    client: httpx.AsyncClient,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> Path:
    """Download a PDF, retrying transient failures up to ``download_max_retries``.

    A short delay (``download_retry_delay``) is inserted between attempts.
    Raises the last error if every attempt fails.
    """
    max_retries = settings.download_max_retries
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return await download_pdf(arxiv_id, pdf_url, client, on_progress=on_progress)
        except Exception as exc:  # noqa: BLE001 - retry any download error
            last_error = exc
            if attempt < max_retries:
                await asyncio.sleep(settings.download_retry_delay)
    raise last_error  # type: ignore[misc]
