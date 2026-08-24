import json

from app import config, database, llm_config


def _set_config_path(tmp_path, monkeypatch):
    path = tmp_path / "llm_config.json"
    monkeypatch.setenv("LLM_CONFIG_PATH", str(path))
    return path


def test_save_and_load_config(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    saved = llm_config.save_config(
        base_url="https://example.com/v1", api_key="sk-abc", model="my-model"
    )
    assert path.exists()
    assert saved["base_url"] == "https://example.com/v1"
    assert saved["api_key"] == "sk-abc"
    assert saved["model"] == "my-model"
    assert llm_config.load_config() == saved


def test_save_config_preserves_unspecified_fields(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    llm_config.save_config(base_url="https://example.com/v1", api_key="sk-abc", model="m1")
    llm_config.save_config(base_url="https://other.com/v1")

    cfg = llm_config.load_config()
    assert cfg["base_url"] == "https://other.com/v1"
    assert cfg["api_key"] == "sk-abc"
    assert cfg["model"] == "m1"


def test_effective_config_local_overrides_env(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    assert llm_config.get_effective_config() == {
        "base_url": "https://env.example.com/v1",
        "api_key": "sk-env",
        "model": "env-model",
    }

    llm_config.save_config(
        base_url="https://local.example.com/v1", api_key="sk-local", model="local-model"
    )
    assert llm_config.get_effective_config() == {
        "base_url": "https://local.example.com/v1",
        "api_key": "sk-local",
        "model": "local-model",
    }


def test_effective_config_defaults_when_nothing_set(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    cfg = llm_config.get_effective_config()
    assert cfg["base_url"] == "https://api.openai.com/v1"
    assert cfg["api_key"] == ""
    assert cfg["model"] == "gpt-4o-mini"


def test_llm_presets_endpoint(client):
    resp = client.get("/api/llm/presets")
    assert resp.status_code == 200
    presets = resp.json()
    names = [p["name"] for p in presets]
    for expected in ("OpenAI", "DeepSeek", "Moonshot Kimi"):
        assert expected in names
    for p in presets:
        assert p["base_url"].startswith("http")
        assert p["default_model"]


def test_llm_config_get_and_put(client, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    resp = client.get("/api/llm/config")
    assert resp.status_code == 200
    assert resp.json()["base_url"] == "https://api.openai.com/v1"
    assert resp.json()["api_key"] == ""

    resp = client.put("/api/llm/config", json={
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-123",
        "model": "deepseek-chat",
    })
    assert resp.status_code == 200
    assert resp.json()["model"] == "deepseek-chat"

    resp = client.get("/api/llm/config")
    assert resp.json()["base_url"] == "https://api.deepseek.com/v1"
    assert resp.json()["api_key"] == "sk-123"
    assert resp.json()["model"] == "deepseek-chat"


def test_llm_config_persisted_to_local_file_not_db(client, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    client.put("/api/llm/config", json={
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "sk-secret",
        "model": "moonshot-v1-8k",
    })

    data_dir = config.settings.data_dir
    path = data_dir / "llm_config.json"
    assert path.exists()

    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["api_key"] == "sk-secret"

    conn = database._connect()
    try:
        rows = conn.execute("PRAGMA table_info(papers)").fetchall()
    finally:
        conn.close()
    columns = [r["name"] for r in rows]
    assert not any("key" in c.lower() for c in columns)
