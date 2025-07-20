import builtins
import importlib
import sys
import types

import lair.util.core as core


def test_safe_int():
    assert core.safe_int("5") == 5
    assert core.safe_int("abc") == "abc"


def test_decode_jsonl():
    jsonl = '{"a":1}\n{"b":2}\n'
    assert core.decode_jsonl(jsonl) == [{"a": 1}, {"b": 2}]


def test_slice_from_str():
    data = [0, 1, 2, 3, 4, 5]
    assert core.slice_from_str(data, ":2") == [0, 1]
    assert core.slice_from_str(data, "1:4:2") == [1, 3]
    assert core.slice_from_str(data, "-2:") == [4, 5]


def test_expand_filename_list(tmp_path):
    f1 = tmp_path / "one.txt"
    f2 = tmp_path / "two.txt"
    f1.write_text("a")
    f2.write_text("b")
    pattern = str(tmp_path / "*.txt")
    result = core.expand_filename_list([pattern])
    assert str(f1) in result and str(f2) in result




def test_convert_scalar_none():
    assert core._convert_scalar("null") is None
    assert core._convert_scalar("~") is None
    assert core._convert_scalar("") is None


def test_parse_yaml_text_no_yaml(monkeypatch):
    # simulate missing yaml module at import time
    monkeypatch.setitem(sys.modules, "yaml", None)
    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    importlib.reload(core)
    assert core.yaml is None
    assert core.parse_yaml_text("a: 1") == {"a": 1}
    monkeypatch.setattr(builtins, "__import__", orig_import)
    importlib.reload(core)


def test_parse_yaml_text_fallback(monkeypatch):
    def fail(_text):
        raise Exception("boom")

    monkeypatch.setattr(core, "yaml", types.SimpleNamespace(safe_load=fail))
    assert core.parse_yaml_text("b: 2") == {"b": 2}
