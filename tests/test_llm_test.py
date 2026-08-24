import httpx


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        if self._data is None:
            raise ValueError("no JSON body")
        return self._data


class FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.url = None
        self.payload = None
        self.headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        self.url = url
        self.payload = json
        self.headers = headers
        return self._response


class RaisingAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        raise httpx.ConnectError("connection refused")


def test_llm_test_empty_config_returns_false(client):
    resp = client.post("/api/llm/test", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "完整配置" in data["message"]


def test_llm_test_partial_config_returns_false(client):
    resp = client.post(
        "/api/llm/test",
        json={"base_url": "https://example.com/v1", "model": "m"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "完整配置" in data["message"]


def test_llm_test_success(client, monkeypatch):
    captured = {}

    def make_client(**kwargs):
        captured.update(kwargs)
        return FakeAsyncClient(
            FakeResponse(status_code=200, data={"choices": [{"message": {"content": "pong"}}]})
        )

    monkeypatch.setattr("app.main.httpx.AsyncClient", make_client)

    resp = client.post(
        "/api/llm/test",
        json={
            "base_url": "https://example.com/v1/",
            "api_key": "sk-123",
            "model": "my-model",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["message"] == "pong"
    assert data["latency_ms"] is not None and data["latency_ms"] >= 0

    assert captured["timeout"] == 15.0


def test_llm_test_http_error_returns_false_and_redacts_key(client, monkeypatch):
    fake_client = FakeAsyncClient(
        FakeResponse(status_code=401, data={"error": {"message": "Invalid API key"}})
    )
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: fake_client)

    resp = client.post(
        "/api/llm/test",
        json={
            "base_url": "https://example.com/v1",
            "api_key": "sk-secret-123",
            "model": "my-model",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "401" in data["message"]
    assert "sk-secret-123" not in data["message"]


def test_llm_test_network_error_returns_false(client, monkeypatch):
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: RaisingAsyncClient())

    resp = client.post(
        "/api/llm/test",
        json={
            "base_url": "https://example.com/v1",
            "api_key": "sk-secret-123",
            "model": "my-model",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["message"]
    assert "sk-secret-123" not in data["message"]


def test_llm_test_does_not_print_api_key(client, monkeypatch, capsys):
    fake_client = FakeAsyncClient(
        FakeResponse(status_code=401, data={"error": {"message": "Invalid API key"}})
    )
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: fake_client)

    client.post(
        "/api/llm/test",
        json={
            "base_url": "https://example.com/v1",
            "api_key": "sk-super-secret-999",
            "model": "my-model",
        },
    )
    captured = capsys.readouterr()
    assert "sk-super-secret-999" not in captured.out
    assert "sk-super-secret-999" not in captured.err
