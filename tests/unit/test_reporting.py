import builtins
import datetime
import traceback

import rich
import rich.text

import lair
from lair.reporting.reporting import Reporting


def patch_config(monkeypatch, values):
    monkeypatch.setattr(
        lair.config,
        "get",
        lambda key, allow_not_found=False, default=None: values.get(key, default),
    )


class DummyConsole:
    def __init__(self, width=20):
        self.width = width
        self.printed = []

    def print(self, *args, **kwargs):
        self.printed.append((args, kwargs))


def test_print_highlighted_json(monkeypatch):
    values = {"style.messages_command.syntax_highlight": True}
    patch_config(monkeypatch, values)
    r = Reporting()
    called = []
    monkeypatch.setattr(rich, "print_json", lambda text, indent=None: called.append(text))
    r.print_highlighted_json('{"a":1}')
    assert called == ['{"a":1}']

    values["style.messages_command.syntax_highlight"] = False
    captured = []
    monkeypatch.setattr(r.console, "print", lambda text, **_: captured.append(text))
    r.print_highlighted_json('{"a":2}')
    assert captured == ['{"a":2}']


def test_filter_keys_dict_list():
    r = Reporting()
    rows = [{"a": 1, "b": 2}, {"b": 3, "c": 4}]
    result = r.filter_keys_dict_list(rows, {"a", "b"})
    assert result == [{"a": 1, "b": 2}, {"b": 3}]
    assert r.filter_keys_dict_list(None, {"a"}) == []


def test_table_from_dicts(monkeypatch):
    r = Reporting()
    captured = {}

    def fake_table(rows, *, column_names=None, column_formatters=None, style=None, markup=False):
        captured.update(
            {
                "rows": rows,
                "column_names": column_names,
                "style": style,
                "markup": markup,
            }
        )

    monkeypatch.setattr(r, "table", fake_table)
    rows = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    r.table_from_dicts(rows, style="s", markup=True)
    assert captured["rows"] == [[1, 2], [3, 4]]
    assert captured["column_names"] == ["x", "y"]
    assert captured["style"] == "s"
    assert captured["markup"] is True


def test_format_value():
    r = Reporting()
    dt = datetime.datetime(2024, 1, 2, 3, 4, 5)
    assert r.format_value(None) == ""
    assert r.format_value(dt) == "01/02/24 03:04:05"
    assert r.format_value(5) == "5"
    assert r.format_value("x") == "x"


def test__format_cell(monkeypatch):
    r = Reporting()
    formatters = {"b": lambda v: f"F{v}"}
    # formatter used when markup=False and column formatter exists
    cell = r._format_cell(1, 1, ["a", "b"], formatters, True)
    assert cell == "F1"
    # markup disabled returns styled value
    styled = r._format_cell(2, 0, ["a"], None, False)
    assert isinstance(styled, rich.text.Text)
    assert str(styled) == "2"
    # markup=True returns value directly
    assert r._format_cell("x", 0, None, None, True) == "x"


def test_table(monkeypatch):
    console = DummyConsole(width=10)
    r = Reporting()
    r.console = console
    rows = [[1, 2], [3, 4]]
    r.table(rows, column_names=["a", "b"], markup=False)
    # first print call should be a Table object
    assert console.printed and isinstance(console.printed[0][0][0], rich.table.Table)
    table = console.printed[0][0][0]
    assert [str(c.header) for c in table.columns] == ["a", "b"]


def test_exception_and_error(monkeypatch):
    console = DummyConsole()
    r = Reporting()
    r.console = console
    called = []
    monkeypatch.setattr(r, "print_rich", lambda *a, **k: called.append(a[0]))
    monkeypatch.setattr(traceback, "print_exception", lambda *a: called.append("tb"))
    values = {"style.render_rich_tracebacks": False, "style.error": "err"}
    patch_config(monkeypatch, values)
    r.exception()
    assert called[-1] == "tb"
    monkeypatch.setattr(lair.util, "is_debug_enabled", lambda: True)
    r.error("boom")
    assert any("ERROR: boom" in str(c) for c in called)


def test_format_json_truncate(monkeypatch):
    r = Reporting()
    r.json_highlighter = lambda s: rich.text.Text(s)
    txt = r.format_json("123456", max_length=3)
    assert str(txt) == "123..."


