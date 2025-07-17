import pytest
import types
import lair
import prompt_toolkit
from tests.helpers.chat_interface import make_interface


def setup_interface(monkeypatch):
    ci = make_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
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
