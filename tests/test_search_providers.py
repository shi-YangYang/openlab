"""Tests for multi-platform search providers and aggregation."""
import httpx
import pytest

from app.platforms import LoginExpiredError, LoginRequiredError
from app.search import aggregator
from app.search import _html
from app.search.arxiv import ArxivSearchProvider
from app.search.baidu_xueshu import BaiduXueshuProvider
from app.search.cnki import CnkiProvider
from app.search.semantic_scholar import SemanticScholarProvider


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self._json


class FakeAsyncClient:
    def __init__(self, response=None, exc=None, text=""):
        self._response = response
        self._exc = exc
        self._text = text
        self.url = None
        self.params = None
        self.headers = None

    async def get(self, url, params=None, headers=None):
        self.url = url
        self.params = params
        self.headers = headers
        if self._exc is not None:
            raise self._exc
        if self._response is not None:
            return self._response
        resp = FakeResponse({})
        resp.text = self._text
        return resp

    async def aclose(self):
        pass


def test_build_providers_all_and_filtered():
    all_providers = aggregator.build_providers()
    assert [p.name for p in all_providers] == list(aggregator.ALL_PLATFORMS)

    some = aggregator.build_providers(["arxiv", "cnki"])
    assert [p.name for p in some] == ["arxiv", "cnki"]

    unknown = aggregator.build_providers(["nope"])
    assert unknown == []


async def test_arxiv_provider_normalizes():
    class FakeArxiv:
        async def search(self, query, max_results=10, category=None):
            return [
                {
                    "arxiv_id": "1706.03762",
                    "title": "Attention",
                    "authors": ["A", "B"],
                    "abstract": "Abs",
                    "categories": ["cs.CL"],
                    "published": "2017-06-12T00:00:00Z",
                    "pdf_url": "https://arxiv.org/pdf/1706.03762",
                }
            ]

    provider = ArxivSearchProvider(client=FakeArxiv())
    papers = await provider.search("attention")

    assert papers[0]["source"] == "arxiv"
    assert papers[0]["url"] == "https://arxiv.org/abs/1706.03762"
    assert papers[0]["categories"] == ["cs.CL"]


async def test_semantic_scholar_normalizes():
    response = FakeResponse(
        {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Attention Is All You Need",
                    "authors": [{"name": "Ashish"}, {"name": "Noam"}],
                    "abstract": "The dominant sequence transduction models...",
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "externalIds": {"ArXiv": "1706.03762"},
                    "publicationDate": "2017-06-12",
                    "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762"},
                }
            ]
        }
    )
    provider = SemanticScholarProvider(client=FakeAsyncClient(response=response))
    papers = await provider.search("attention")

    assert papers[0]["source"] == "semantic_scholar"
    assert papers[0]["arxiv_id"] == "1706.03762"
    assert papers[0]["authors"] == ["Ashish", "Noam"]
    assert papers[0]["abstract"].startswith("The dominant")
    assert papers[0]["published"] == "2017-06-12"


async def test_aggregator_merges_and_falls_back(monkeypatch):
    class OkProvider:
        name = "arxiv"

        async def search(self, query, max_results=10):
            return [{"arxiv_id": "1", "source": "arxiv", "title": "One"}]

        def fallback_url(self, query):
            return "https://arxiv.org/search/?query=x"

    class FailProvider:
        name = "baidu_xueshu"

        async def search(self, query, max_results=10):
            raise RuntimeError("timeout")

        def fallback_url(self, query):
            return "https://xueshu.baidu.com/s?wd=x"

    monkeypatch.setattr(
        aggregator,
        "build_providers",
        lambda platforms=None, arxiv_client=None, category=None: [OkProvider(), FailProvider()],
    )

    result = await aggregator.search("x", platforms=["arxiv", "baidu_xueshu"], max_results=10)

    assert len(result["papers"]) == 1
    assert result["papers"][0]["arxiv_id"] == "1"
    assert result["fallbacks"] == [
        {
            "platform": "baidu_xueshu",
            "url": "https://xueshu.baidu.com/s?wd=x",
            "need_login": False,
            "expired": False,
        }
    ]


async def test_baidu_provider_requires_login_without_state(monkeypatch):
    monkeypatch.setattr("app.search.baidu_xueshu.has_state", lambda platform: False)
    provider = BaiduXueshuProvider()
    with pytest.raises(LoginRequiredError):
        await provider.search("x")

    assert provider.fallback_url("x").startswith("https://xueshu.baidu.com/s?wd=")


