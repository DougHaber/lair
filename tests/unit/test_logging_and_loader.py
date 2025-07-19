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
    with pytest.raises(Exception):
        loader._register_module(mod, tmp_path)


def test_module_loader_validate(tmp_path):
    loader = ModuleLoader()
    mod = make_dummy_module(tmp_path)
    loader._validate_module(mod)
    bad = types.ModuleType("bad")
    with pytest.raises(Exception):
        loader._validate_module(bad)

def test_get_module_files(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / ".hidden.py").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.py").write_text("")
    loader = ModuleLoader()
    files = loader._get_module_files(tmp_path)
    assert set(files) == {str(tmp_path / "a.py"), str(sub / "b.py")}


def test_get_module_name(tmp_path):
    mod = types.ModuleType("x_mod")
    sub = tmp_path / "some_dir"
    sub.mkdir()
    file = sub / "my_file.py"
    file.write_text("")
    mod.__file__ = str(file)
    loader = ModuleLoader()
    name = loader._get_module_name(mod, tmp_path)
    assert name.endswith("some-dir/my-file")


def test_validate_module_errors(tmp_path):
    loader = ModuleLoader()
    mod = types.ModuleType("bad")
    mod.__file__ = str(tmp_path / "bad.py")
    (tmp_path / "bad.py").write_text("")
    mod._module_info = "not_callable"
    with pytest.raises(Exception, match="not a function"):
        loader._validate_module(mod)

    def bad_info():
        return {"wrong": True}

    mod._module_info = bad_info
    with pytest.raises(Exception, match="Invalid _module_info"):
        loader._validate_module(mod)


def test_import_file_success(tmp_path, monkeypatch):
    loader = ModuleLoader()
    file = tmp_path / "m.py"
    file.write_text("def _module_info():\n    return {'class': object}\n")
    called = {}
    monkeypatch.setattr(loader, "_validate_module", lambda m: called.setdefault("v", True))
    monkeypatch.setattr(loader, "_register_module", lambda m, p: called.setdefault("r", True))
    loader.import_file(str(file), tmp_path)
    assert called == {"v": True, "r": True}


def test_import_file_failure(tmp_path, monkeypatch):
    loader = ModuleLoader()
    file = tmp_path / "bad.py"
    file.write_text("def _module_info():\n    return {'class': object}\n")
    monkeypatch.setattr(loader, "_validate_module", lambda m: (_ for _ in ()).throw(Exception("boom")))
    warnings = []
    monkeypatch.setattr(logging_mod.logger, "warning", lambda msg: warnings.append(msg))
    loader.import_file(str(file), tmp_path)
    assert any("boom" in w for w in warnings)


def test_load_modules_from_path_sorted(monkeypatch):
    loader = ModuleLoader()
    files = ["/z.py", "/a.py"]
    monkeypatch.setattr(loader, "_get_module_files", lambda p: files)
    order = []
    monkeypatch.setattr(loader, "import_file", lambda f, p: order.append(f))
    loader.load_modules_from_path("unused")
    assert order == sorted(files)
