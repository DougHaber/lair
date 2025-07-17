import pytest
import lair
from lair.sessions import get_chat_session, OpenAIChatSession
import lair.sessions.openai_chat_session as ocs


def test_get_chat_session_openai(monkeypatch):
    monkeypatch.setattr(lair.events, "subscribe", lambda *a, **k: None)
    session = get_chat_session("openai_chat")
    assert isinstance(session, OpenAIChatSession)


def test_get_chat_session_unknown():
    with pytest.raises(ValueError):
        get_chat_session("bogus")
