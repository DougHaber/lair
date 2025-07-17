import importlib
import lair
import pytest
from tests.test_config_module import make_config_env

config_module = importlib.import_module("lair.config")


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
    assert cfg.active_mode == "test"  # unchanged because no default_mode


def test_set_inherit_and_invalid_cast(tmp_path, monkeypatch):
    make_config_env(tmp_path, monkeypatch)
    cfg = config_module.Configuration()
    cfg.set("_inherit", ["base"])  # special-case key
    assert cfg.get("_inherit") == ["base"]
    with pytest.raises(config_module.ConfigInvalidType):
        cfg.set("session.max_history_length", "oops")
