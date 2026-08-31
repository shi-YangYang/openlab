"""Paper translation: extract PDF text, translate via LLM chunk-by-chunk,
and store the translated markdown next to the source PDF."""
import asyncio
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import database
from .config import settings
from .llm_config import get_effective_config
from .redact import redact_secrets

CHUNK_CHARS = 3500
CONCURRENCY = 8
MAX_CHUNKS = 60
CHUNK_RETRIES = 2


async def _translate_chunk_with_retry(
    chunk: str, language: str, index: int, on_error: Optional[Callable[[str], Any]] = None
) -> str:
    for attempt in range(CHUNK_RETRIES + 1):
        try:
            return await _translate_chunk(chunk, language, index)
        except Exception as exc:  # noqa: BLE001 - one chunk must not kill the run
            if attempt < CHUNK_RETRIES:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            message = redact_secrets(str(exc))[:200]
            if on_error:
                await on_error(f"片段 {index + 1} 翻译失败: {message}")
            return (
                f"\n\n> [片段 {index + 1} 翻译失败：上游服务超时/错误，请稍后重新翻译该论文]\n\n"
            )

_LANG_PROMPT = {
    "zh": "你是一位专业的学术论文翻译。把用户提供的论文片段完整翻译成中文，"
          "保留公式、代码块、引用标记（如 [1]）与段落结构，不要添加解释，只输出译文。",
    "en": "You are a professional academic translator. Translate the given paper "
          "fragment into English. Keep formulas, code blocks, citation markers and "
          "paragraph structure. Output only the translation.",
}

_translation_locks: Dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


def _lock_for(arxiv_id: str) -> asyncio.Lock:
    return _translation_locks.setdefault(arxiv_id, asyncio.Lock())


def translated_path(arxiv_id: str) -> Path:
    """Local markdown path of the translated paper."""
    return settings.papers_dir / f"{arxiv_id}.translated.md"


def has_translation(arxiv_id: str) -> bool:
    record = database.get_paper(arxiv_id)
    if record is None or record.get("status") != "downloaded":
        return False
    local = record.get("local_pdf_path")
    if local and not Path(local).exists():
        return False
    return translated_path(arxiv_id).exists()


def read_translation(arxiv_id: str) -> Optional[str]:
    path = translated_path(arxiv_id)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def delete_translation(arxiv_id: str) -> None:
    for path in (translated_path(arxiv_id), translated_pdf_path(arxiv_id)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # arxiv_id may contain characters that are invalid in a Windows path
            # (e.g. url-like ids from cnki/baidu) — nothing to delete then.
            pass


def extract_pdf_text(arxiv_id: str) -> str:
    record = database.get_paper(arxiv_id)
    if record is None:
        raise ValueError(f"Paper not found: {arxiv_id}")
    if record.get("status") != "downloaded":
        raise ValueError("该论文尚未下载，请先下载后再翻译")
    local = record.get("local_pdf_path")
    path = Path(local) if local else settings.papers_dir / f"{arxiv_id}.pdf"
    if not path.exists():
        raise ValueError("本地 PDF 文件不存在，请重新下载")
    doc = fitz.open(str(path))
    try:
        parts = [page.get_text("text") for page in doc]
    finally:
        doc.close()
    text = "\n\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ValueError("PDF 未提取到文本（可能是扫描件），无法翻译")
    return text


def _split_chunks(text: str) -> List[str]:
    """Split by paragraphs into chunks of about CHUNK_CHARS characters."""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for para in paragraphs:
        p = para.strip()
        if not p:
            continue
        buf.append(p)
        size += len(p)
        if size >= CHUNK_CHARS:
            chunks.append("\n\n".join(buf))
            buf, size = [], 0
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks[:MAX_CHUNKS]


async def _translate_chunk(chunk: str, language: str, index: int) -> str:
    from langchain_openai import ChatOpenAI

    cfg = get_effective_config()
    if not cfg.get("api_key"):
        raise ValueError("LLM_API_KEY 未配置")
    llm = ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.1,
        request_timeout=120.0,
    )
    resp = await llm.ainvoke([("system", _LANG_PROMPT.get(language, _LANG_PROMPT["zh"])), ("human", chunk)])
    content = resp.content
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content
        )
    title = f"## [片段 {index + 1}]\n\n" if index > 0 else ""
    return title + str(content).strip()


