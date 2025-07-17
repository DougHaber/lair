import os
import stat
import datetime
import builtins
import lair
from lair.components.tools.file_tool import FileTool


def setup_tool(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    lair.config.set("tools.file.path", str(workspace), no_event=True)
    return FileTool(), workspace


def test_list_directory_returns_details(tmp_path):
    tool, workspace = setup_tool(tmp_path)
    file_path = workspace / "f.txt"
    file_path.write_text("content")
    # ensure file stats set
    result = tool.list_directory(".")
    assert result["contents"][0]["name"] == "f.txt"
    # permissions string should be three digits
    perms = result["contents"][0]["permissions"]
    assert len(perms) >= 3
    # timestamp should be ISO formatted
    ts = result["contents"][0]["last_modified"]
    datetime.datetime.fromisoformat(ts)


def test_list_directory_handles_oserror(monkeypatch, tmp_path):
    tool, workspace = setup_tool(tmp_path)

    def bad_listdir(path):
        raise OSError("boom")

    monkeypatch.setattr(os, "listdir", bad_listdir)
    out = tool.list_directory(".")
    assert out["error"] == "boom"


def test_write_file_open_exception(monkeypatch, tmp_path):
    tool, workspace = setup_tool(tmp_path)
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
