import os
import pytest

import lair
import importlib

config_module = importlib.import_module("lair.config")


def make_config_env(tmp_path, monkeypatch):
    """Prepare HOME and patch read_package_file for config initialization."""
    monkeypatch.setenv("HOME", str(tmp_path))
    os.makedirs(tmp_path, exist_ok=True)
    orig_read = lair.util.read_package_file

    def fake_read(path, name):
        if name == "config.yaml":
            return "default_mode: test\ntest:\n  chat.attachments_enabled: false\n"
        return orig_read(path, name)

    monkeypatch.setattr(lair.util, "read_package_file", fake_read)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)


def test_configuration_initializes_and_loads(tmp_path, monkeypatch):
    make_config_env(tmp_path, monkeypatch)
    cfg = config_module.Configuration()
    config_file = tmp_path / ".lair" / "config.yaml"
    assert config_file.is_file()
    with open(config_file) as fd:
        assert "default_mode: test" in fd.read()
    assert cfg.active_mode == "test"
    assert cfg.get("chat.attachments_enabled") is False


def test_add_config_errors_and_change_mode(tmp_path, monkeypatch):
    make_config_env(tmp_path, monkeypatch)
    cfg = config_module.Configuration()
    # default_mode not found should raise SystemExit
    with pytest.raises(SystemExit):
        cfg._add_config({"default_mode": "missing"})
    # unknown mode change
    with pytest.raises(Exception):
        cfg.change_mode("missing")


def test_update_get_set_and_cast(monkeypatch, tmp_path):
    make_config_env(tmp_path, monkeypatch)
    cfg = config_module.Configuration()
    # force update
    cfg.update({"chat.enable_toolbar": False}, force=True)
    assert cfg.get("chat.enable_toolbar") is False
    # get unknown
    with pytest.raises(ValueError):
        cfg.get("nope")
    # set unknown key
    with pytest.raises(config_module.ConfigUnknownKeyException):
        cfg.set("nope", 1)
    # invalid bool value triggers ConfigInvalidType
    with pytest.raises(config_module.ConfigInvalidType):
        cfg.set("chat.attachments_enabled", "maybe")
    # cast empty string for int returns None
    assert cfg._cast_value("session.max_history_length", "") is None


def test_add_config_inherit_and_no_default(tmp_path, monkeypatch):
    make_config_env(tmp_path, monkeypatch)
    cfg = config_module.Configuration()
    new_config = {
        "base": {"chat.enable_toolbar": False},
        "child": {"_inherit": ["base"], "chat.attachments_enabled": True},
    }
    cfg._add_config(new_config)
    assert cfg.modes["child"]["chat.enable_toolbar"] is False
    assert cfg.modes["child"]["chat.attachments_enabled"] is True
    assert cfg.active_mode == "test"


def test_set_inherit_and_invalid_cast(tmp_path, monkeypatch):
    make_config_env(tmp_path, monkeypatch)
    cfg = config_module.Configuration()
    cfg.set("_inherit", ["base"])
    assert cfg.get("_inherit") == ["base"]
    with pytest.raises(config_module.ConfigInvalidType):
        cfg.set("session.max_history_length", "oops")
