import datetime

import rich
import rich.text

import lair
from lair.reporting.reporting import Reporting


def make_reporting(monkeypatch):
    rep = Reporting(disable_color=True)
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: None)
    monkeypatch.setattr(rep.console, "print", lambda *a, **k: None)
    return rep


def test_filter_and_format(monkeypatch):
    rep = make_reporting(monkeypatch)
    rows = [{"a": 1, "b": 2}, {"a": 3, "c": 4}]
    assert rep.filter_keys_dict_list(rows, {"a"}) == [{"a": 1}, {"a": 3}]
    assert rep.filter_keys_dict_list(None, {"a"}) == []
    assert rep.format_value(None) == ""
    dt = datetime.datetime(2020, 1, 2, 3, 4, 5)
    assert rep.format_value(dt) == "01/02/20 03:04:05"
    assert rep.format_value(5) == "5"
    assert rep.format_value("x") == "x"


def test_table_and_format_cell(monkeypatch):
    rep = make_reporting(monkeypatch)
    out = []
    monkeypatch.setattr(rep, "print_rich", lambda obj, **kw: out.append(obj))
    rep.table([[1, 2], [3, 4]], column_names=["a", "b"], column_formatters={"a": lambda v: f"n{v}"})
    assert out and isinstance(out[0], rich.table.Table)
    assert out[0].row_count == 2


def test_format_json(monkeypatch):
    rep = make_reporting(monkeypatch)
    text = rep.format_json('{"a":1}', enable_highlighting=False)
    assert isinstance(text, rich.text.Text)
    short = rep.format_json('{"a":1}', max_length=2)
    assert short.plain.endswith("...")


def test_assistant_tool_calls_tool_message(monkeypatch):
    rep = make_reporting(monkeypatch)
    printed = []
    monkeypatch.setattr(rep.console, "print", lambda *a, **k: printed.append(a[0]))
    tool_call = {"function": {"name": "f", "arguments": "{}"}, "id": "1"}
    rep.assistant_tool_calls({"tool_calls": [tool_call]}, show_heading=True)
    message = {"tool_call_id": "1", "content": "{}"}
    rep.tool_message(message, show_heading=True)
    assert printed


def test_format_content_list_and_messages(monkeypatch):
    rep = make_reporting(monkeypatch)
    content = [
        {"type": "text", "text": "hi"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}},
    ]
    msg = rep.format_content_list(content)
    assert "text: hi" in msg and "image: image/png" in msg
    calls = []
    monkeypatch.setattr(rep, "system_message", lambda m, show_heading=False: calls.append(("sys", m)))
    monkeypatch.setattr(rep, "llm_output", lambda m, show_heading=False: calls.append(("llm", m)))
    monkeypatch.setattr(rep, "assistant_tool_calls", lambda m, show_heading=False: calls.append(("tool", m)))
    monkeypatch.setattr(rep, "tool_message", lambda m, show_heading=False: calls.append(("toolmsg", m)))
    tc = {"function": {"name": "f", "arguments": "{}"}, "id": "1"}
    rep.message({"role": "system", "content": "hi"})
    rep.message({"role": "assistant", "content": "ans"})
    rep.message({"role": "assistant", "content": "ans", "tool_calls": [tc]})
    rep.message({"role": "tool", "content": "{}", "tool_call_id": "1"})
    rep.message({"role": "other", "content": "x"})
    assert [c[0] for c in calls] == ["sys", "llm", "tool", "toolmsg", "sys"]


def test_misc_helpers(monkeypatch):
    rep = make_reporting(monkeypatch)
    lines = rep.messages_to_str([{"role": "a", "content": "b"}])
    assert "A: b" in lines
    style = rep.get_style_by_range(50, minimum=0, maximum=100, styles=["a", "b"], inverse=True)
    assert style in {"a", "b"}
    assert rep.color_gt_lt(1, center=0) == "green"
    assert rep.color_gt_lt(-1, center=0) == "red"
    assert rep.color_gt_lt(0, center=0) == "gray"
    assert isinstance(rep.color_bool(True), rich.text.Text)
    assert isinstance(rep.color_bool(False), rich.text.Text)


def test_reporting_init_and_highlight(monkeypatch):
    monkeypatch.setattr(lair.config, "get", lambda k: k == "style.messages_command.syntax_highlight")
    json_called = []
    monkeypatch.setattr(rich, "print_json", lambda *a, **k: json_called.append("json"))
    monkeypatch.setattr(rich, "print", lambda *a, **k: json_called.append("plain"))
    rep = Reporting(force_color=True)
    assert rep.console.no_color is False
    rep.print_highlighted_json("{}")
    assert json_called == ["json"]
    monkeypatch.setattr(lair.config, "get", lambda k: False)
    json_called.clear()
    rep.print_highlighted_json("{}")
    assert json_called == ["plain"]


def test_reporting_table_system(monkeypatch):
    rep = make_reporting(monkeypatch)
    recorded = []
    monkeypatch.setattr(rep, "table", lambda *a, **kw: recorded.append(kw.get("style")))
    monkeypatch.setattr(lair.config, "get", lambda k: "sys" if k == "style.system_message" else False)
    rep.table_from_dicts_system([{"a": 1}])
    rep.table_system([[1]])
    assert recorded == ["sys", "sys"]


def test_reporting_system_error(monkeypatch):
    rep = Reporting(disable_color=True)
    outputs = []
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: outputs.append(a[0]))
    monkeypatch.setattr(rep, "exception", lambda: outputs.append("exc"))
    monkeypatch.setattr(
        lair.config,
        "get",
        lambda k: {
            "style.render_rich_tracebacks": False,
            "style.error": "ERR",
            "style.user_error": "USR",
            "style.system_message": "SM",
            "style.system_message_heading": "HEAD",
            "style.render_markdown": False,
        }.get(k, False),
    )
    rep.error("boom", show_exception=True)
    rep.system_message("hello", show_heading=True, disable_markdown=True)
    assert "exc" in outputs and any("ERROR: boom" in str(o) for o in outputs)
    assert any("hello" in str(o) for o in outputs)
