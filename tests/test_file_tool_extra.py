from pathlib import Path

import pytest

import lair
from lair.components.tools.file_tool import FileTool


@pytest.fixture()
def tool(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    lair.config.set("tools.file.path", str(workspace), no_event=True)
    return FileTool()


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