def test_assistant_tool_calls(monkeypatch):
    console = DummyConsole(width=20)
    r = Reporting()
    r.console = console
    values = {
        "style.llm_output.tool_call.background": "",
        "style.llm_output_heading": "",
        "style.llm_output.tool_call.bullet": "",
        "style.llm_output.tool_call.prefix": "",
        "style.llm_output.tool_call.function": "",
        "style.llm_output.tool_call.max_arguments_length": None,
        "style.llm_output.tool_call.arguments": "",
        "style.llm_output.tool_call.arguments_syntax_highlighting": False,
        "style.llm_output.tool_call.id": "",
    }
    patch_config(monkeypatch, values)
    msg = {"tool_calls": [{"id": "id1", "function": {"name": "t", "arguments": "{}"}}]}
    r.assistant_tool_calls(msg, show_heading=True)
    assert any("AI" in args[0] for args, _ in console.printed)
    assert len(console.printed) == 3


def test_tool_message(monkeypatch):
    console = DummyConsole(width=20)
    r = Reporting()
    r.console = console
    values = {
        "style.tool_message.background": "",
        "style.tool_message.heading": "",
        "style.tool_message.bullet": "",
        "style.tool_message.id": "",
        "style.tool_message.arrow": "",
        "style.tool_message.max_response_length": None,
        "style.tool_message.response": "",
        "style.tool_message.response_syntax_highlighting": False,
    }
    patch_config(monkeypatch, values)
    msg = {"tool_call_id": "cid", "content": "{}"}
    r.tool_message(msg, show_heading=True)
    assert any("TOOL" in args[0] for args, _ in console.printed)
    assert len(console.printed) == 3


def test_system_message(monkeypatch):
    console = DummyConsole()
    r = Reporting()
    r.console = console
    values = {"style.system_message_heading": "head", "style.system_message": "sys", "style.render_markdown": False}
    patch_config(monkeypatch, values)
    r.system_message("hi", show_heading=True)
    assert console.printed[0][0][0] == "SYSTEM"
    assert isinstance(console.printed[1][0][0], rich.text.Text)


def test_llm_output(monkeypatch):
    console = DummyConsole()
    r = Reporting()
    r.console = console
    values = {
        "style.render_markdown": True,
        "style.llm_output_heading": "",
        "style.llm_output": "",
        "style.thoughts.enabled": False,
    }
    patch_config(monkeypatch, values)
    r.llm_output("hi", show_heading=True)
    assert any(args[0] == "AI" for args, _ in console.printed)


