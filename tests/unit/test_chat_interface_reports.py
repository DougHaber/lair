from __future__ import annotations

# ruff: noqa: E402
import sys
import types

import pdfplumber  # noqa: F401,E402

import lair
from lair.cli.chat_interface_reports import ChatInterfaceReports
from lair.logging import logger

from tests.helpers import ChatSessionDouble, RecordingReporting, SessionManagerDouble

sys.modules.pop("pdfplumber", None)


def make_ci(*, messages=None, models=None, tools=None, sessions=None):
    ci = ChatInterfaceReports()
    ci.reporting = RecordingReporting()
    ci.commands = {"/cmd": {"description": "desc"}}
    ci._get_shortcut_details = lambda: {"S": "shortcut"}

    tool_set = types.SimpleNamespace(
        get_all_tools=lambda load_manifest=False: [dict(tool) for tool in tools or []]
    )

    ci.chat_session = ChatSessionDouble(
        tool_set=tool_set,
        models=models or [{"id": "model-a"}, {"id": "model-b"}],
        messages=messages,
    )

    manager = SessionManagerDouble()
    if sessions:
        for snapshot in sessions:
            manager.sessions[snapshot["id"]] = dict(snapshot)
            alias = snapshot.get("alias")
            if alias:
                manager.aliases[alias] = snapshot["id"]
    ci.session_manager = manager
    return ci


def test_print_config_report_unknown_baseline(monkeypatch):
    ci = make_ci()
    captured: list[str] = []
    monkeypatch.setattr(logger, "error", lambda message: captured.append(message))
    ci.print_config_report(baseline="unknown")
    assert captured == ["Unknown mode: unknown"]
    assert ci.reporting.messages == []


def test_print_config_report_differences(monkeypatch):
    ci = make_ci()
    original_model = lair.config.get("model.name")
    lair.config.set("model.name", "new-model", no_event=True)
    try:
        ci.print_config_report(show_only_differences=True, filter_regex=r"^model\.name$")
    finally:
        lair.config.set("model.name", original_model, no_event=True)
    expected = [
        ["model.name", f"{lair.config.get('chat.set_command.modified_style')}:new-model"],
    ]
    assert ("table", expected) in ci.reporting.tables


def test_print_history_limits():
    history_messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
    ]
    ci = make_ci(messages=history_messages)
    ci.print_history(num_messages=1)
    assert ci.reporting.messages == [("message", history_messages[1])]

    ci_empty = make_ci(messages=[])
    ci_empty.print_history()
    assert ci_empty.reporting.messages == []


def test_models_and_modes_and_tools_reports():
    ci = make_ci(models=[{"id": "b"}, {"id": "a"}], tools=[{"class_name": "A", "name": "t", "enabled": True}])
    ci.print_models_report(update_cache=True)
    assert ci._models == [{"id": "a"}, {"id": "b"}]
    ci.print_modes_report()
    ci.print_tools_report()
    assert len(ci.reporting.tables) == 3


def test_print_mcp_tools_report():
    tools = [
        {"class_name": "MCPTool", "name": "a", "enabled": True, "source": "s"},
        {"class_name": "FileTool", "name": "b", "enabled": False},
    ]
    ci = make_ci(tools=tools)
    ci.print_mcp_tools_report()
    assert ci.reporting.tables
    assert ci.reporting.tables[0][1][0]["name"] == "a"


def test_print_tools_report_includes_mcp():
    ci = make_ci()
    ci.print_tools_report()
    assert any(row["class_name"] == "MCP" for row in ci.reporting.tables[0][1])


def test_print_sessions_report():
    sessions = [
        {"id": 1, "alias": "a", "title": "t1", "session": {"mode": "m1", "model_name": "m"}, "history": [1]},
        {"id": 2, "alias": "b", "title": "t2", "session": {"mode": "m2", "model_name": "m"}, "history": []},
    ]
    ci = make_ci(sessions=sessions)
    ci.print_sessions_report()
    assert ci.reporting.tables and ci.reporting.tables[0][0] == "dict"

    ci_empty = make_ci(sessions=[])
    ci_empty.print_sessions_report()
    assert ci_empty.reporting.messages == [("system", "No sessions found.")]


def test_print_help_and_current_model():
    ci = make_ci()
    ci.print_help()
    ci.print_current_model_report()
    assert len(ci.reporting.tables) == 3


def test_iter_config_rows_unmodified():
    ci = make_ci()
    rows = list(ci._iter_config_rows(False, r"^model\.name$", None))
    expected_value = f"{lair.config.get('chat.set_command.modified_style')}:" + lair.config.get("model.name")
    assert rows[0] == ["model.name", expected_value]


def test_print_config_report_baseline_no_keys():
    ci = make_ci()
    ci.print_config_report(filter_regex=r"^nomatch$", baseline="openai")
    assert ("system", f"Current mode: {lair.config.active_mode}, Baseline mode: openai") in ci.reporting.messages
    assert ci.reporting.messages[-1] == ("system", "No matching keys")


def test_iter_config_rows_unmodified_style():
    ci = make_ci()
    key = "chat.enable_toolbar"
    rows = list(ci._iter_config_rows(False, rf"^{key}$", None))
    expected = f"{lair.config.get('chat.set_command.unmodified_style')}:" + str(lair.config.get(key))
    assert rows == [[key, expected]]
    assert list(ci._iter_config_rows(True, rf"^{key}$", None)) == []
