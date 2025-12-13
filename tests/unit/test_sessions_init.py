import importlib
import sys
import types

import pytest

import lair.sessions as sessions


def test_get_chat_session_openai(monkeypatch):
    class DummyOpenAI:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=DummyOpenAI))
    import lair.sessions.openai_chat_session as ocs

    importlib.reload(ocs)
    importlib.reload(sessions)
    session = sessions.get_chat_session("openai_chat")
    assert isinstance(session, ocs.OpenAIChatSession)


def test_get_chat_session_unknown():
    with pytest.raises(ValueError):
        sessions.get_chat_session("other")
