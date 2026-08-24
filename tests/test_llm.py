import pytest

from app import llm
from app.presets import LLM_PRESETS


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChatModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return FakeMessage('{"query": "attention mechanism transformer"}')


async def test_decompose_topic_uses_langchain_chatopenai(monkeypatch):
    created = {}

    def fake_chat(**kwargs):
        created["kwargs"] = kwargs
        return FakeChatModel(**kwargs)

    monkeypatch.setattr(llm, "ChatOpenAI", fake_chat)
    monkeypatch.setattr(llm, "get_effective_config", lambda: {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "sk-test",
        "model": "deepseek-chat",
    })

    result = await llm.decompose_topic("transformers")

    assert result == "attention mechanism transformer"
    assert created["kwargs"]["base_url"] == "https://api.deepseek.com/v1"
    assert created["kwargs"]["api_key"] == "sk-test"
    assert created["kwargs"]["model"] == "deepseek-chat"


async def test_decompose_topic_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(llm, "get_effective_config", lambda: {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
    })
    with pytest.raises(ValueError):
        await llm.decompose_topic("topic")


def test_parse_content_handles_code_fence():
    assert llm._parse_content('```json\n{"query": "hello world"}\n```') == "hello world"
    assert llm._parse_content('{"query": "  hello world  "}') == "hello world"
    assert llm._parse_content("plain text query") == "plain text query"


def test_presets_include_required_platforms():
    names = [p["name"] for p in LLM_PRESETS]
    for expected in ("OpenAI", "DeepSeek", "Moonshot Kimi"):
        assert expected in names
    for p in LLM_PRESETS:
        assert p["base_url"].startswith("http")
        assert p["default_model"]
