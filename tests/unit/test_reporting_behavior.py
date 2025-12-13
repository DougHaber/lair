import traceback

import pytest
import rich
import rich.markdown
import rich.text

import lair
from lair.reporting.reporting import Reporting, ReportingSingletoneMeta


# Helper similar to one in test_reporting_utils
def make_reporting(monkeypatch):
    ReportingSingletoneMeta._instances.clear()
    rep = Reporting(disable_color=True)
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: None)
    monkeypatch.setattr(rep.console, "print", lambda *a, **k: None)
    return rep


def test_init_options(monkeypatch):
    ReportingSingletoneMeta._instances.clear()
    rep = Reporting(disable_color=True)
    assert rep.console.no_color is True
    ReportingSingletoneMeta._instances.clear()
    rep = Reporting(force_color=True)
    assert rep.console.no_color is False
    assert rep.console._force_terminal is True
    ReportingSingletoneMeta._instances.clear()


def test_table_helpers(monkeypatch):
    rep = make_reporting(monkeypatch)
    called = []
    monkeypatch.setattr(rep, "table", lambda *a, **kw: called.append(kw.get("column_names")))
    rep.table_from_dicts([], column_names=["a"])
    assert not called
    rep.table_from_dicts([{"a": 1}], column_names=("a",))
    assert called == [["a"]]
    printed = []
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: printed.append(True))
    rep.table(None)
    assert not printed


def test_format_cell_markup(monkeypatch):
    rep = make_reporting(monkeypatch)
    result = rep._format_cell("x", 0, None, None, markup=True)
    assert result == "x"


def test_exception_branches(monkeypatch):
    rep = make_reporting(monkeypatch)
    tb_called = []
    monkeypatch.setattr(rich.traceback, "Traceback", lambda: "TB")
    monkeypatch.setattr(rep, "print_rich", lambda arg=None, **k: tb_called.append(arg))
    monkeypatch.setattr(lair.config, "get", lambda k: k == "style.render_rich_tracebacks")
    rep.exception()
    assert tb_called == ["TB"]
    tb_called.clear()
    monkeypatch.setattr(lair.config, "get", lambda k: False)
    monkeypatch.setattr(traceback, "print_exception", lambda *a: tb_called.append("plain"))
    rep.exception()
    assert tb_called == ["plain"]


def test_assistant_tool_calls_and_tool_message(monkeypatch):
    rep = make_reporting(monkeypatch)
    printed = []
    monkeypatch.setattr(rep.console, "print", lambda *a, **k: printed.append(a[0]))
    monkeypatch.setattr(lair.config, "get", lambda k: False)
    tool_call = {"function": {"name": "f", "arguments": "{}"}, "id": "1"}
    rep.assistant_tool_calls({"tool_calls": [tool_call]})
    message = {"tool_call_id": "1", "content": "{}"}
    rep.tool_message(message)
    assert printed


def test_user_and_system_messages(monkeypatch):
    rep = make_reporting(monkeypatch)
    out = []
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: out.append((a, k)))
    monkeypatch.setattr(lair.config, "get", lambda k: k == "style.render_markdown")
    rep.user_error("oops")
    rep.system_message("sys", disable_markdown=False, show_heading=True)
    assert any("oops" in str(a[0]) for a, _ in out)
    assert any(isinstance(a[0], rich.markdown.Markdown) for a, _ in out)


def test_llm_output_thoughts(monkeypatch):
    rep = make_reporting(monkeypatch)
    calls = []
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: calls.append(a[0]))

    def cfg(key):
        return {
            "style.thoughts.hide_thoughts": True,
            "style.thoughts.hide_tags": False,
            "style.llm_output_thought": "th",
            "style.llm_output": "out",
        }.get(key, False)

    monkeypatch.setattr(lair.config, "get", cfg)
    rep._llm_output__with_thoughts("begin <thought>secret</thought> end")
    assert len(calls) == 2  # thought hidden
    calls.clear()

    def cfg2(key):
        return {
            "style.thoughts.hide_thoughts": False,
            "style.thoughts.hide_tags": True,
            "style.llm_output_thought": "th",
            "style.llm_output": "out",
        }.get(key, False)

    monkeypatch.setattr(lair.config, "get", cfg2)
    rep._llm_output__with_thoughts("begin <thought>secret</thought> end")
    assert any(getattr(c, "markup", "") == "secret" for c in calls)
    calls.clear()

    def cfg3(key):
        return {
            "style.thoughts.hide_thoughts": False,
            "style.thoughts.hide_tags": False,
            "style.llm_output_thought": "th",
            "style.llm_output": "out",
        }.get(key, False)

    monkeypatch.setattr(lair.config, "get", cfg3)
    rep._llm_output__with_thoughts("begin <thought>secret</thought> end")
    assert any("<thought>" in getattr(c, "markup", "") for c in calls)


def test_llm_output(monkeypatch):
    rep = make_reporting(monkeypatch)
    msgs = []
    monkeypatch.setattr(rep, "_llm_output__with_thoughts", lambda m: msgs.append("t"))
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: msgs.append(a[0]))

    def cfg(key):
        return {
            "style.render_markdown": False,
            "style.llm_output": "out",
            "style.thoughts.enabled": False,
            "style.llm_output_heading": "h",
        }.get(key, False)

    monkeypatch.setattr(lair.config, "get", cfg)
    rep.llm_output("hi", show_heading=True)
    assert any(isinstance(m, rich.text.Text) for m in msgs)
    msgs.clear()

    def cfg2(key):
        return {
            "style.render_markdown": True,
            "style.thoughts.enabled": True,
            "style.llm_output_heading": "h",
        }.get(key, False)

    monkeypatch.setattr(lair.config, "get", cfg2)
    rep.llm_output("hi")
    assert "t" in msgs


def test_format_content_list_error(monkeypatch):
    rep = make_reporting(monkeypatch)
    with pytest.raises(ValueError):
        rep.format_content_list([{"type": "bad"}])


def test_message_user(monkeypatch):
    rep = make_reporting(monkeypatch)
    output = []
    monkeypatch.setattr(rep, "print_rich", lambda *a, **k: output.append(a[0]))
    monkeypatch.setattr(lair.config, "get", lambda k: False)
    rep.message({"role": "user", "content": "hello"})
    assert any("HUMAN" in str(o) for o in output)


def test_get_style_by_range_defaults(monkeypatch):
    rep = make_reporting(monkeypatch)
    style = rep.get_style_by_range(50)
    assert style.startswith("rgb(")
    style_log = rep.get_style_by_range(50, log=True)
    assert style_log.startswith("rgb(")
