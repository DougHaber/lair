import types

import prompt_toolkit
import pytest

import lair
from tests.helpers.chat_interface import make_interface


def setup_interface(monkeypatch):
    ci = make_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
    ci.reporting.error = lambda msg: ci.reporting.messages.append(("error", msg))
    return ci


def test_init_starting_session_create(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(
        ci, "_switch_to_session", lambda *a, **k: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("u"))
    )
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: True)
    ci.chat_session.session_alias = None
    ci._init_starting_session("newalias", create_session_if_missing=True)
    assert ci.chat_session.session_alias == "newalias"
    assert ci.session_manager.aliases["newalias"] == ci.chat_session.session_id


def test_init_starting_session_integer_error(monkeypatch, caplog):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(
        ci, "_switch_to_session", lambda *a, **k: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("u"))
    )
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: False)
    monkeypatch.setattr(lair.util, "safe_int", int)
    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        ci._init_starting_session("123", create_session_if_missing=True)
    assert "Session aliases may not be integers" in caplog.text


def test_get_shortcut_details(monkeypatch):
    ci = setup_interface(monkeypatch)
    details = ci._get_shortcut_details()
    assert details["F1 - F12"] == "Switch to session 1-12"
    assert details["ESC-d"] == "Toggle debugging output"
    assert details["C-x C-h"] == "Show the full chat history"


def test_handle_request_command(monkeypatch):
    ci = setup_interface(monkeypatch)
    called = []
    ci.commands = {"/do": {"callback": lambda c, a, s: called.append((c, a, s))}}
    assert ci._handle_request_command("/do arg1 arg2") is True
    assert called and called[0][0] == "/do"
    assert ci._handle_request_command("/unknown") is False


def test_handle_request_chat_with_attachments(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(
        lair.util,
        "get_attachments_content",
        lambda files: ([{"type": "text", "text": "att"}], [{"role": "user", "content": "converted"}]),
    )
    history_before = ci.chat_session.history.num_messages()
    assert ci._handle_request_chat("hi <<file.txt>>") is True
    assert ci.chat_session.history.num_messages() > history_before


def test_get_embedded_response(monkeypatch):
    ci = setup_interface(monkeypatch)
    msg = "<answer>(section)</answer> ```py\ncode\n```"
    assert ci._get_embedded_response(msg, 0) == "section"
    assert ci._get_embedded_response(msg, -1) == "code"
    assert ci._get_embedded_response(msg, 5) is None


def test_prompt_invokes_handle_request(monkeypatch):
    ci = setup_interface(monkeypatch)
    ci.prompt_session = types.SimpleNamespace(prompt=lambda *a, **k: " hi ")
    monkeypatch.setattr(prompt_toolkit.styles.Style, "from_dict", lambda d: None)
    called = []
    monkeypatch.setattr(ci, "_handle_request", lambda r: called.append(r) or True)
    monkeypatch.setattr(ci.session_manager, "refresh_from_chat_session", lambda s: called.append("refresh"))
    ci._prompt()
    assert called[0] == "hi"
    assert "refresh" in called


def test_init_starting_session_alias_conflict(monkeypatch, caplog):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(
        ci,
        "_switch_to_session",
        lambda *a, **k: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("u")),
    )
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: False)
    monkeypatch.setattr(lair.util, "safe_int", lambda v: None)
    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        ci._init_starting_session("dup", create_session_if_missing=True)
    assert "Alias is already used" in caplog.text


def test_init_starting_session_unknown_exit(monkeypatch, caplog):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(
        ci,
        "_switch_to_session",
        lambda *a, **k: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("u")),
    )
    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        ci._init_starting_session("missing", create_session_if_missing=False)
    assert "Unknown session: missing" in caplog.text


def test_get_embedded_response_empty_section(monkeypatch):
    ci = setup_interface(monkeypatch)
    msg = "<answer>()</answer>"
    assert ci._get_embedded_response(msg, 0) is None


def test_handle_request_command_error(monkeypatch):
    ci = setup_interface(monkeypatch)

    def bad(c, a, s):
        raise ValueError("boom")

    ci.commands = {"/bad": {"callback": bad}}
    captured = []
    monkeypatch.setattr(ci.reporting, "error", lambda m: captured.append(m))
    assert ci._handle_request_command("/bad arg") is False
    assert any("Command failed" in m for m in captured)


def test_handle_request_empty_and_error(monkeypatch):
    ci = setup_interface(monkeypatch)
    assert ci._handle_request("") is False
    monkeypatch.setattr(ci, "_handle_request_chat", lambda r: (_ for _ in ()).throw(RuntimeError("fail")))
    captured = []
    monkeypatch.setattr(ci.reporting, "error", lambda m: captured.append(m))
    assert ci._handle_request("hi") is False
    assert any("Chat failed" in m for m in captured)


def test_handle_request_chat_attachment_only(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.attachments_enabled", True)
    lair.config.set("chat.attachment_syntax_regex", r"<<(.*?)>>")
    monkeypatch.setattr(
        lair.util,
        "get_attachments_content",
        lambda files: ([{"type": "text", "text": "file"}], [{"role": "user", "content": "c"}]),
    )
    before = ci.chat_session.history.num_messages()
    assert ci._handle_request_chat("<<f.txt>>") is True
    assert ci.chat_session.history.num_messages() > before
