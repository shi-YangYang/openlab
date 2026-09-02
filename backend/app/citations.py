"""Citation builders for BibTeX and GB/T 7714 exports (spec-038 FR-6).

Metadata is best-effort: papers from any source (arxiv/baidu/cnki/upload) may
miss authors/published/url, in which case the corresponding field or segment
is simply omitted while the entry stays valid.
"""
import json
import re
from datetime import date
from typing import Any, Dict, List, Optional

_LATEX_MAP = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_"}
_LATEX_RE = re.compile(r"[&%#_]")


def _latex_escape(text: str) -> str:
    return _LATEX_RE.sub(lambda match: _LATEX_MAP[match.group(0)], text)


def _as_author_list(paper: Dict[str, Any]) -> List[str]:
    authors = paper.get("authors")
    if isinstance(authors, list):
        return [str(a).strip() for a in authors if str(a).strip()]
    if isinstance(authors, str):
        raw = authors.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except ValueError:
            return [raw]
        if isinstance(parsed, list):
            return [str(a).strip() for a in parsed if str(a).strip()]
        return [str(parsed).strip()]
    return []


def _title(paper: Dict[str, Any]) -> str:
    return str(paper.get("title") or "").strip()


def _year(paper: Dict[str, Any]) -> Optional[str]:
    match = re.search(r"\d{4}", str(paper.get("published") or ""))
    return match.group(0) if match else None


def _url(paper: Dict[str, Any]) -> str:
    return str(paper.get("url") or paper.get("pdf_url") or "").strip()


def _is_arxiv(paper: Dict[str, Any]) -> bool:
    return str(paper.get("source") or "arxiv").strip().lower() == "arxiv"


def _bibtex_key(paper: Dict[str, Any], used: set) -> str:
    authors = _as_author_list(paper)
    surname = ""
    if authors:
        surname = re.sub(r"[^0-9A-Za-z]", "", authors[0].split()[-1]).lower()
    year = _year(paper) or ""
    first_word = ""
    for token in re.split(r"[^0-9A-Za-z]+", _title(paper)):
        if token:
            first_word = token.lower()
            break
    base = f"{surname or 'unknown'}{year}{first_word or 'untitled'}"
    candidate = base
    suffix = 0
    while candidate in used:
        suffix += 1
        candidate = f"{base}-{chr(96 + suffix)}"
    used.add(candidate)
    return candidate


def build_bibtex(papers: List[Dict[str, Any]]) -> str:
    """Render papers as BibTeX entries separated by blank lines."""
    used: set = set()
    entries: List[str] = []
    for paper in papers:
        key = _bibtex_key(paper, used)
        fields: List[str] = []
        title = _title(paper)
        if title:
            fields.append(f"  title = {{{_latex_escape(title)}}}")
        authors = _as_author_list(paper)
        if authors:
            fields.append(f"  author = {{{_latex_escape(' and '.join(authors))}}}")
        year = _year(paper)
        if year:
            fields.append(f"  year = {{{year}}}")
        if _is_arxiv(paper):
            arxiv_id = str(paper.get("arxiv_id") or "").strip()
            fields.append(f"  journal = {{arXiv preprint arXiv:{arxiv_id}}}")
        else:
            url = _url(paper)
            if url:
                fields.append(f"  note = {{Available at: {url}}}")
        if _url(paper):
            fields.append(f"  url = {{{_url(paper)}}}")
        body = ",\n".join(fields)
        entries.append(f"@article{{{key},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def build_gbt7714(papers: List[Dict[str, Any]]) -> str:
    """Render papers as a numbered GB/T 7714 reference list."""
    access_date = date.today().strftime("%Y-%m-%d")
    lines: List[str] = []
    for index, paper in enumerate(papers, start=1):
        segments: List[str] = []
        authors = _as_author_list(paper)
        if authors:
            author_text = ", ".join(authors[:3])
            if len(authors) > 3:
                author_text += ", 等"
            segments.append(author_text)
        title = _title(paper)
        if title:
            segments.append(f"{title}[J/OL]")
        year = _year(paper)
        if year:
            segments.append(f"{year}[{access_date}]")
        url = _url(paper)
        if url:
            segments.append(url)
        if not segments:
            segments.append(str(paper.get("arxiv_id") or "").strip() or "(metadata missing)")
        lines.append(f"[{index}] " + ". ".join(segments) + ".")
    return "\n".join(lines) + ("\n" if lines else "")
