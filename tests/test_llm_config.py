import json

import pytest

from app import config, database, llm_config


def _set_config_path(tmp_path, monkeypatch):
    path = tmp_path / "llm_config.json"
    monkeypatch.setenv("LLM_CONFIG_PATH", str(path))
    return path


def _group(**overrides):
    reasoning_efforts = overrides.pop("reasoning_efforts", [])
    model_ids = overrides.pop("models", ["gpt-4o-mini", "gpt-4o"])
    default_model = overrides.pop("default_model", model_ids[0] if model_ids else "")
    models = [
        {
            "id": mid,
            "context_length": None,
            "reasoning_efforts": list(reasoning_efforts) if mid == default_model else [],
        }
        for mid in model_ids
    ]
    group = {
        "id": "oai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-abc",
        "models": models,
        "default_model": default_model,
    }
    group.update(overrides)
    return group


def test_load_config_migrates_legacy_flat_structure(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    path.write_text(
        json.dumps(
            {
                "base_url": "https://example.com/v1",
                "api_key": "sk-legacy",
                "model": "legacy-model",
                "reasoning_effort": "high",
            }
        ),
        encoding="utf-8",
    )

    cfg = llm_config.load_config()
    assert cfg["active_group"] == "default"
    assert len(cfg["groups"]) == 1
    group = cfg["groups"][0]
    assert group["id"] == "default"
    assert group["name"] == "默认"
    assert group["base_url"] == "https://example.com/v1"
    assert group["api_key"] == "sk-legacy"
    assert group["models"] == [
        {"id": "legacy-model", "context_length": None, "reasoning_efforts": ["high"]}
    ]
    assert group["default_model"] == "legacy-model"

    # Idempotent: reloading does not duplicate groups.
    again = llm_config.load_config()
    assert again == cfg
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["active_group"] == "default"
    assert len(raw["groups"]) == 1


def test_save_and_load_config_round_trip(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    saved = llm_config.save_config(
        {"active_group": "oai", "groups": [_group()]}
    )
    assert path.exists()
    assert saved["active_group"] == "oai"
    assert saved["groups"][0]["api_key"] == "sk-abc"
    assert llm_config.load_config() == saved


def test_save_config_default_model_falls_back_to_first_model(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    saved = llm_config.save_config(
        {
            "active_group": "oai",
            "groups": [
                {
                    "id": "oai",
                    "name": "OpenAI",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-abc",
                    "models": ["gpt-4o-mini", "gpt-4o"],
                }
            ],
        }
    )
    assert saved["groups"][0]["default_model"] == "gpt-4o-mini"


def test_save_config_rejects_missing_active_group(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        llm_config.save_config({"active_group": "nope", "groups": [_group()]})


def test_save_config_rejects_duplicate_ids(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        llm_config.save_config(
            {"active_group": "oai", "groups": [_group(), _group()]}
        )


def test_save_config_rejects_empty_groups(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        llm_config.save_config({"active_group": "oai", "groups": []})


def test_effective_config_uses_active_group(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    llm_config.save_config(
        {
            "active_group": "ali",
            "groups": [
                _group(
                    id="ali",
                    name="阿里云",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
                    api_key="sk-ali",
                    models=["qwen-plus", "qwen-max"],
                    default_model="qwen-max",
                    reasoning_efforts=["medium"],
                ),
                _group(id="oai", api_key="sk-oai"),
            ],
        }
    )
    assert llm_config.get_effective_config() == {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-ali",
        "model": "qwen-max",
        "reasoning_effort": "medium",
    }


def test_effective_config_env_and_defaults_when_nothing_set(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)

    cfg = llm_config.get_effective_config()
    assert cfg["base_url"] == "https://api.openai.com/v1"
    assert cfg["api_key"] == ""
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["reasoning_effort"] == ""


def test_effective_config_env_fallback_when_group_field_empty(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-env")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)

    assert llm_config.get_effective_config() == {
        "base_url": "https://env.example.com/v1",
        "api_key": "sk-env",
        "model": "env-model",
        "reasoning_effort": "",
    }


def test_load_config_synthesizes_default_when_no_file(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    cfg = llm_config.load_config()
    assert cfg["active_group"] == "default"
    assert len(cfg["groups"]) == 1
    assert cfg["groups"][0]["id"] == "default"
    assert cfg["groups"][0]["default_model"] == "gpt-4o-mini"


def test_migrates_string_models_to_objects_with_group_reasoning_effort(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    path.write_text(
        json.dumps(
            {
                "active_group": "oai",
                "groups": [
                    {
                        "id": "oai",
                        "name": "OpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "sk-abc",
                        "models": ["gpt-4o-mini", "gpt-4o"],
                        "default_model": "gpt-4o-mini",
                        "reasoning_effort": "medium",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cfg = llm_config.load_config()
    group = cfg["groups"][0]
    assert group["models"] == [
        {"id": "gpt-4o-mini", "context_length": None, "reasoning_efforts": ["medium"]},
        {"id": "gpt-4o", "context_length": None, "reasoning_efforts": ["medium"]},
    ]
    assert group["default_model"] == "gpt-4o-mini"
    assert "reasoning_effort" not in group

    # Idempotent: reloading does not change the migrated result.
    assert llm_config.load_config() == cfg


def test_migrates_group_reasoning_effort_to_default_model_entry(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    path.write_text(
        json.dumps(
            {
                "active_group": "oai",
                "groups": [
                    {
                        "id": "oai",
                        "name": "OpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "sk-abc",
                        "models": [
                            {"id": "gpt-4o-mini", "context_length": 128000, "reasoning_effort": ""},
                            {"id": "gpt-4o", "context_length": 128000, "reasoning_effort": "high"},
                        ],
                        "default_model": "gpt-4o-mini",
                        "reasoning_effort": "medium",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cfg = llm_config.load_config()
    group = cfg["groups"][0]
    assert group["models"] == [
        {"id": "gpt-4o-mini", "context_length": 128000, "reasoning_efforts": ["medium"]},
        {"id": "gpt-4o", "context_length": 128000, "reasoning_efforts": ["high"]},
    ]
    assert "reasoning_effort" not in group
    assert llm_config.get_effective_config()["reasoning_effort"] == "medium"


def test_save_config_preserves_model_metadata(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    saved = llm_config.save_config(
        {
            "active_group": "oai",
            "groups": [
                {
                    "id": "oai",
                    "name": "OpenAI",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-abc",
                    "models": [
                        {"id": "gpt-4o-mini", "context_length": 128000, "reasoning_efforts": ["medium"]},
                        {"id": "gpt-4o", "context_length": 1048576, "reasoning_efforts": []},
                    ],
                    "default_model": "gpt-4o-mini",
                }
            ],
        }
    )
    assert saved["groups"][0]["models"] == [
        {"id": "gpt-4o-mini", "context_length": 128000, "reasoning_efforts": ["medium"]},
        {"id": "gpt-4o", "context_length": 1048576, "reasoning_efforts": []},
    ]
    assert llm_config.load_config() == saved


def test_migrates_single_reasoning_effort_to_list(tmp_path, monkeypatch):
    path = _set_config_path(tmp_path, monkeypatch)
    path.write_text(
        json.dumps(
            {
                "active_group": "oai",
                "groups": [
                    {
                        "id": "oai",
                        "name": "OpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "sk-abc",
                        "models": [
                            {"id": "gpt-4o-mini", "reasoning_effort": "low"},
                            {"id": "gpt-4o", "reasoning_effort": ""},
                        ],
                        "default_model": "gpt-4o-mini",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cfg = llm_config.load_config()
    group = cfg["groups"][0]
    assert group["models"] == [
        {"id": "gpt-4o-mini", "context_length": None, "reasoning_efforts": ["low"]},
        {"id": "gpt-4o", "context_length": None, "reasoning_efforts": []},
    ]
    assert llm_config.get_effective_config()["reasoning_effort"] == "low"

    # Idempotent: reloading does not change the migrated result.
    assert llm_config.load_config() == cfg


def test_effective_config_reasoning_effort_empty_when_list_empty(tmp_path, monkeypatch):
    _set_config_path(tmp_path, monkeypatch)
    llm_config.save_config(
        {
            "active_group": "oai",
            "groups": [
                _group(models=["gpt-4o"], default_model="gpt-4o", reasoning_efforts=[])
            ],
        }
    )
    assert llm_config.get_effective_config()["reasoning_effort"] == ""


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
