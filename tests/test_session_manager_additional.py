import json

import pytest

import lair
from tests.test_session_manager import DummyChatSession, make_manager


def test_ensure_map_size_and_get_session_id(monkeypatch, tmp_path):
    manager, mod = make_manager(monkeypatch, tmp_path)
    manager.env.map_size = 50
    lair.config.set("database.sessions.size", 100, no_event=True)
    manager.ensure_correct_map_size()
    assert manager.env.map_size == 100

    assert not manager.is_alias_available("123")  # numeric aliases not allowed
    assert manager.get_session_id("missing", raise_exception=False) is None
    with pytest.raises(mod.UnknownSessionException):
        manager.get_session_id("missing")


def test_prune_empty_and_all_sessions(monkeypatch, tmp_path):
    manager, _ = make_manager(monkeypatch, tmp_path)
    with manager.env.begin(write=True) as txn:
        txn.put(b"session:00000001", json.dumps({"id": 1, "history": []}).encode())
        txn.put(
            b"session:00000002",
            json.dumps({"id": 2, "history": [{"role": "user", "content": "hi"}]}).encode(),
        )
    manager.prune_empty()
    sessions = list(manager.all_sessions())
    assert len(sessions) == 1 and sessions[0]["id"] == 2


def test_edges_and_refresh(monkeypatch, tmp_path):
    manager, _ = make_manager(monkeypatch, tmp_path)
    chat1 = DummyChatSession()
    chat1.history.messages.append({"role": "user", "content": "m"})
    manager.add_from_chat_session(chat1)

    assert manager._get_next_session_id() == 2
    assert manager.get_next_session_id(99) == 1
    assert manager.get_previous_session_id(99) == 1

    chat2 = DummyChatSession()
    chat2.session_id = 5
    chat2.session_alias = "five"
    chat2.history.messages.append({"role": "assistant", "content": "hello"})
    manager.refresh_from_chat_session(chat2)
    assert manager.get_session_id("five") == 5

    with pytest.raises(ValueError):
        manager.set_alias(chat1.session_id, "five")

    manager.delete_session("five")
    assert manager.get_session_id("five", raise_exception=False) is None
    assert manager.get_session_dict(chat1.session_id)["id"] == chat1.session_id
