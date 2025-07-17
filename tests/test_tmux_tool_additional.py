import os

import pytest

import lair
from lair.components.tools.tmux_tool import TmuxTool
from tests.test_tmux_tool import DummySession, DummyWindow, restore_config, setup_config


class DummyToolSet:
    def __init__(self):
        self.added = []

    def add_tool(self, **kwargs):
        self.added.append(kwargs)


@pytest.fixture
def basic_tool(tmp_path):
    old = setup_config(tmp_path)
    tool = TmuxTool()
    tool._ensure_connection = lambda: None
    tool.session = DummySession()
    yield tool
    restore_config(old)


def test_add_to_tool_set_registers(basic_tool):
    ts = DummyToolSet()
    basic_tool.add_to_tool_set(ts)
    names = [item["name"] for item in ts.added]
    assert names == [
        "run",
        "send_keys",
        "capture_output",
        "read_new_output",
        "attach_window",
        "kill",
        "list_windows",
    ]
    # Ensure the definition handler returns proper structure
    run_def = ts.added[0]["definition_handler"]()
    assert run_def["function"]["name"] == "run"


def test_get_log_file_name_creates_dirs(tmp_path, basic_tool):
    nested = tmp_path / "a" / "b"
    lair.config.set(
        "tools.tmux.capture_file_name",
        os.path.join(str(nested), "cap-{window_id}.log"),
        no_event=True,
    )
    window = DummyWindow(1)
    file_name = basic_tool.get_log_file_name_and_create_directories(window)
    assert os.path.isdir(nested)
    assert file_name.endswith("cap-@1.log")


def test_read_new_output_no_windows(basic_tool):
    with pytest.raises(Exception, match="No active tmux windows"):
        basic_tool.read_new_output()


def test_generate_definitions(basic_tool):
    assert basic_tool._generate_capture_output_definition()["function"]["name"] == "capture_output"
    assert basic_tool._generate_read_new_output_definition()["function"]["name"] == "read_new_output"
    assert basic_tool._generate_kill_definition()["function"]["name"] == "kill"
    assert basic_tool._generate_list_windows_definition()["function"]["name"] == "list_windows"
    assert basic_tool._generate_attach_window_definition()["function"]["name"] == "attach_window"
