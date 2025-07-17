import types

import pytest

import lair.logging as logging_mod
from lair.module_loader import ModuleLoader


def test_init_logging_and_exit(monkeypatch):
    printed = []
    monkeypatch.setattr(logging_mod, "console", types.SimpleNamespace(print=lambda t: printed.append(str(t))))
    logging_mod.init_logging(enable_debugging=True)
    logging_mod.logger.info("hi")
    assert any("hi" in p for p in printed)
    with pytest.raises(SystemExit):
        logging_mod.logger.exit_error("fail")


def make_dummy_module(tmp_path, name="mod"):
    mod = types.ModuleType(name)
    path = tmp_path / f"{name}.py"
    mod.__file__ = str(path)
    mod._module_info = lambda: {"class": object}
    path.write_text("")
    return mod


def test_module_loader_register(tmp_path):
    loader = ModuleLoader()
    mod = make_dummy_module(tmp_path)
    loader._register_module(mod, tmp_path)
    name = loader._get_module_name(mod, tmp_path)
    assert name in loader.modules
    try:
        loader._register_module(mod, tmp_path)
        raise AssertionError("Expected duplicate registration failure")
    except Exception as exc:
        assert "Unable to register repeat name" in str(exc)


def test_module_loader_validate(tmp_path):
    loader = ModuleLoader()
    mod = make_dummy_module(tmp_path)
    loader._validate_module(mod)
    bad = types.ModuleType("bad")
    try:
        loader._validate_module(bad)
        raise AssertionError("Expected missing _module_info failure")
    except Exception as exc:
        assert "_module_info not defined" in str(exc)
