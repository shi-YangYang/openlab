"""PDF text extraction via PyMuPDF.

Reuses the PDF files downloaded by spec-001 (stored under
``settings.papers_dir``). Extraction failures (missing file, corrupt PDF,
scanned/empty text) are surfaced as :class:`PdfExtractionError` so callers can
mark the analysis as ``failed`` with a clear reason.
"""
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover - older PyMuPDF exposes ``fitz``
    import fitz as pymupdf  # type: ignore


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be opened or yields no extractable text."""


def extract_text(pdf_path: Path) -> str:
    """Extract and concatenate the text of every page of a PDF file.

    Raises ``PdfExtractionError`` if the file is missing, cannot be opened, or
    yields no extractable text.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise PdfExtractionError(f"PDF file not found: {path}")

    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:  # noqa: BLE001 - PyMuPDF raises various errors
        raise PdfExtractionError(f"Failed to open PDF: {exc}") from exc

    try:
        pages = [page.get_text() for page in doc]
    except Exception as exc:  # noqa: BLE001
        raise PdfExtractionError(f"Failed to extract text: {exc}") from exc
    finally:
        doc.close()

    text = "\n".join(page.strip() for page in pages if page and page.strip()).strip()
    if not text:
        raise PdfExtractionError(f"No extractable text found in PDF: {path}")
    return text