def test_format_content_list_and_message(monkeypatch):
    console = DummyConsole()
    r = Reporting()
    r.console = console
    values = {"style.human_output_heading": "h", "style.human_output": "hu", "style.render_markdown": False}
    patch_config(monkeypatch, values)
    content = [
        {"type": "text", "text": "hello"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abcd"}},
    ]
    formatted = r.format_content_list(content)
    assert "image/png" in formatted
    msg = {"role": "user", "content": "hi"}
    r.message(msg)
    assert any("HUMAN" in args[0] for args, _ in console.printed)


def test_messages_to_str_and_colors():
    r = Reporting()
    msgs = [{"role": "a", "content": "b"}]
    assert r.messages_to_str(msgs) == "A: b"
    assert r.get_style_by_range(5, maximum=10)  # returns a color string
    assert r.get_style_by_range(5, maximum=10, log=True, inverse=True)
    assert r.color_gt_lt(1, center=0) == "green"
    assert r.color_gt_lt(-1, center=0) == "red"
    assert r.color_gt_lt(0, center=0) == "gray"
    assert isinstance(r.color_bool(True), rich.text.Text)
    assert isinstance(r.color_bool(False), rich.text.Text)
import pytest
import rich
import rich.traceback

from lair.reporting.reporting import Reporting, ReportingSingletoneMeta


def reset_reporting():
    ReportingSingletoneMeta._instances.pop(Reporting, None)


def test_init_options(monkeypatch):
    calls = []

    def fake_console(**kwargs):
        calls.append(kwargs)
        return DummyConsole()

    monkeypatch.setattr(ReportingSingletoneMeta, "_instances", {})
    monkeypatch.setattr(rich.console, "Console", fake_console)
    Reporting(disable_color=True)
    assert calls[0]["no_color"] is True and calls[0]["force_terminal"] is None

    reset_reporting()
    monkeypatch.setattr(rich.console, "Console", fake_console)
    Reporting(force_color=True)
    assert calls[1]["no_color"] is False and calls[1]["force_terminal"] is True


def test_table_from_dicts_branches(monkeypatch):
    reset_reporting()
    r = Reporting()
    captured = []
    monkeypatch.setattr(r, "table", lambda *a, **k: captured.append(k))

    r.table_from_dicts(None)
    r.table_from_dicts([])
    assert not captured

    rows = [{"a": 1}]
    r.table_from_dicts(rows, column_names=[], automatic_column_names=False)
    assert captured[0]["column_names"] == []

    captured.clear()
    r.table_from_dicts(rows, column_names=["a"], style="s")
    assert captured[0]["column_names"] == ["a"]
    assert captured[0]["style"] == "s"


def test_table_none(monkeypatch):
    reset_reporting()
    r = Reporting()
    printed = []
    monkeypatch.setattr(r, "print_rich", lambda *a, **k: printed.append(a))
    r.table(None)
    assert not printed


def test_table_system_wrappers(monkeypatch):
    reset_reporting()
    r = Reporting()
    patch_config(monkeypatch, {"style.system_message": "sys"})
    captured = {}

    monkeypatch.setattr(r, "table_from_dicts", lambda *a, **kw: captured.update(kw))
    r.table_from_dicts_system([{"x": 1}])
    assert captured["style"] == "sys"

    monkeypatch.setattr(r, "table", lambda *a, **kw: captured.update(kw))
    r.table_system([[1]])
    assert captured["style"] == "sys"


def test_exception_rich(monkeypatch):
    reset_reporting()
    r = Reporting()
    patch_config(monkeypatch, {"style.render_rich_tracebacks": True})
    captured = []
    monkeypatch.setattr(r, "print_rich", lambda obj, **k: captured.append(obj))
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        r.exception()
    assert any(isinstance(c, rich.traceback.Traceback) for c in captured)


def test_user_error(monkeypatch):
    reset_reporting()
    r = Reporting()
    patch_config(monkeypatch, {"style.user_error": "err"})
    captured = []
    monkeypatch.setattr(r, "print_rich", lambda *a, **k: captured.append(k.get("style")))
    r.user_error("boom")
    assert captured == ["err"]


def test_system_message_markdown(monkeypatch):
    reset_reporting()
    r = Reporting()
    patch_config(
        monkeypatch,
        {
            "style.render_markdown": True,
            "style.system_message": "s",
            "style.system_message_heading": "h",
        },
    )
    r.console = DummyConsole()
    r.system_message("hi", show_heading=True)
    assert r.console.printed[0][0][0] == "SYSTEM"
    assert isinstance(r.console.printed[1][0][0], rich.markdown.Markdown)


def test_llm_output_thoughts(monkeypatch):
    reset_reporting()
    r = Reporting()
    printed = []
    patch_config(
        monkeypatch,
        {
            "style.render_markdown": True,
            "style.thoughts.enabled": True,
            "style.thoughts.hide_thoughts": False,
            "style.thoughts.hide_tags": True,
            "style.llm_output_thought": "",
            "style.llm_output": "",
        },
    )
    monkeypatch.setattr(r, "print_rich", lambda obj, **k: printed.append(obj))
    r.llm_output("before <thought>idea</thought> after")
    assert isinstance(printed[1], rich.markdown.Markdown)


def test_llm_output_plain(monkeypatch):
    reset_reporting()
    r = Reporting()
    captured = []
    patch_config(monkeypatch, {"style.render_markdown": False, "style.llm_output": "s"})
    monkeypatch.setattr(r, "print_rich", lambda obj, **k: captured.append((str(obj), k.get("style"))))
    r.llm_output("hi")
    assert captured[0] == ("hi", "s")


def test_format_content_list_error():
    reset_reporting()
    r = Reporting()
    with pytest.raises(ValueError):
        r.format_content_list([{"type": "unknown"}])


def test_message_assistant_tool(monkeypatch):
    reset_reporting()
    r = Reporting()
    r.console = DummyConsole()
    patch_config(
        monkeypatch,
        {
            "style.human_output_heading": "h",
            "style.human_output": "hu",
            "style.llm_output_heading": "",
            "style.llm_output": "",
            "style.render_markdown": True,
            "style.tool_message.background": "",
            "style.tool_message.heading": "",
            "style.tool_message.bullet": "",
            "style.tool_message.id": "",
            "style.tool_message.arrow": "",
            "style.tool_message.max_response_length": None,
            "style.tool_message.response": "",
            "style.tool_message.response_syntax_highlighting": False,
            "style.llm_output.tool_call.background": "",
            "style.llm_output.tool_call.bullet": "",
            "style.llm_output.tool_call.prefix": "",
            "style.llm_output.tool_call.function": "",
            "style.llm_output.tool_call.max_arguments_length": None,
            "style.llm_output.tool_call.arguments": "",
            "style.llm_output.tool_call.arguments_syntax_highlighting": False,
            "style.llm_output.tool_call.id": "",
        },
    )
    msg = {
        "role": "assistant",
        "tool_calls": [{"id": "id1", "function": {"name": "t", "arguments": "{}"}}],
        "content": "",
    }
    r.message(msg)
    assert any("TOOL CALL" in str(args[0]) for args, _ in r.console.printed)
