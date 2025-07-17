import builtins
import datetime
import os
from pathlib import Path

import pytest

import lair
from lair.components.tools.file_tool import FileTool


@pytest.fixture
def file_tool(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    lair.config.set("tools.file.path", str(workspace), no_event=True)
    return FileTool()


@pytest.fixture()
def tool(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    lair.config.set("tools.file.path", str(workspace), no_event=True)
    return FileTool()


def setup_tool(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    lair.config.set("tools.file.path", str(workspace), no_event=True)
    return FileTool(), workspace


def test_resolve_path_within_and_outside(file_tool, tmp_path):
    base = tmp_path / "workspace"
    lair.config.set("tools.file.path", str(base), no_event=True)
    inside = file_tool._resolve_path("a.txt")
    assert inside == os.path.join(str(base), "a.txt")
    with pytest.raises(ValueError):
        file_tool._resolve_path("../evil.txt")


def test_list_directory_basic(file_tool):
    workspace = lair.config.get("tools.file.path")
    f = os.path.join(workspace, "file.txt")
    with open(f, "w") as fd:
        fd.write("data")
    result = file_tool.list_directory(".")
    names = [e["name"] for e in result["contents"]]
    assert "file.txt" in names
    error = file_tool.list_directory("file.txt")
    assert "not a directory" in error["error"]


def test_read_file_patterns_and_errors(file_tool, tmp_path):
    ws = tmp_path / "workspace"
    lair.config.set("tools.file.path", str(ws), no_event=True)
    (ws / "a.txt").write_text("first")
    sub = ws / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("second")
    result = file_tool.read_file("**/*.txt")
    assert result["file_content"] == {"a.txt": "first", os.path.join("sub", "b.txt"): "second"}
    error = file_tool.read_file("nomatch/*.txt")
    assert "No files match" in error["error"]
    outside = tmp_path / "outside.txt"
    outside.write_text("bad")
    deny = file_tool.read_file(str(outside))
    assert "outside the workspace" in deny["error"]


def test_write_and_delete_file(file_tool):
    msg = file_tool.write_file("new/thing.txt", "hello")
    path = file_tool._resolve_path("new/thing.txt")
    assert os.path.isfile(path)
    assert msg["message"].endswith(f"'{path}'.")
    with open(path) as fd:
        assert fd.read() == "hello"
    bad = file_tool.write_file("../bad.txt", "oops")
    assert "outside the workspace" in bad["error"]
    deleted = file_tool.delete_file("new/thing.txt")
    assert os.path.isfile(path) is False and "deleted" in deleted["message"]
    missing = file_tool.delete_file("none.txt")
    assert "not a file" in missing["error"]


def test_directory_creation_and_removal(file_tool):
    make = file_tool.make_directory("dir/sub")
    created = file_tool._resolve_path("dir/sub")
    assert os.path.isdir(created)
    assert "created" in make["message"]
    removed = file_tool.remove_directory("dir/sub")
    assert not os.path.isdir(created) and "removed" in removed["message"]
    error = file_tool.remove_directory("dir/sub")
    assert "not a directory" in error["error"]


def test_list_directory_returns_details(tmp_path):
    tool, workspace = setup_tool(tmp_path)
    file_path = workspace / "f.txt"
    file_path.write_text("content")
    result = tool.list_directory(".")
    assert result["contents"][0]["name"] == "f.txt"
    perms = result["contents"][0]["permissions"]
    assert len(perms) >= 3
    ts = result["contents"][0]["last_modified"]
    datetime.datetime.fromisoformat(ts)


def test_list_directory_handles_oserror(monkeypatch, tmp_path):
    tool, _ = setup_tool(tmp_path)

    def bad_listdir(path):
        raise OSError("boom")

    monkeypatch.setattr(os, "listdir", bad_listdir)
    out = tool.list_directory(".")
    assert out["error"] == "boom"


def test_write_file_open_exception(monkeypatch, tmp_path):
    tool, _ = setup_tool(tmp_path)
    called = {}

    def bad_open(*args, **kwargs):
        called["hit"] = True
        raise OSError("fail")

    monkeypatch.setattr(builtins, "open", bad_open)
    result = tool.write_file("a.txt", "data")
    assert called.get("hit")
    assert result["error"] == "fail"


def test_delete_file_given_directory(tmp_path):
    tool, workspace = setup_tool(tmp_path)
    d = workspace / "dir"
    d.mkdir()
    res = tool.delete_file("dir")
    assert "not a file" in res["error"]


def test_generate_definitions_include_workspace(tool, tmp_path):
    workspace = lair.config.get("tools.file.path")
    assert workspace in tool._generate_list_directory_definition()["function"]["description"]
    assert workspace in tool._generate_read_file_definition()["function"]["description"]
    assert workspace in tool._generate_write_file_definition()["function"]["description"]
    assert workspace in tool._generate_delete_file_definition()["function"]["description"]
    assert workspace in tool._generate_make_directory_definition()["function"]["description"]
    assert workspace in tool._generate_remove_directory_definition()["function"]["description"]


def test_list_directory_outside_workspace(tool, tmp_path):
    outside = tmp_path / "other"
    outside.mkdir()
    result = tool.list_directory(str(outside))
    assert "outside the workspace" in result["error"]


def test_read_file_skips_directories(tool):
    workspace = Path(lair.config.get("tools.file.path"))
    (workspace / "a.txt").write_text("hello")
    (workspace / "dir").mkdir()
    response = tool.read_file("**")
    assert "a.txt" in response["file_content"]
    assert "dir" not in response["file_content"]


def test_read_file_handles_exception(monkeypatch, tool):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    import lair.components.tools.file_tool as ft

    monkeypatch.setattr(ft.glob, "glob", boom)
    result = tool.read_file("*.txt")
    assert "boom" in result["error"]


def test_make_directory_error(tool):
    result = tool.make_directory("../bad")
    assert "outside the workspace" in result["error"]


def test_delete_file_error(tool):
    result = tool.delete_file("../bad.txt")
    assert "outside the workspace" in result["error"]


def test_remove_directory_exception(monkeypatch, tool):
    workspace = Path(lair.config.get("tools.file.path"))
    dir_path = workspace / "subdir"
    dir_path.mkdir()

    def raise_oserror(path):
        raise OSError("fail")

    import lair.components.tools.file_tool as ft

    monkeypatch.setattr(ft.os, "rmdir", raise_oserror)
    result = tool.remove_directory("subdir")
    assert result["error"] == "fail"
