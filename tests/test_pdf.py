from pathlib import Path

import pytest

from app.pdf import PdfExtractionError, extract_text


def _make_pdf(path: Path, text: str) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_extract_text_from_pdf(tmp_path):
    path = tmp_path / "sample.pdf"
    _make_pdf(path, "Hello openlab research agent")
    assert "Hello openlab research agent" in extract_text(path)


def test_extract_text_missing_file_raises(tmp_path):
    with pytest.raises(PdfExtractionError):
        extract_text(tmp_path / "missing.pdf")


def test_extract_text_empty_pdf_raises(tmp_path):
    path = tmp_path / "empty.pdf"
    _make_pdf(path, "")
    with pytest.raises(PdfExtractionError):
        extract_text(path)