def test_baidu_provider_parses_links():
    html = (
        '<h3 data-v="" class="paper-title">'
        '<a href="https://xueshu.baidu.com/usercenter/paper/show?paperid=1&amp;site=xueshu_se">Paper One</a>'
        '</h3>'
        '<div data-v="" class="paper-abstract">Abstract one</div>'
        '<div data-v="" class="paper-info">'
        '<a href="https://xueshu.baidu.com/ndscholar/browse/search?wd=author%3A%28Alice%29"><span>Alice</span><span>，</span></a>'
        '<a href="https://xueshu.baidu.com/ndscholar/browse/search?wd=author%3A%28Bob%29"><span>Bob</span></a>'
        '&nbsp;-&nbsp;2021年'
        '</div>'
        '<div data-v="" class="paper-source">source</div>'
        '<h3 data-v="" class="paper-title">'
        '<a href="https://xueshu.baidu.com/usercenter/paper/show?paperid=2&amp;site=xueshu_se">Paper Two</a>'
        '</h3>'
        '<div data-v="" class="paper-abstract">Abstract two</div>'
        '<div data-v="" class="paper-info">2020年</div>'
        '<div data-v="" class="paper-source">source</div>'
    )
    provider = BaiduXueshuProvider()
    papers = provider._parse(html, 10)

    assert [p["title"] for p in papers] == ["Paper One", "Paper Two"]
    assert papers[0]["source"] == "baidu_xueshu"
    assert papers[0]["authors"] == ["Alice", "Bob"]
    assert papers[0]["published"] == "2021"
    assert papers[0]["abstract"] == "Abstract one"
    assert papers[0]["url"] == (
        "https://xueshu.baidu.com/usercenter/paper/show?paperid=1&site=xueshu_se"
    )
    assert papers[0]["arxiv_id"].startswith("baidu-")


def test_cnki_provider_fallback_url():
    provider = CnkiProvider()
    url = provider.fallback_url("深度学习")
    assert "kns.cnki.net" in url
    assert "%E6%B7%B1%E5%BA%A6%E5%AD%A6%E4%B9%A0" in url


async def test_semantic_scholar_sends_user_agent():
    client = FakeAsyncClient(response=FakeResponse({"data": []}))
    provider = SemanticScholarProvider(client=client)
    await provider.search("attention")

    assert client.headers is not None
    assert "Mozilla" in client.headers["User-Agent"]
    assert client.headers["Accept"] == "application/json"


async def test_baidu_provider_searches_with_login_state(monkeypatch):
    monkeypatch.setattr("app.search.baidu_xueshu.has_state", lambda platform: True)
    monkeypatch.setattr(
        "app.platforms.browser.fetch_search_html",
        lambda platform, query: (
            '<h3 data-v="" class="paper-title">'
            '<a href="https://xueshu.baidu.com/usercenter/paper/show?paperid=1&amp;site=xueshu_se">Paper One</a>'
            '</h3>'
            '<div data-v="" class="paper-abstract">Abs</div>'
            '<div data-v="" class="paper-info">2021年</div>'
            '<div data-v="" class="paper-source">src</div>'
        ),
    )
    provider = BaiduXueshuProvider()
    papers = await provider.search("x")

    assert [p["title"] for p in papers] == ["Paper One"]


async def test_cnki_provider_searches_with_login_state(monkeypatch):
    monkeypatch.setattr("app.search.cnki.has_state", lambda platform: True)
    monkeypatch.setattr(
        "app.platforms.browser.fetch_search_html",
        lambda platform, query: (
            '<tr>'
            '<td class="name"><a href="https://kns.cnki.net/kcms2/article/abstract?v=abc">Paper One</a></td>'
            "</tr>"
            "<tr>"
            '<td class="author"><a href="/author">张 三</a><a href="/author">李 四</a></td>'
            '<td class="date">2024-01-15</td>'
            "</tr>"
        ),
    )
    provider = CnkiProvider()
    papers = await provider.search("x")

    assert [p["title"] for p in papers] == ["Paper One"]
    assert papers[0]["authors"] == ["张 三", "李 四"]
    assert papers[0]["published"] == "2024-01-15"


def test_extract_links_filters_navigation_noise():
    html = (
        '<html><body>'
        '<a href="https://xueshu.baidu.com/">首页</a>'
        '<a href="https://xueshu.baidu.com/login">登录</a>'
        '<a href="javascript:void(0)">更多</a>'
        '<div class="result"><a href="https://xueshu.baidu.com/a">Paper One</a></div>'
        '<a href="https://xueshu.baidu.com/b">Paper Two</a>'
        "</body></html>"
    )
    links = _html.extract_links(html)

    titles = [t for t, _ in links]
    assert "Paper One" in titles
    assert "Paper Two" in titles
    assert "首页" not in titles
    assert "登录" not in titles
    assert "更多" not in titles
    assert links[0][0] == "Paper One"


def test_extract_links_prefers_result_containers():
    html = (
        '<div class="sc_content"><a href="https://xueshu.baidu.com/r">Result Title</a></div>'
        '<a href="https://xueshu.baidu.com/nav">Footer Nav Link</a>'
    )
    links = _html.extract_links(html)

    assert links[0] == ("Result Title", "https://xueshu.baidu.com/r")


async def test_provider_raises_expired_on_verification(monkeypatch):
    def _expired(platform, query):
        raise LoginExpiredError(platform)

    monkeypatch.setattr("app.search.cnki.has_state", lambda platform: True)
    monkeypatch.setattr("app.platforms.browser.fetch_search_html", _expired)
    provider = CnkiProvider()
    with pytest.raises(LoginExpiredError):
        await provider.search("x")
