import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app import config, database
from app.agent import sessions
from app.agent.compaction import KEEP_RECENT, compact_messages, should_compact


@pytest.fixture(autouse=True)
def _setup_db(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    database.init_db()
    sessions.clear_sessions()
    yield
    sessions.clear_sessions()


def test_should_compact_boundaries():
    assert should_compact(7900, 10000) is False
    assert should_compact(8000, 10000) is True
    assert should_compact(10000, 10000) is True


def test_should_compact_without_context_length():
    assert should_compact(999999, None) is False
    assert should_compact(999999, 0) is False


def _session_with_history(pairs: int):
    session = sessions.create_session()
    session.messages.append(SystemMessage(content="系统提示"))
    for i in range(pairs * 2):
        if i % 2 == 0:
            session.messages.append(HumanMessage(content=f"历史消息{i}"))
        else:
            session.messages.append(AIMessage(content=f"历史消息{i}"))
    return session


class SummaryLLM:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return AIMessage(content="- 结论A\n- 路径 /data/x.csv")


class BoomLLM:
    async def ainvoke(self, messages):
        raise RuntimeError("summary backend down")


async def test_compact_messages_replaces_old_history_and_persists():
    session = _session_with_history(pairs=4)
    original_texts = [m.content for m in session.messages]
    llm = SummaryLLM()

    ok = await compact_messages(session, llm)

    assert ok is True
    assert len(llm.calls) == 1
    prompt = llm.calls[0][0]
    assert "历史消息" in prompt.content

    messages = session.messages
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content.startswith("[历史摘要]")
    assert "结论A" in messages[1].content
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]
    assert len(non_system) == KEEP_RECENT + 1
    kept = [m.content for m in non_system[1:]]
    assert kept == original_texts[-KEEP_RECENT:]

    raw = sessions.get_raw_messages(session.session_id)
    assert any(isinstance(m, HumanMessage) and "[历史摘要]" in m.content for m in raw)
    assert isinstance(raw[0], SystemMessage)


async def test_compact_messages_skipped_when_recent_enough():
    session = _session_with_history(pairs=3)
    llm = SummaryLLM()

    ok = await compact_messages(session, llm)

    assert ok is False
    assert llm.calls == []
    assert len([m for m in session.messages if not isinstance(m, SystemMessage)]) == 6


async def test_compact_messages_failure_leaves_session_untouched():
    session = _session_with_history(pairs=4)
    snapshot = [(type(m).__name__, m.content) for m in list(session.messages)]

    ok = await compact_messages(session, BoomLLM())

    assert ok is False
    assert [(type(m).__name__, m.content) for m in session.messages] == snapshot
