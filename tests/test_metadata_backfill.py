"""spec-039: metadata backfill (AC-1/AC-2) and duplicate tool-call guard (AC-3)."""
import asyncio

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app import config, database
from app.agent import agent as agent_module
from app.agent import permissions as agent_permissions
from app.agent import sessions
from app.metadata_backfill import backfill_metadata
from tests.conftest import make_paper


@pytest.fixture(autouse=True)
def _setup_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    monkeypatch.setenv(
        "AGENT_PERMISSIONS_PATH", str(data_dir / "agent_permissions.json")
    )
    agent_permissions.save("conservative", [])
    database.init_db()
    sessions.clear_sessions()
    yield
    sessions.clear_sessions()


class FakeBackfillArxiv:
    """fetch_by_ids-only fake: results keyed by arxiv_id, missing id -> [] ."""

    def __init__(self, results=None, error_ids=None):
        self.results = results or {}
        self.error_ids = set(error_ids or ())
        self.calls = []

    async def fetch_by_ids(self, ids):
        self.calls.append(list(ids))
        arxiv_id = ids[0]
        if arxiv_id in self.error_ids:
            raise RuntimeError("arxiv unreachable")
        if arxiv_id not in self.results:
            return []
        return [dict(self.results[arxiv_id])]

    async def aclose(self):
        return None


def _missing_paper(arxiv_id, source="arxiv"):
    paper = make_paper(arxiv_id, published="")
    paper["authors"] = []
    paper["categories"] = []
    paper["source"] = source
    return paper


# ----------------------------- AC-1: backfill -------------------------------


def test_backfill_updates_missing_metadata_and_keeps_local_fields(
    tmp_path, monkeypatch
):
    fts_calls = []
    real_update_fts = database.update_paper_fts

    def fts_spy(arxiv_id):
        fts_calls.append(arxiv_id)
        return real_update_fts(arxiv_id)

    monkeypatch.setattr("app.db.papers.update_paper_fts", fts_spy)

    database.upsert_paper(_missing_paper("1"))
    database.set_status("1", "downloaded", str(tmp_path / "1.pdf"))
    database.upsert_paper(_missing_paper("2", source="baidu"))
    database.upsert_paper(_missing_paper("3"))
    database.upsert_paper(_missing_paper("4"))

    fts_calls.clear()  # only count the syncs fired by backfill itself
    fake = FakeBackfillArxiv(
        results={
            "1": make_paper("1"),
            # "3": hit but identical metadata -> unchanged.
            "3": {
                "arxiv_id": "3",
                "title": "Title",
                "authors": [],
                "abstract": "Abstract of 3",
                "categories": [],
                "published": "",
                "pdf_url": "https://arxiv.org/pdf/3",
            },
        },
        error_ids={"4"},
    )
    counts = asyncio.run(backfill_metadata(20, client=fake))

    assert counts == {
        "updated": 1,
        "skipped_non_arxiv": 1,
        "unchanged": 1,
        "failed": 1,
    }
    assert fake.calls == [["1"], ["3"], ["4"]]

    updated = database.get_paper("1")
    assert updated["authors"] == ["Alice", "Bob"]
    assert updated["published"] == "2024-05-01T17:59:59Z"
    assert updated["categories"] == ["cs.AI"]
    # Local download state is never touched (NFR-2).
    assert updated["status"] == "downloaded"
    assert updated["local_pdf_path"] == str(tmp_path / "1.pdf")
    assert updated["progress"] == 0
    # FTS sync fired for the real update only.
    assert fts_calls == ["1"]


def test_backfill_zero_counts_when_nothing_missing(tmp_path):
    database.upsert_paper(make_paper("1"))
    fake = FakeBackfillArxiv()
    counts = asyncio.run(backfill_metadata(20, client=fake))
    assert counts == {
        "updated": 0,
        "skipped_non_arxiv": 0,
        "unchanged": 0,
        "failed": 0,
    }
    assert fake.calls == []


# ----------------------------- AC-2: route ----------------------------------


def test_backfill_route_returns_counts_and_refreshes_library(client, monkeypatch):
    database.upsert_paper(_missing_paper("1"))
    fake = FakeBackfillArxiv(results={"1": make_paper("1")})
    monkeypatch.setattr(client.app.state, "arxiv_client", fake)

    resp = client.post("/api/papers/metadata/backfill")
    assert resp.status_code == 200
    assert resp.json() == {
        "updated": 1,
        "skipped_non_arxiv": 0,
        "unchanged": 0,
        "failed": 0,
    }

    papers = client.get("/api/papers").json()
    row = next(p for p in papers if p["arxiv_id"] == "1")
    assert row["authors"] == ["Alice", "Bob"]
    assert row["published"] == "2024-05-01T17:59:59Z"


# ------------------------- AC-3: duplicate guard ----------------------------


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    async def astream(self, messages):
        response = self.responses.pop(0)
        yield AIMessageChunk(
            content=response.content,
            tool_calls=list(getattr(response, "tool_calls", []) or []),
            usage_metadata=getattr(response, "usage_metadata", None),
        )


def _tool_call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


async def test_duplicate_non_dangerous_call_skipped(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"count": 2, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("search_papers", {"query": "attention"}, "c1"),
        _tool_call("search_papers", {"query": "attention"}, "c2"),
        AIMessage(content="完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    result = await agent_module.run_chat(None, "搜索 attention")

    assert executed == [("search_papers", {"query": "attention"})]
    assert [e["status"] for e in result["tool_calls"]] == ["done", "skipped"]
    session = sessions.get_session(result["session_id"])
    skipped = [
        m.content
        for m in session.messages
        if isinstance(m, ToolMessage) and "重复调用已跳过" in m.content
    ]
    assert len(skipped) == 1
    assert "count" in skipped[0]  # previous result replayed


async def test_same_tool_different_args_executes(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"count": 1, "papers": []}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("search_papers", {"query": "attention"}, "c1"),
        _tool_call("search_papers", {"query": "transformer"}, "c2"),
        AIMessage(content="完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    result = await agent_module.run_chat(None, "搜索")

    assert len(executed) == 2
    assert [e["status"] for e in result["tool_calls"]] == ["done", "done"]


async def test_dangerous_tool_not_deduped(monkeypatch):
    executed = []

    async def fake_execute(name, args):
        executed.append((name, args))
        return {"output": "ok"}

    monkeypatch.setattr("app.agent.tools.execute_tool", fake_execute)
    llm = FakeLLM([
        _tool_call("run_command", {"server_id": "s1", "command": "ls"}, "c1"),
        _tool_call("run_command", {"server_id": "s1", "command": "ls"}, "c2"),
        AIMessage(content="完成。"),
    ])
    monkeypatch.setattr(agent_module, "_build_bound_llm", lambda *a, **k: llm)

    first = await agent_module.run_chat(None, "运行 ls")
    assert first["pending_approval"] is not None

    second = await agent_module.run_approve(first["session_id"], True)
    # Same name + same args as the first call, yet it goes through approval
    # again instead of being deduped.
    assert second["pending_approval"]["tool"] == "run_command"

    third = await agent_module.run_approve(first["session_id"], True)
    assert third["reply"] == "完成。"
    assert executed == [
        ("run_command", {"server_id": "s1", "command": "ls"}),
        ("run_command", {"server_id": "s1", "command": "ls"}),
    ]
