"""Tests for local PDF upload: LLM metadata extraction and upload/confirm flow."""
import pytest

from app import upload
from tests.conftest import make_paper


def _make_pdf_bytes(text: str = "Hello openlab research paper") -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


async def test_extract_metadata_uses_llm(monkeypatch):
    class FakeMessage:
        content = (
            '{"title": "My Paper", "authors": ["Alice", "Bob"], '
            '"abstract": "An abstract", "published": "2024-05-01"}'
        )

    class FakeChat:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def ainvoke(self, messages):
            self.messages = messages
            return FakeMessage()

    created = {}

    def fake_chat(**kwargs):
        created["kwargs"] = kwargs
        return FakeChat(**kwargs)

    monkeypatch.setattr(upload, "ChatOpenAI", fake_chat)
    monkeypatch.setattr(upload, "get_effective_config", lambda: {
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test",
        "model": "my-model",
    })

    meta = await upload.extract_metadata("the full paper text")

    assert meta == {
        "title": "My Paper",
        "authors": ["Alice", "Bob"],
        "abstract": "An abstract",
        "published": "2024-05-01",
    }
    assert created["kwargs"]["api_key"] == "sk-test"


async def test_extract_metadata_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(upload, "get_effective_config", lambda: {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
    })
    with pytest.raises(ValueError):
        await upload.extract_metadata("text")


def test_upload_rejects_non_pdf(client):
    resp = client.post(
        "/api/papers/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_confirm_rejects_invalid_token(client):
    resp = client.post(
        "/api/papers/upload/confirm",
        json={
            "pdf_token": "../etc/passwd",
            "paper": {"title": "x", "authors": [], "abstract": "", "published": ""},
        },
    )
    assert resp.status_code == 400


def test_confirm_missing_upload(client):
    resp = client.post(
        "/api/papers/upload/confirm",
        json={
            "pdf_token": "a" * 32,
            "paper": {"title": "x", "authors": [], "abstract": "", "published": ""},
        },
    )
    assert resp.status_code == 404


def test_upload_and_confirm_flow(client, monkeypatch):
    async def fake_extract(text):
        return {
            "title": "Extracted Title",
            "authors": ["Alice"],
            "abstract": "Extracted abstract",
            "published": "2024-05-01",
        }

    monkeypatch.setattr("app.upload.extract_metadata", fake_extract)

    pdf_bytes = _make_pdf_bytes("A paper about research agents")
    resp = client.post(
        "/api/papers/upload",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    token = data["pdf_token"]
    assert token
    assert data["paper"]["title"] == "Extracted Title"

    confirm = client.post(
        "/api/papers/upload/confirm",
        json={
            "pdf_token": token,
            "paper": {
                "title": "Edited Title",
                "authors": ["Bob", "Carol"],
                "abstract": "Edited abstract",
                "published": "2023",
            },
        },
    )
    assert confirm.status_code == 200
    rec = confirm.json()
    assert rec["source"] == "upload"
    assert rec["status"] == "downloaded"
    assert rec["arxiv_id"] == "upload-sample"
    assert rec["title"] == "Edited Title"
    assert rec["authors"] == ["Bob", "Carol"]

    records = client.get("/api/papers").json()
    assert any(r["arxiv_id"] == rec["arxiv_id"] for r in records)


def _upload_and_confirm(client, monkeypatch, filename, title="T"):
    async def fake_extract(text):
        return {"title": title, "authors": [], "abstract": "", "published": ""}

    monkeypatch.setattr("app.upload.extract_metadata", fake_extract)
    pdf_bytes = _make_pdf_bytes("paper text")
    resp = client.post(
        "/api/papers/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    token = resp.json()["pdf_token"]
    confirm = client.post(
        "/api/papers/upload/confirm",
        json={
            "pdf_token": token,
            "paper": {"title": title, "authors": [], "abstract": "", "published": ""},
        },
    )
    assert confirm.status_code == 200
    return confirm.json()


def test_confirm_uses_cleaned_filename(client, monkeypatch):
    rec = _upload_and_confirm(client, monkeypatch, "Attention Paper.pdf")
    assert rec["arxiv_id"] == "upload-attention-paper"


def test_confirm_falls_back_to_uuid_when_name_empty(client, monkeypatch):
    rec = _upload_and_confirm(client, monkeypatch, "!!.pdf")
    assert rec["arxiv_id"].startswith("upload-")
    assert len(rec["arxiv_id"]) == len("upload-") + 8


def test_confirm_deduplicates_same_filename(client, monkeypatch):
    first = _upload_and_confirm(client, monkeypatch, "Attention Paper.pdf")
    second = _upload_and_confirm(client, monkeypatch, "Attention Paper.pdf")
    assert first["arxiv_id"] == "upload-attention-paper"
    assert second["arxiv_id"] == "upload-attention-paper-1"
