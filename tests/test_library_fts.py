"""spec-037: library FTS layer, sync points, routes and agent tool."""
import asyncio
import json

from app import config, database
from app.agent import tools as agent_tools
from tests.conftest import make_paper


def _setup_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    database.init_db()
    return data_dir


def _paper(arxiv_id, title="Title", abstract=None):
    paper = make_paper(arxiv_id, title=title)
    if abstract is not None:
        paper["abstract"] = abstract
    return paper


def _analysis_content(**overrides):
    content = {
        "summary": {
            "research_problem": "如何提升机器翻译质量",
            "method": "提出注意力机制",
            "contributions": ["多头注意力"],
            "conclusion": "效果显著",
        },
        "experiments": {"datasets": [], "baselines": [], "metrics": [], "key_results": ""},
        "limitations": "",
        "future_work": "",
        "keywords": ["图神经网络"],
        "tags": ["NLP"],
    }
    content.update(overrides)
    return content


def test_fts_available_by_default(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    assert database.fts_available() is True


def test_chinese_substring_and_english_case_insensitive(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(
        _paper("1", title="Attention Is All You Need", abstract="本文提出注意力机制用于机器翻译")
    )
    database.upsert_paper(_paper("2", title="Deep RL", abstract="reinforcement learning"))

    hits = database.search_paper_fts("注意力")
    assert [h["arxiv_id"] for h in hits] == ["1"]
    assert database.search_paper_fts("注意力机制")[0]["arxiv_id"] == "1"
    # English matching is case-insensitive (AC-1).
    assert {h["arxiv_id"] for h in database.search_paper_fts("ATTENTION")} == {"1"}
    assert {h["arxiv_id"] for h in database.search_paper_fts("attention")} == {"1"}
    # Unrelated term does not match.
    assert database.search_paper_fts("强化学习") == []
    # Multi-word AND semantics: only the paper containing both terms.
    assert [h["arxiv_id"] for h in database.search_paper_fts("attention 机器翻译")] == ["1"]


def test_analysis_content_becomes_searchable(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(_paper("3", abstract="占位摘要"))
    database.upsert_paper(_paper("4", abstract="另一篇"))
    # Before the analysis, keywords are not searchable.
    assert database.search_paper_fts("图神经网络") == []

    database.upsert_analysis("3", json.dumps(_analysis_content(), ensure_ascii=False), "zh")

    hits = database.search_paper_fts("图神经网络")
    assert [h["arxiv_id"] for h in hits] == ["3"]
    assert "analysis" in hits[0]["matched_in"]
    assert database.search_paper_fts("提出注意力")[0]["arxiv_id"] == "3"
    assert database.search_paper_fts("NLP")[0]["arxiv_id"] == "3"
    # A 2-char term cannot use trigram MATCH and falls back to LIKE.
    assert [h["arxiv_id"] for h in database.search_paper_fts("占位")] == ["3"]
    assert [h["arxiv_id"] for h in database.search_paper_fts("占位摘")] == ["3"]


def test_two_char_chinese_term_falls_back_to_like(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(_paper("11", title="锂离子电池", abstract="battery"))
    database.upsert_paper(_paper("12", title="Fuel Cell", abstract="燃料电池系统"))

    hits = database.search_paper_fts("电池")
    assert {h["arxiv_id"] for h in hits} == {"11", "12"}
    assert hits[0]["arxiv_id"] == "11" and "title" in hits[0]["matched_in"]
    assert hits[1]["arxiv_id"] == "12" and "abstract" in hits[1]["matched_in"]


def test_mixed_length_terms_use_like_and_semantics(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(_paper("13", title="电池", abstract="lithium anode"))
    database.upsert_paper(_paper("14", title="电极", abstract="battery design"))

    # Short + long term: the whole query runs as LIKE with AND semantics.
    assert [h["arxiv_id"] for h in database.search_paper_fts("电池 lithium")] == ["13"]
    # No paper contains every term -> empty, not partial matches.
    assert database.search_paper_fts("电池 anode design") == []


def test_delete_paper_removed_from_index(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(_paper("5", abstract="含注意力机制"))
    assert database.search_paper_fts("注意力")[0]["arxiv_id"] == "5"

    assert database.delete_paper("5") is True
    assert database.search_paper_fts("注意力") == []
    conn = database._connect()
    try:
        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM papers_fts WHERE paper_id = '5'"
        ).fetchone()
    finally:
        conn.close()
    assert rows["n"] == 0


def test_rebuild_idempotent(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(_paper("6", title="Transformer", abstract="注意力机制"))
    database.upsert_paper(_paper("7", title="BERT", abstract="预训练语言模型"))
    database.upsert_analysis("6", json.dumps(_analysis_content(), ensure_ascii=False), "zh")

    first = database.rebuild_paper_fts()
    second = database.rebuild_paper_fts()
    assert first == second == 2

    def snapshot():
        return sorted(
            [(h["arxiv_id"], h["title"]) for h in database.search_paper_fts("注意力", 50)]
            + [(h["arxiv_id"], h["title"]) for h in database.search_paper_fts("预训练", 50)]
        )

    assert snapshot() == [("6", "Transformer"), ("7", "BERT")]
    assert snapshot() == snapshot()


def test_startup_backfill_only_when_empty(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    # Simulate a pre-spec-037 database: papers exist but no sync hook ran,
    # so the FTS table is empty (inserted raw, bypassing upsert_paper).
    conn = database._connect()
    try:
        conn.execute(
            "INSERT INTO papers (arxiv_id, title, abstract, source)"
            " VALUES ('8', 'Legacy Paper', '注意力机制研究', 'arxiv')"
        )
        conn.commit()
    finally:
        conn.close()
    assert database.rebuild_paper_fts_if_empty() == 1
    # Second call: index no longer empty -> idempotent no-op.
    assert database.rebuild_paper_fts_if_empty() == 0
    assert database.search_paper_fts("注意力")[0]["arxiv_id"] == "8"


def test_search_route_400_rebuild_and_results(client):
    database.upsert_paper(_paper("9", title="Diffusion", abstract="扩散模型注意力机制"))

    # Empty q -> 400 (route branch).
    resp = client.get("/api/papers/search", params={"q": "   "})
    assert resp.status_code == 400

    rebuilt = client.post("/api/papers/search/rebuild")
    assert rebuilt.status_code == 200
    assert rebuilt.json() == {"rebuilt": 1}

    resp = client.get("/api/papers/search", params={"q": "注意力"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["arxiv_id"] == "9"
    assert "abstract" in data[0]["matched_in"]


def test_search_route_503_when_fts_unavailable(client, monkeypatch):
    monkeypatch.setattr(database, "fts_available", lambda: False)
    resp = client.get("/api/papers/search", params={"q": "anything"})
    assert resp.status_code == 503
    assert "FTS5" in resp.json()["detail"]
    rebuilt = client.post("/api/papers/search/rebuild")
    assert rebuilt.status_code == 503


def test_agent_tool_search_library(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    database.upsert_paper(_paper("10", title="GNN", abstract="图神经网络注意力机制"))

    result = asyncio.run(agent_tools.search_library("注意力", 5))
    assert result["count"] == 1
    hit = result["papers"][0]
    assert hit["arxiv_id"] == "10"
    assert hit["title"] == "GNN"
    assert hit["source"] == "arxiv"
    assert hit["has_analysis"] is False
    assert len(hit["abstract"]) <= 200

    database.upsert_analysis("10", json.dumps(_analysis_content(), ensure_ascii=False), "zh")
    result = asyncio.run(agent_tools.search_library("注意力"))
    assert result["papers"][0]["has_analysis"] is True

    empty = asyncio.run(agent_tools.search_library("   "))
    assert empty["count"] == 0 and empty["error"]

    unknown = asyncio.run(agent_tools.search_library("不存在的关键词xyz"))
    assert unknown == {"query": "不存在的关键词xyz", "count": 0, "papers": []}


def test_agent_tool_registered():
    assert "search_library" in agent_tools.TOOLS_BY_NAME
    assert not agent_tools.is_dangerous("search_library")
