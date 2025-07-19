import datetime
import pytest
import rich.text

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
