import pytest

import lair
from lair.sessions import OpenAIChatSession, get_chat_session


def test_get_chat_session_openai(monkeypatch):
    monkeypatch.setattr(lair.events, "subscribe", lambda *a, **k: None)
    session = get_chat_session("openai_chat")
    assert isinstance(session, OpenAIChatSession)


def test_get_chat_session_unknown():
    with pytest.raises(ValueError):
        get_chat_session("bogus")
