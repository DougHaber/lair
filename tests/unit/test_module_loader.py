import os
import types
import pytest

from lair.module_loader import ModuleLoader


def create_module_file(path, name="mod", info=None):
    """Helper to create a module on disk and return the loaded module object."""
    if info is None:
        info = {"class": object}
    mod = types.ModuleType(name)
    file = path / f"{name}.py"
    file.write_text("\n")
    mod.__file__ = str(file)
    mod._module_info = lambda: info
    return mod


def test_get_module_files_filters(tmp_path):
    (tmp_path / "keep.py").write_text("\n")
    (tmp_path / "__init__.py").write_text("\n")
    (tmp_path / "ignore.txt").write_text("\n")
    (tmp_path / ".hidden.py").write_text("\n")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "inner.py").write_text("\n")
    loader = ModuleLoader()
    files = loader._get_module_files(tmp_path)
    relative = {os.path.relpath(f, tmp_path) for f in files}
    assert relative == {"keep.py", os.path.join("subdir", "inner.py")}


def test_get_module_name_converts_underscores(tmp_path):
    mod = create_module_file(tmp_path, name="my_mod_file")
    loader = ModuleLoader()
    name = loader._get_module_name(mod, tmp_path)
    assert name == "my-mod-file"


def test_validate_module_error_conditions(tmp_path):
    loader = ModuleLoader()
    good = create_module_file(tmp_path)
    loader._validate_module(good)  # should not raise

    missing = types.ModuleType("missing")
    with pytest.raises(Exception, match="not defined"):
        loader._validate_module(missing)

    notfunc = types.ModuleType("notfunc")
    notfunc._module_info = "nope"  # type: ignore
    with pytest.raises(Exception, match="not a function"):
        loader._validate_module(notfunc)

    bad_schema = create_module_file(tmp_path, name="bad", info={})
    with pytest.raises(Exception, match="Invalid _module_info"):
        loader._validate_module(bad_schema)


def test_register_module_alias_conflicts(tmp_path):
    loader = ModuleLoader()
    first = create_module_file(tmp_path, name="first", info={"class": object, "aliases": ["alias"]})
    loader._register_module(first, tmp_path)

    # Duplicate alias should raise an exception
    second = create_module_file(tmp_path, name="second", info={"class": object, "aliases": ["alias"]})
    with pytest.raises(Exception, match="repeat command / alias"):
        loader._register_module(second, tmp_path)


def test_import_file_success_and_failure(tmp_path, monkeypatch):
    loader = ModuleLoader()
    good_file = tmp_path / "good.py"
    good_file.write_text("def _module_info():\n    return {'class': object}\n")

    bad_file = tmp_path / "bad.py"
    bad_file.write_text("# no info here\n")

    warnings = []
    monkeypatch.setattr(loader, "_register_module", lambda *a, **k: warnings.append("registered"))
    loader.import_file(str(good_file), tmp_path)
    assert warnings == ["registered"]

    warnings.clear()
    monkeypatch.setattr(loader, "_register_module", lambda *a, **k: warnings.append("registered"))
    loader.import_file(str(bad_file), tmp_path)
    assert warnings == []


def test_load_modules_from_path(tmp_path):
    (tmp_path / "m1.py").write_text("def _module_info():\n    return {'class': object}\n")
    (tmp_path / "m2.py").write_text("def _module_info():\n    return {'class': object}\n")
    loader = ModuleLoader()
    loader.load_modules_from_path(tmp_path)
    assert {"m1", "m2"} <= set(loader.commands)


def test_register_module_name_conflicts_with_alias(tmp_path):
    loader = ModuleLoader()
    first = create_module_file(tmp_path, name="first", info={"class": object, "aliases": ["other"]})
    loader._register_module(first, tmp_path)

    # Now create a module whose name collides with existing alias
    second = create_module_file(tmp_path, name="other")
    with pytest.raises(Exception, match="repeat command name"):  # alias collides with command
        loader._register_module(second, tmp_path)
