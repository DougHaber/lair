import types
import contextlib
import pytest
import lair
import prompt_toolkit
from tests.test_chat_interface_extended import make_interface


def setup_ci(monkeypatch):
    ci = make_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
    return ci


def test_switch_to_session_success(monkeypatch):
    ci = setup_ci(monkeypatch)
    first = ci.chat_session.session_id
    ci._new_chat_session()
    second = ci.chat_session.session_id
    ci._switch_to_session(first)
    assert ci.chat_session.session_id == first
    assert ci.last_used_session_id == second


def test_switch_to_session_unknown(monkeypatch):
    ci = setup_ci(monkeypatch)
    monkeypatch.setattr(
        ci.session_manager,
        "switch_to_session",
        lambda *a, **k: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("bad")),
    )
    captured = []
    monkeypatch.setattr(lair.logging.logger, "error", lambda m: captured.append(m))
    ci._switch_to_session("unknown", raise_exceptions=False)
    assert captured and "Unknown session: unknown" in captured[0]
    with pytest.raises(lair.sessions.UnknownSessionException):
        ci._switch_to_session("unknown", raise_exceptions=True)


def test_f_key_binding(monkeypatch):
    ci = setup_ci(monkeypatch)
    called = []
    monkeypatch.setattr(ci, "_switch_to_session", lambda sid, raise_exceptions=False: called.append(int(sid)))
    kb = ci._get_keybindings()
    handler = next(b.handler for b in kb.bindings if b.keys[0].name.lower() == "f5")
    event = types.SimpleNamespace(key_sequence=[types.SimpleNamespace(key="f5")])
    handler(event)
    assert called == [5]


def test_get_embedded_response_strips_newline(monkeypatch):
    ci = setup_ci(monkeypatch)
    msg = "<answer>(value\n)</answer>"
    assert ci._get_embedded_response(msg, 0) == "value"

