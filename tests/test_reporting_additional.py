import pytest
import rich
import rich.traceback

from lair.reporting.reporting import Reporting, ReportingSingletoneMeta
from tests.test_reporting import DummyConsole, patch_config


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
