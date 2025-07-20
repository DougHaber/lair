import os

import pytest

import lair
from lair.components.tools.file_tool import FileTool


@pytest.fixture
def file_tool(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    lair.config.set("tools.file.path", str(workspace), no_event=True)
    return FileTool()


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


def test_generate_definitions(file_tool):
    defs = file_tool._generate_list_directory_definition()
    assert defs["function"]["name"] == "list_directory"
    write_def = file_tool._generate_write_file_definition()
    assert lair.config.get("tools.file.path") in write_def["function"]["description"]


def test_additional_generate_definitions(file_tool):
    workspace = lair.config.get("tools.file.path")

    read_def = file_tool._generate_read_file_definition()
    assert read_def["function"]["name"] == "read_file"
    assert workspace in read_def["function"]["description"]
    assert read_def["function"]["parameters"]["required"] == ["path"]

    delete_def = file_tool._generate_delete_file_definition()
    assert delete_def["function"]["name"] == "delete_file"
    assert workspace in delete_def["function"]["description"]

    make_def = file_tool._generate_make_directory_definition()
    assert make_def["function"]["name"] == "make_directory"

    remove_def = file_tool._generate_remove_directory_definition()
    assert remove_def["function"]["name"] == "remove_directory"


def test_error_paths(file_tool, monkeypatch):
    monkeypatch.setattr(file_tool, "_resolve_path", lambda p: (_ for _ in ()).throw(ValueError("bad")))
    out = file_tool.list_directory(".")
    assert "bad" in out["error"]
    out2 = file_tool.write_file("a", "b")
    assert "bad" in out2["error"]
    out3 = file_tool.delete_file("a")
    assert "bad" in out3["error"]
    out4 = file_tool.make_directory("a")
    assert "bad" in out4["error"]
    out5 = file_tool.remove_directory("a")
    assert "bad" in out5["error"]


def test_read_file_skips_directories(file_tool):
    base = lair.config.get("tools.file.path")
    dir1 = os.path.join(base, "dir")
    os.makedirs(dir1)
    with open(os.path.join(dir1, "f.txt"), "w") as fh:
        fh.write("data")
    os.makedirs(os.path.join(base, "dir2"))
    res = file_tool.read_file("**")
    assert list(res["file_content"].values()) == ["data"]


def test_generate_remaining_definitions(file_tool):
    read_def = file_tool._generate_read_file_definition()
    path = lair.config.get("tools.file.path")
    assert read_def["function"]["name"] == "read_file"
    assert path in read_def["function"]["description"]

    delete_def = file_tool._generate_delete_file_definition()
    assert delete_def["function"]["name"] == "delete_file"
    assert path in delete_def["function"]["description"]

    make_def = file_tool._generate_make_directory_definition()
    assert make_def["function"]["name"] == "make_directory"
    assert path in make_def["function"]["description"]

    remove_def = file_tool._generate_remove_directory_definition()
    assert remove_def["function"]["name"] == "remove_directory"
    assert path in remove_def["function"]["description"]


def test_read_file_handles_open_errors(file_tool, monkeypatch):
    workspace = lair.config.get("tools.file.path")
    target = os.path.join(workspace, "fail.txt")
    with open(target, "w"):
        pass

    def explode(*_args, **_kwargs):
        raise OSError("cannot open")

    monkeypatch.setattr("builtins.open", explode)
    result = file_tool.read_file("fail.txt")
    assert "cannot open" in result["error"]
