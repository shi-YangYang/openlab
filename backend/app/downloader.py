"""PDF download and background job execution."""
from pathlib import Path
from typing import Any, Dict, List

import httpx

from . import database
from .config import settings


def is_downloaded(arxiv_id: str) -> bool:
    record = database.get_paper(arxiv_id)
    if record and record.get("status") == "downloaded" and record.get("local_pdf_path"):
        return Path(record["local_pdf_path"]).exists()
    return False


async def download_pdf(
    arxiv_id: str, pdf_url: str, client: httpx.AsyncClient
) -> Path:
    settings.papers_dir.mkdir(parents=True, exist_ok=True)
    path = settings.papers_dir / f"{arxiv_id}.pdf"
    resp = await client.get(pdf_url)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


async def run_download_job(papers: List[Dict[str, Any]]) -> None:
    """Download a batch of PDFs, updating status in the database.

    Papers already downloaded are skipped (their status is kept as
    ``downloaded``). Failures are recorded with status ``failed``.
    """
    client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    try:
        for paper in papers:
            arxiv_id = paper["arxiv_id"]
            if is_downloaded(arxiv_id):
                database.set_status(arxiv_id, "downloaded")
                continue

            database.set_status(arxiv_id, "downloading")
            pdf_url = paper.get("pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}"
            try:
                path = await download_pdf(arxiv_id, pdf_url, client)
                database.set_status(arxiv_id, "downloaded", str(path))
            except Exception:
                database.set_status(arxiv_id, "failed")
    finally:
        await client.aclose()