async def translate_paper(
    arxiv_id: str,
    language: str = "zh",
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:
    """Translate the downloaded paper preserving the original PDF layout.

    Produces ``{arxiv_id}.translated.pdf`` (layout-preserving overlay) and
    ``{arxiv_id}.translated.md`` (plain markdown for in-app preview).
    ``on_progress(percent, message)`` is awaited as work progresses.
    """
    async with _lock_for(arxiv_id):
        if has_translation(arxiv_id):
            if on_progress:
                await on_progress(100, "已有翻译")
            return {"path": str(translated_pdf_path(arxiv_id)), "cached": True}

        out_pdf = await translate_pdf_inplace(
            arxiv_id, language, on_progress=on_progress
        )

        # Also persist a markdown version for the in-app viewer.
        try:
            markdown = _build_markdown_from_pdf(arxiv_id, language)
            out_md = translated_path(arxiv_id)
            out_md.write_text(redact_secrets(markdown), encoding="utf-8")
        except Exception:
            pass  # markdown preview is best-effort; the PDF is the deliverable

        if on_progress:
            await on_progress(100, "翻译完成")
        return {"path": str(out_pdf), "cached": False}


def _build_markdown_from_pdf(arxiv_id: str, language: str) -> str:
    """Extract text from the translated PDF for the in-app preview."""
    import fitz

    doc = fitz.open(str(translated_pdf_path(arxiv_id)))
    try:
        parts = [page.get_text("text") for page in doc]
    finally:
        doc.close()
    return "# 论文翻译\n\n" + "\n\n".join(parts)


def translated_pdf_path(arxiv_id: str) -> Path:
    return settings.papers_dir / f"{arxiv_id}.translated.pdf"


def _markdown_to_pdf(markdown: str, out_path: Path) -> None:
    """Fallback simple renderer (kept for compatibility)."""
    try:
        import fitz
        from pymupdf import Story
    except ImportError:
        raise RuntimeError("服务器缺少 pymupdf，无法生成翻译 PDF")
    _esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = "<html><body><p>" + _esc(markdown[:5000]) + "</p></body></html>"
    story = Story(html=html, em=11)
    writer = fitz.DocumentWriter(str(out_path))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (48, 48, -48, -48)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()


async def translate_pdf_inplace(
    arxiv_id: str,
    language: str = "zh",
    on_progress: Optional[Any] = None,
    source_pdf: Optional[Path] = None,
    out_pdf: Optional[Path] = None,
) -> Path:
    """Translate the original PDF preserving its layout.

    For each page, text blocks are extracted (with bbox+font size), translated
    in batch, then drawn back over the original text (white-boxed) in the same
    positions. Images, tables (as drawings) and figures are kept untouched.
    """
    import fitz

    record = database.get_paper(arxiv_id) or {}
    src_path = Path(
        source_pdf
        or record.get("local_pdf_path")
        or settings.papers_dir / f"{arxiv_id}.pdf"
    )
    out = Path(out_pdf or translated_pdf_path(arxiv_id))
    out.parent.mkdir(parents=True, exist_ok=True)

    src_doc = fitz.open(str(src_path))
    # collect text blocks per page
    pages_blocks = []
    total_blocks = 0
    for page in src_doc:
        blocks = [
            b for b in page.get_text("blocks")
            if b[6] == 0 and b[4].strip()  # text blocks with content
        ]
        pages_blocks.append(blocks)
        total_blocks += len(blocks)

    if total_blocks == 0:
        raise ValueError("PDF 无可提取文本（可能是扫描件）")

    if on_progress:
        await on_progress(3, f"共 {len(src_doc)} 页 / {total_blocks} 个文本块，开始翻译")

    # gather all block texts and translate in chunked batches
    texts = [b[4].strip().replace("\n", "\n") for blocks in pages_blocks for b in blocks]
    # batch into LLM-sized groups (~3000 chars) to reduce request count
    batch_groups: List[List[int]] = []
    cur: List[int] = []
    cur_len = 0
    for idx, t in enumerate(texts):
        cur.append(idx)
        cur_len += len(t)
        if cur_len >= 2800:
            batch_groups.append(cur)
            cur, cur_len = [], 0
    if cur:
        batch_groups.append(cur)

    translations: Dict[int, str] = {}
    sem = asyncio.Semaphore(CONCURRENCY)
    done_batches = 0
    total_batches = len(batch_groups)

    async def translate_batch(group: List[int]) -> None:
        nonlocal done_batches
        async with sem:
            payload = "\n\n".join(
                f"[BLOCK {i}]\n{texts[i]}" for i in group
            )
            try:
                parts = await _translate_batch_blocks(payload, len(group), language)
                for local_i, translated in enumerate(parts):
                    translations[group[local_i]] = translated
            except Exception as exc:  # noqa: BLE001
                if on_progress:
                    await on_progress(
                        3 + int(done_batches * 90 / max(1, total_batches)),
                        f"一批翻译失败，使用占位（{redact_secrets(str(exc))[:80]}）",
                    )
                for i in group:
                    translations[i] = texts[i]  # fallback: keep original
            done_batches += 1
            if on_progress:
                await on_progress(
                    3 + int(done_batches * 90 / max(1, total_batches)),
                    f"已翻译 {done_batches}/{total_batches} 批",
                )

    await asyncio.gather(*(translate_batch(g) for g in batch_groups))

    if on_progress:
        await on_progress(96, "正在生成排版 PDF…")

    # overlay: copy source doc, white-out each block, draw translated text
    out_doc = fitz.open(str(src_path))
    white = (1, 1, 1)
    black = (0, 0, 0)
    for page_index, blocks in enumerate(pages_blocks):
        page = out_doc[page_index]
        for local_i, b in enumerate(blocks):
            global_i = sum(len(pb) for pb in pages_blocks[:page_index]) + local_i
            translated = translations.get(global_i)
            if not translated:
                continue
            rect = fitz.Rect(b[0], b[1], b[2], b[3])
            if rect.is_empty or rect.width < 8 or rect.height < 6:
                continue
            # white-out original text
            page.draw_rect(rect, color=None, fill=white, fill_opacity=1)
            # font size ~= original span size, shrink to fit translated length
            orig_chars = max(1, len(b[4]))
            new_chars = max(1, len(translated))
            base_size = 10.5
            d = page.get_text("dict", clip=rect)
            sizes = [
                s["size"]
                for blk in d.get("blocks", []) if blk.get("type") == 0
                for line in blk.get("lines", []) for s in line.get("spans", [])
            ]
            if sizes:
                base_size = max(6.0, min(sizes))
            fs = base_size * min(1.0, (orig_chars / new_chars) ** 0.5 * 1.15)
            fs = max(4.5, min(base_size, fs))
            # insert translated text into the same rect (expands downward if needed)
            try:
                page.insert_htmlbox(
                    rect,
                    f"<span style=\"font-size:{fs:.1f}px\">{translated}</span>",
                )
            except Exception:
                try:
                    page.insert_textbox(rect, translated, fontsize=fs, color=black)
                except Exception:
                    pass

    # Merge/dedupe the CJK fonts embedded by every insert_htmlbox call;
    # without this the output can balloon to hundreds of MB.
    try:
        out.subset_fonts()
    except Exception:
        pass
    out_doc.subset_fonts()
    out_doc.save(str(out), garbage=3, deflate=True)
    out_doc.close()
    src_doc.close()
    return out


async def _translate_batch_blocks(payload: str, count: int, language: str) -> List[str]:
    """Translate a batch of numbered blocks; returns exactly ``count`` strings."""
    from langchain_openai import ChatOpenAI

    cfg = get_effective_config()
    if not cfg.get("api_key"):
        raise ValueError("LLM_API_KEY 未配置")
    llm = ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=0.1,
        request_timeout=120.0,
    )
    system = (
        _LANG_PROMPT.get(language, _LANG_PROMPT["zh"])
        + " 输入包含多个以 [BLOCK n] 开头的文本块。"
        "请逐块翻译，按原顺序输出，每块译文前同样加 [BLOCK n] 标记，块间空一行。"
    )
    resp = await llm.ainvoke([("system", system), ("human", payload)])
    content = resp.content
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content
        )
    text = str(content).strip()
    # parse [BLOCK n] sections
    parts = re.split(r"\[BLOCK \d+\]", text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) < count:
        parts = parts + ["[翻译缺失]"] * (count - len(parts))
    return parts[:count]




