"""Tests for platform login-state management (spec-014)."""
import time

import pytest

from app.platforms import LoginExpiredError, LoginRequiredError, sessions
from app.platforms.browser import is_verification_page


@pytest.fixture(autouse=True)
def _reset_platform_states():
    sessions.reset_states()
    yield
    sessions.reset_states()


def test_sessions_save_load_has_delete(client):
    sessions.save_state("cnki", {"cookies": [{"name": "token", "value": "x"}]})
    assert sessions.has_state("cnki")
    assert sessions.load_state("cnki") == {"cookies": [{"name": "token", "value": "x"}]}
    assert not sessions.has_state("baidu_xueshu")

    sessions.delete_state("cnki")
    assert not sessions.has_state("cnki")
    assert sessions.load_state("cnki") is None


def test_sessions_state_transitions(client):
    assert sessions.get_state("cnki") == "not_logged_in"
    sessions.set_state("cnki", "logging_in")
    assert sessions.get_state("cnki") == "logging_in"
    sessions.set_state("cnki", "logged_in")
    assert sessions.get_state("cnki") == "logged_in"
    sessions.set_state("cnki", "expired")
    assert sessions.get_state("cnki") == "expired"


def test_get_state_derives_logged_in_from_file(client):
    sessions.save_state("baidu_xueshu", {"cookies": []})
    assert sessions.get_state("baidu_xueshu") == "logged_in"


def test_is_verification_page():
    assert is_verification_page("https://xueshu.baidu.com/s?wd=x", "百度安全验证")
    assert is_verification_page("https://xueshu.baidu.com/verify/", "搜索结果")
    assert not is_verification_page("https://xueshu.baidu.com/s?wd=x", "搜索结果")
    assert not is_verification_page("https://kns.cnki.net/kns8s/defaultresult/index?kw=x", "知网检索")


def test_list_platforms_endpoint(client):
    resp = client.get("/api/platforms")
    assert resp.status_code == 200
    data = resp.json()
    assert {p["platform"] for p in data} == {"cnki", "baidu_xueshu"}
    assert all(p["state"] == "not_logged_in" for p in data)


def test_unknown_platform_returns_404(client):
    assert client.get("/api/platforms/nope/status").status_code == 404
    assert client.post("/api/platforms/nope/login").status_code == 404
    assert client.post("/api/platforms/nope/logout").status_code == 404


def test_login_endpoint_marks_logging_in_then_logged_in(client, monkeypatch):
    def fake_run_login(platform):
        sessions.save_state(platform, {"cookies": [], "origins": []})
        sessions.set_state(platform, "logged_in")

    monkeypatch.setattr("app.main.browser.run_login", fake_run_login)

    resp = client.post("/api/platforms/cnki/login")
    assert resp.status_code == 200
    assert resp.json()["state"] == "logging_in"

    deadline = time.time() + 2
    state = "logging_in"
    while time.time() < deadline:
        state = client.get("/api/platforms/cnki/status").json()["state"]
        if state == "logged_in":
            break
        time.sleep(0.02)
    assert state == "logged_in"
    assert sessions.has_state("cnki")


def test_login_while_logging_in_is_idempotent(client, monkeypatch):
    sessions.set_state("cnki", "logging_in")
    calls = []

    def fake_run_login(platform):
        calls.append(platform)

    monkeypatch.setattr("app.main.browser.run_login", fake_run_login)
    resp = client.post("/api/platforms/cnki/login")
    assert resp.json()["state"] == "logging_in"
    time.sleep(0.05)
    assert calls == []


def test_logout_deletes_state(client):
    sessions.save_state("cnki", {"cookies": []})
    sessions.set_state("cnki", "logged_in")

    resp = client.post("/api/platforms/cnki/logout")
    assert resp.status_code == 200
    assert resp.json()["state"] == "not_logged_in"
    assert not sessions.has_state("cnki")


async def test_aggregator_marks_need_login_and_expired(monkeypatch):
    from app.search import aggregator

    class NeedLoginProvider:
        name = "cnki"

        async def search(self, query, max_results=10):
            raise LoginRequiredError("cnki")

        def fallback_url(self, query):
            return "https://kns.cnki.net/"

    class ExpiredProvider:
        name = "baidu_xueshu"

        async def search(self, query, max_results=10):
            raise LoginExpiredError("baidu_xueshu")

        def fallback_url(self, query):
            return "https://xueshu.baidu.com/"

    monkeypatch.setattr(
        aggregator,
        "build_providers",
        lambda platforms=None, arxiv_client=None, category=None: [
            NeedLoginProvider(),
            ExpiredProvider(),
        ],
    )

    result = await aggregator.search("x", platforms=["cnki", "baidu_xueshu"], max_results=10)
    by_platform = {f["platform"]: f for f in result["fallbacks"]}

    assert by_platform["cnki"]["need_login"] is True
    assert by_platform["cnki"]["expired"] is False
    assert by_platform["baidu_xueshu"]["need_login"] is False
    assert by_platform["baidu_xueshu"]["expired"] is True
