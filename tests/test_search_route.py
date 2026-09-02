"""Route-level tests for per-platform max_results semantics (spec-036)."""

import pytest

from tests.conftest import make_paper


def _paper(source, idx, published="2024-05-01T17:59:59Z"):
    paper = make_paper(f"{source}-{idx}", published=published)
    paper["source"] = source
    return paper


@pytest.fixture()
def mock_aggregate(client, monkeypatch):
    captured = {}

    def _set(papers):
        async def fake_aggregate(query, platforms=None, max_results=10,
                                 arxiv_client=None, category=None):
            captured["query"] = query
            captured["platforms"] = platforms
            captured["max_results"] = max_results
            return {"papers": papers, "fallbacks": []}

        monkeypatch.setattr("app.routes.search.aggregate_search", fake_aggregate)
        return papers

    return _set


def test_keyword_keeps_max_results_per_platform(client, mock_aggregate):
    papers = []
    for source in ("arxiv", "semantic_scholar", "baidu_xueshu", "cnki"):
        papers.extend(_paper(source, i) for i in range(10))
    mock_aggregate(papers)

    resp = client.post("/api/search", json={
        "query": "attention", "max_results": 10,
        "platforms": ["arxiv", "semantic_scholar", "baidu_xueshu", "cnki"],
    })
    assert resp.status_code == 200
    returned = resp.json()["papers"]
    assert len(returned) == 40
    by_source = {}
    for p in returned:
        by_source.setdefault(p["source"], []).append(p)
    assert {s: len(v) for s, v in by_source.items()} == {
        "arxiv": 10,
        "semantic_scholar": 10,
        "baidu_xueshu": 10,
        "cnki": 10,
    }
    # Order preserved: platforms appear in first-occurrence order.
    sources_in_order = []
    for p in returned:
        if not sources_in_order or sources_in_order[-1] != p["source"]:
            sources_in_order.append(p["source"])
    assert sources_in_order == ["arxiv", "semantic_scholar", "baidu_xueshu", "cnki"]


def test_topic_keeps_max_results_per_platform(client, mock_aggregate, monkeypatch):
    async def fake_decompose(topic):
        return "decomposed query"

    monkeypatch.setattr("app.routes.search.decompose_topic", fake_decompose)
    papers = []
    for source in ("arxiv", "semantic_scholar", "baidu_xueshu", "cnki"):
        papers.extend(_paper(source, i) for i in range(10))
    mock_aggregate(papers)

    resp = client.post("/api/search/topic", json={
        "topic": "transformers", "max_results": 10,
        "platforms": ["arxiv", "semantic_scholar", "baidu_xueshu", "cnki"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "decomposed query"
    assert len(data["papers"]) == 40
    by_source = {}
    for p in data["papers"]:
        by_source.setdefault(p["source"], []).append(p)
    assert all(len(v) == 10 for v in by_source.values()) and len(by_source) == 4


def test_short_platform_does_not_affect_others(client, mock_aggregate):
    papers = [_paper("arxiv", i) for i in range(10)]
    papers.extend(_paper("cnki", i) for i in range(3))
    mock_aggregate(papers)

    resp = client.post("/api/search", json={
        "query": "x", "max_results": 10, "platforms": ["arxiv", "cnki"],
    })
    assert resp.status_code == 200
    returned = resp.json()["papers"]
    assert len(returned) == 13
    counts = {}
    for p in returned:
        counts[p["source"]] = counts.get(p["source"], 0) + 1
    assert counts == {"arxiv": 10, "cnki": 3}


def test_per_platform_limit_applies_after_date_filter(client, mock_aggregate):
    papers = []
    for i in range(12):
        published = "2024-05-01T00:00:00Z" if i < 11 else "2020-01-01T00:00:00Z"
        papers.append(_paper("arxiv", i, published=published))
    papers.extend(_paper("cnki", i) for i in range(2))
    mock_aggregate(papers)

    resp = client.post("/api/search", json={
        "query": "x", "max_results": 10, "platforms": ["arxiv", "cnki"],
        "date_from": "2024-01-01", "date_to": "2024-12-31",
    })
    assert resp.status_code == 200
    returned = resp.json()["papers"]
    # arxiv: 11 in range -> truncated to 10; cnki: 2 kept (below limit).
    counts = {}
    for p in returned:
        counts[p["source"]] = counts.get(p["source"], 0) + 1
    assert counts == {"arxiv": 10, "cnki": 2}
    assert all(p["published"] >= "2024-01-01" for p in returned)


def test_history_stores_full_multi_platform_papers(client, mock_aggregate):
    papers = []
    for source in ("arxiv", "cnki"):
        papers.extend(_paper(source, i) for i in range(10))
    mock_aggregate(papers)

    resp = client.post("/api/search", json={
        "query": "q", "max_results": 10, "platforms": ["arxiv", "cnki"],
    })
    assert resp.status_code == 200

    history = client.get("/api/search/history").json()
    assert history and history[0]["paper_count"] == 20
    detail = client.get(f"/api/search/history/{history[0]['id']}").json()
    assert len(detail["papers"]) == 20
    sources = {p["source"] for p in detail["papers"]}
    assert sources == {"arxiv", "cnki"}
