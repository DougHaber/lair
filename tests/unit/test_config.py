from lair.config import Configuration, ConfigInvalidTypeError, ConfigUnknownKeyError
import os
import types
import lair
import pytest


def create_config(tmp_path, yaml_text):
    home = tmp_path
    (home / ".lair").mkdir()
    (home / ".lair" / "config.yaml").write_text(yaml_text)
    return str(home)


def test_inherit_with_list(tmp_path, monkeypatch):
    home = create_config(
        tmp_path,
        """
foo:
  a: 1
bar:
  _inherit: [foo]
  b: 2
""",
    )
    monkeypatch.setenv("HOME", home)
    config = Configuration()
    assert config.modes["bar"]["a"] == 1
    assert config.modes["bar"]["b"] == 2


def test_inherit_with_string(tmp_path, monkeypatch):
    home = create_config(
        tmp_path,
        """
foo:
  a: 1
bar:
  _inherit: "['foo']"
  b: 2
""",
    )
    monkeypatch.setenv("HOME", home)
    config = Configuration()
    assert config.modes["bar"]["a"] == 1
    assert config.modes["bar"]["b"] == 2


def test_init_creates_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    monkeypatch.setattr(lair.sessions.openai_chat_session, "openai", types.SimpleNamespace(OpenAI=lambda **k: None))
    assert not os.path.isdir(tmp_path / ".lair")
    config = Configuration()
    assert (tmp_path / ".lair" / "config.yaml").is_file()
    assert config.get("chat.attachments_enabled") is True


def test_set_cast_and_errors(tmp_path, monkeypatch):
    home = create_config(tmp_path, "foo:\n  a: 1")
    monkeypatch.setenv("HOME", home)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    monkeypatch.setattr(lair.sessions.openai_chat_session, "openai", types.SimpleNamespace(OpenAI=lambda **k: None))
    config = Configuration()

    config.set("chat.attachments_enabled", "False")
    assert config.get("chat.attachments_enabled") is False

    with pytest.raises(ConfigInvalidTypeError):
        config.set("chat.attachments_enabled", "nope")

    with pytest.raises(ConfigUnknownKeyError):
        config.set("unknown.key", True)

    config.set("session.max_history_length", "")
    assert config.get("session.max_history_length") is None

    assert config.get("missing", allow_not_found=True, default=10) == 10


def test_parse_inherit_various():
    import importlib

    cfg = importlib.import_module("lair.config")
    assert cfg._parse_inherit("") == []
    assert cfg._parse_inherit("[a , 'b']") == ["a", "b"]
