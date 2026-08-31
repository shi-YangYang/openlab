"""spec-035 backend tests: download concurrency, startup recovery, pending
persistence, unified LLM JSON parsing, experiment run zombie recovery."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app import config, database, downloader
from app.agent import agent as agent_module
from app.agent import sessions
from app.app import app
from app.llm_json import parse_llm_json
from app.schemas import PaperMetadata


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, messages):
        return self.responses.pop(0)


# ---------------------------------------------------------------------------
# AC-1: batch download runs concurrently, failures recorded per paper
# ---------------------------------------------------------------------------


def _paper(arxiv_id):
    return {"arxiv_id": arxiv_id, "source": "arxiv", "pdf_url": "x", "url": ""}


async def test_download_job_runs_concurrently(client, monkeypatch):
    papers = [_paper(f"2601.0000{i}") for i in range(3)]
    for paper in papers:
        database.upsert_paper(paper)

    started = []

    async def fake_download_pdf(arxiv_id, pdf_url, http_client, on_progress=None):
        started.append(time.monotonic())
        if on_progress is not None:
            await on_progress(50)
        await asyncio.sleep(0.5)
        if on_progress is not None:
            await on_progress(100)
        return config.settings.papers_dir / f"{arxiv_id}.pdf"

    monkeypatch.setattr(
        downloader, "download_pdf", lambda *a, **k: fake_download_pdf(*a, **k)
    )

    start = time.monotonic()
    await downloader.run_download_job(papers)
    elapsed = time.monotonic() - start

    assert len(started) == 3
    # Serial execution would take >= 1.5s; concurrent must stay well below it.
    assert elapsed < 1.2
    for paper in papers:
        record = database.get_paper(paper["arxiv_id"])
        assert record["status"] == "downloaded"
        assert record["progress"] == 100


async def test_download_job_records_failure_per_paper(client, monkeypatch):
    ok_paper = _paper("2602.00001")
    bad_paper = _paper("2602.00002")
    database.upsert_paper(ok_paper)
    database.upsert_paper(bad_paper)
    monkeypatch.setattr(config.settings, "download_max_retries", 0)

    async def fake_download_pdf(arxiv_id, pdf_url, http_client, on_progress=None):
        if arxiv_id == bad_paper["arxiv_id"]:
            raise RuntimeError("boom")
        return config.settings.papers_dir / f"{arxiv_id}.pdf"

    monkeypatch.setattr(
        downloader, "download_pdf", lambda *a, **k: fake_download_pdf(*a, **k)
    )

    await downloader.run_download_job([ok_paper, bad_paper])

    ok = database.get_paper(ok_paper["arxiv_id"])
    assert ok["status"] == "downloaded"
    assert ok["progress"] == 100
    bad = database.get_paper(bad_paper["arxiv_id"])
    assert bad["status"] == "failed"
    assert bad["error"] == "下载失败"
    assert bad["progress"] == 0


def test_download_job_skips_already_downloaded(client, monkeypatch):
    paper = _paper("2602.00003")
    database.upsert_paper(paper)
    pdf = config.settings.papers_dir / f"{paper['arxiv_id']}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 fake")
    database.set_status(paper["arxiv_id"], "downloaded", str(pdf))

    calls = []

    async def fake_download_pdf(arxiv_id, pdf_url, http_client, on_progress=None):
        calls.append(arxiv_id)
        return pdf

    monkeypatch.setattr(
        downloader, "download_pdf", lambda *a, **k: fake_download_pdf(*a, **k)
    )

    asyncio.run(downloader.run_download_job([paper]))

    assert calls == []
    assert database.get_paper(paper["arxiv_id"])["status"] == "downloaded"


# ---------------------------------------------------------------------------
# AC-2: startup recovery resets residual downloading papers
# ---------------------------------------------------------------------------


def test_startup_resets_stale_downloading_papers(client):
    database.upsert_paper(_paper("2603.00001"))
    database.set_status("2603.00001", "downloading")
    database.set_download_progress("2603.00001", 42)

    with TestClient(app) as restarted:
        record = database.get_paper("2603.00001")
        assert record["status"] == "failed"
        assert record["error"] == "应用重启中断"
        assert restarted.get("/api/health").status_code == 200


# ---------------------------------------------------------------------------
# AC-3: pending approval survives a restart and clears after approve
# ---------------------------------------------------------------------------


def _pending_payload():
    return {
        "tool_calls": [
            {
                "id": "call_1",
                "name": "get_experiment_run_status",
                "args": {"run_id": 999},
            }
        ],
        "model": None,
        "reasoning_effort": None,
        "forbidden": False,
    }


def test_pending_persists_across_restart(client):
    session = sessions.create_session()
    sessions.set_pending(session, _pending_payload())

    # Simulate a restart: drop the in-process cache and replay lifespan.
    sessions._cache.clear()
    with TestClient(app):
        detail = client.get(f"/api/agent/sessions/{session.session_id}").json()
        assert detail["pending"] == {
            "tool": "get_experiment_run_status",
            "args": {"run_id": 999},
            "forbidden": False,
        }
        restored = sessions.get_session(session.session_id)
        assert restored.pending == _pending_payload()
        # Startup must NOT clear pending (FR-2: legitimate cross-restart state).
        assert database.get_agent_session(session.session_id)["pending"] is not None


async def test_pending_restored_from_db_and_cleared_on_approve(client, monkeypatch):
    session = sessions.create_session()
    sessions.set_pending(session, _pending_payload())
    # Prove the approve path works from persisted state, not the cache.
    sessions._cache.clear()

    monkeypatch.setattr(
        agent_module,
        "_build_bound_llm",
        lambda *a, **k: FakeLLM([AIMessage(content="已确认执行。")]),
    )
    result = await agent_module.run_approve(session.session_id, True)
    assert result["reply"] == "已确认执行。"
    assert result["pending_approval"] is None

    assert database.get_agent_session(session.session_id)["pending"] is None
    sessions._cache.clear()
    detail = client.get(f"/api/agent/sessions/{session.session_id}").json()
    assert detail["pending"] is None


def test_detail_pending_is_none_without_pending(client):
    session = sessions.create_session()
    detail = client.get(f"/api/agent/sessions/{session.session_id}").json()
    assert detail["pending"] is None


# ---------------------------------------------------------------------------
# AC-4: parse_llm_json matrix
# ---------------------------------------------------------------------------


def test_parse_llm_json_plain():
    assert parse_llm_json('{"a": 1}') == {"a": 1}
    assert parse_llm_json('[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]


def test_parse_llm_json_code_fences():
    assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_llm_json('```\n[1, 2]\n```') == [1, 2]


def test_parse_llm_json_noise_extraction():
    assert parse_llm_json('前缀 {"a": 1} 后缀') == {"a": 1}
    assert parse_llm_json('计划：[{"a": 1}] 完', container="array") == [{"a": 1}]


def test_parse_llm_json_array_wraps_bare_dict():
    assert parse_llm_json('{"a": 1}', container="array") == [{"a": 1}]


def test_parse_llm_json_model_validation():
    result = parse_llm_json(
        '```json\n{"title": "T", "authors": ["A"], "abstract": "", "published": ""}\n```',
        PaperMetadata,
        container="object",
    )
    assert result.title == "T"
    with pytest.raises(ValueError):
        parse_llm_json('{"title": 1}', PaperMetadata, container="object")


def test_parse_llm_json_invalid_raises_with_stage_info():
    with pytest.raises(ValueError, match="JSON"):
        parse_llm_json("完全不是 JSON 的文本")
    with pytest.raises(ValueError, match="JSON 对象"):
        parse_llm_json("[1, 2]", container="object")


def test_llm_parse_content_fallback_preserved():
    from app import llm as llm_utils

    assert llm_utils._parse_content('{"query": "  hello world  "}') == "hello world"
    assert llm_utils._parse_content("plain text query") == "plain text query"


def test_legacy_parsers_removed_and_replacements_in_place():
    from app import analysis, experiment, innovation, upload

    for module in (analysis, experiment, innovation, upload):
        assert not hasattr(module, "_parse_json")
        assert not hasattr(module, "_parse_json_array")
        assert not hasattr(module, "_strip_fences")


# ---------------------------------------------------------------------------
# AC-5: startup recovery resets stale running/paused experiment runs
# ---------------------------------------------------------------------------


def test_startup_resets_stale_experiment_runs(client):
    experiment_id = database.insert_experiment("papers", None, ["1"], None, "zh")
    running = database.create_experiment_run(experiment_id, "srv")
    paused = database.create_experiment_run(experiment_id, "srv")
    done = database.create_experiment_run(experiment_id, "srv")
    database.update_experiment_run(running["id"], status="running", current_step="sync_code")
    database.update_experiment_run(paused["id"], status="paused", error="步骤失败")
    database.update_experiment_run(done["id"], status="succeeded")

    with TestClient(app):
        running_after = database.get_experiment_run(running["id"])
        assert running_after["status"] == "interrupted"
        assert running_after["error"] == "应用重启，运行中断"

        paused_after = database.get_experiment_run(paused["id"])
        assert paused_after["status"] == "interrupted"
        assert paused_after["error"] == "应用重启，运行中断"

        done_after = database.get_experiment_run(done["id"])
        assert done_after["status"] == "succeeded"
        assert done_after["error"] == ""