def _markdown_to_pdf(markdown: str, out_path: Path) -> None:
    """Render markdown (headings/paragraphs/lists/bold) to a CJK-capable PDF
    using PyMuPDF's Story API. Multi-page automatically."""
    try:
        import fitz
        from pymupdf import Story
    except ImportError:
        raise RuntimeError("服务器缺少 pymupdf，无法生成翻译 PDF")

    def _esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body_parts: List[str] = []
    for block in markdown.split("\n\n"):
        b = block.strip()
        if not b:
            continue
        if b.startswith("### "):
            body_parts.append(f"<h3>{_esc(b[4:])}</h3>")
        elif b.startswith("## "):
            body_parts.append(f"<h2>{_esc(b[3:])}</h2>")
        elif b.startswith("# "):
            body_parts.append(f"<h1>{_esc(b[2:])}</h1>")
        elif b.startswith("- ") or b.startswith("* "):
            items = [li.strip() for li in b.split("\n") if li.strip().startswith(("- ", "* "))]
            lis = "".join(f"<li>{_esc(li.lstrip('-* '))}</li>" for li in items)
            body_parts.append(f"<ul>{lis}</ul>")
        else:
            # inline bold/italic
            b = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", b)
            b = re.sub(r"\*(.+?)\*", r"<i>\1</i>", b)
            body_parts.append(f"<p>{_esc(b)}</p>" if "<b>" not in b and "<i>" not in b else f"<p>{b}</p>")

    html = (
        "<html><head><style>"
        "h1{font-size:20px;text-align:center;}"
        "h2{font-size:16px;margin-top:14px;}"
        "h3{font-size:13px;}"
        "p{font-size:11px;line-height:1.6;text-align:justify;}"
        "li{font-size:11px;line-height:1.5;}"
        "body{font-family:sans-serif;}"
        "</style></head><body>" + "".join(body_parts) + "</body></html>"
    )

    story = Story(html=html, em=11)
    writer = fitz.DocumentWriter(str(out_path))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (48, 48, -48, -48)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
