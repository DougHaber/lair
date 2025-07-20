# ruff: noqa: E402
import sys
import types

import pdfplumber  # noqa: F401,E402

import lair
from lair.cli.chat_interface_reports import ChatInterfaceReports
from lair.logging import logger

sys.modules.pop("pdfplumber", None)


class DummyReporting:
    def __init__(self):
        self.messages = []
        self.tables = []

    def system_message(self, message, **kwargs):
        self.messages.append(("system", message))

    def message(self, message, **kwargs):
        self.messages.append(("message", message))

    def table_system(self, rows, **kwargs):
        self.tables.append(("table", rows))

    def table_from_dicts_system(self, rows, **kwargs):
        self.tables.append(("dict", rows))

    def style(self, text, style=None):
        return f"{style}:{text}" if style else text

    def color_bool(self, value, true_str="yes", false_str="-", false_style="dim"):
        return true_str if value else f"{false_style}:{false_str}"


class DummyChatSession:
    def __init__(self, *, messages=None, models=None, tools=None, session_id=1):
        self.session_id = session_id
        self.history = types.SimpleNamespace(get_messages=lambda: list(messages or []))
        self._models = list(models or [])
        self.tool_set = types.SimpleNamespace(get_all_tools=lambda: list(tools or []))

    def list_models(self):
        return list(self._models)


class DummySessionManager:
    def __init__(self, sessions=None):
        self._sessions = list(sessions or [])

    def all_sessions(self):
        return list(self._sessions)


def make_ci(*, messages=None, models=None, tools=None, sessions=None):
    ci = ChatInterfaceReports()
    ci.reporting = DummyReporting()
    ci.commands = {"/cmd": {"description": "desc"}}
    ci._get_shortcut_details = lambda: {"S": "shortcut"}
    ci.chat_session = DummyChatSession(messages=messages, models=models, tools=tools)
    ci.session_manager = DummySessionManager(sessions=sessions)
    return ci


def test_print_config_report_unknown_baseline(monkeypatch):
    ci = make_ci()
    captured = []
    monkeypatch.setattr(logger, "error", lambda msg: captured.append(msg))
    ci.print_config_report(baseline="unknown")
    assert captured == ["Unknown mode: unknown"]
    assert ci.reporting.messages == []


def test_print_config_report_differences(monkeypatch):
    ci = make_ci()
    old_model = lair.config.get("model.name")
    lair.config.set("model.name", "new-model", no_event=True)
    try:
        ci.print_config_report(show_only_differences=True, filter_regex=r"^model\.name$")
    finally:
        lair.config.set("model.name", old_model, no_event=True)
    assert (
        "table",
        [["model.name", f"{lair.config.get('chat.set_command.modified_style')}:new-model"]],
    ) in ci.reporting.tables


def test_print_history_limits():
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    ci = make_ci(messages=msgs)
    ci.print_history(num_messages=1)
    assert ci.reporting.messages == [("message", msgs[1])]
    ci2 = make_ci(messages=[])
    ci2.print_history()
    assert ci2.reporting.messages == []


def test_models_and_modes_and_tools_reports():
    ci = make_ci(models=[{"id": "b"}, {"id": "a"}], tools=[{"class_name": "A", "name": "t", "enabled": True}])
    ci.print_models_report(update_cache=True)
    assert ci._models == [{"id": "a"}, {"id": "b"}]
    ci.print_modes_report()
    ci.print_tools_report()
    # three tables: models, modes, tools
    assert len(ci.reporting.tables) == 3


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
    # expect two tables from help and one from current model
    assert len(ci.reporting.tables) == 3


def test_iter_config_rows_unmodified():
    ci = make_ci()
    rows = list(ci._iter_config_rows(False, r"^model\.name$", None))
    expected = ["model.name", f"{lair.config.get("chat.set_command.modified_style")}:" + lair.config.get("model.name")]
    assert rows[0] == expected


def test_print_config_report_baseline_no_keys():
    ci = make_ci()
    ci.print_config_report(filter_regex=r"^nomatch$", baseline="openai")
    assert ("system", f"Current mode: {lair.config.active_mode}, Baseline mode: openai") in ci.reporting.messages
    assert ci.reporting.messages[-1] == ("system", "No matching keys")


def test_iter_config_rows_unmodified_style():
    ci = make_ci()
    key = "chat.enable_toolbar"
    rows = list(ci._iter_config_rows(False, fr"^{key}$", None))
    expected = [key, f"{lair.config.get('chat.set_command.unmodified_style')}:" + str(lair.config.get(key))]
    assert rows == [expected]

    # When show_only_differences is True the row is omitted
    assert list(ci._iter_config_rows(True, fr"^{key}$", None)) == []
