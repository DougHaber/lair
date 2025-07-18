import json

import pytest

import lair
from lair.components.history import ChatHistory
from lair.sessions import serializer


class DummySession:
    def __init__(self):
        self.session_id = 1
        self.session_alias = "alias"
        self.session_title = "title"
        self.last_prompt = "prompt"
        self.last_response = "response"
        self.history = ChatHistory()
        self.history.add_message("user", "hi")


def test_session_to_dict(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(lair.config, "active_mode", "test-mode", raising=False)
    monkeypatch.setattr(lair.config, "get_modified_config", lambda: {"modified": True})
    original_get = lair.config.get

    def patched_get(key, allow_not_found=False, default=None):
        if key == "model.name":
            return "patched-model"
        return original_get(key, allow_not_found, default)

    monkeypatch.setattr(lair.config, "get", patched_get)
    result = serializer.session_to_dict(session)
    assert result["version"] == "0.2"
    assert result["settings"] == {"modified": True}
    assert result["session"]["mode"] == "test-mode"
    assert result["session"]["model_name"] == "patched-model"
    assert result["history"] == session.history.get_messages()


def test_save_and_load(tmp_path, monkeypatch):
    session = DummySession()
    monkeypatch.setattr(lair.config, "active_mode", "save-mode", raising=False)
    monkeypatch.setattr(lair.config, "get_modified_config", lambda: {})
    original_get = lair.config.get

    def patched_get(key, allow_not_found=False, default=None):
        if key == "model.name":
            return "save-model"
        return original_get(key, allow_not_found, default)

    monkeypatch.setattr(lair.config, "get", patched_get)
    file_path = tmp_path / "state.json"
    serializer.save(session, file_path)
    saved = json.loads(file_path.read_text())
    assert saved["session"]["model_name"] == "save-model"
    changes = {}
    monkeypatch.setattr(lair.config, "change_mode", lambda mode: changes.setdefault("mode", mode))
    monkeypatch.setattr(lair.config, "update", lambda data: changes.setdefault("settings", data))
    new_session = DummySession()
    serializer.load(new_session, file_path)
    assert new_session.session_id == session.session_id
    assert new_session.session_alias == session.session_alias
    assert new_session.session_title == session.session_title
    assert new_session.last_prompt == session.last_prompt
    assert new_session.last_response == session.last_response
    assert new_session.history.get_messages() == session.history.get_messages()
    assert changes == {"mode": "save-mode", "settings": {}}


def test_update_session_from_dict_errors():
    session = DummySession()
    with pytest.raises(Exception, match="missing 'version'"):
        serializer.update_session_from_dict(session, {})
    with pytest.raises(Exception, match="no longer supported"):
        serializer.update_session_from_dict(session, {"version": "0.1"})
    with pytest.raises(Exception, match="unknown version"):
        serializer.update_session_from_dict(session, {"version": "unknown"})
