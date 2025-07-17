import types
import pytest
import prompt_toolkit
import lair
import logging
from lair.logging import logger
from tests.test_chat_interface_extended import make_interface


def setup_interface(monkeypatch):
    ci = make_interface(monkeypatch)
    # run callbacks immediately
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
    return ci


def test_init_starting_session_alias_used(monkeypatch, caplog):
    ci = setup_interface(monkeypatch)
    # patch alias availability to False to trigger error path
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: False)
    monkeypatch.setattr(
        ci,
        "_switch_to_session",
        lambda *a, **k: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("x")),
    )
    with caplog.at_level("ERROR"), pytest.raises(SystemExit):
        ci._init_starting_session("alias", create_session_if_missing=True)
    assert "Alias is already used" in caplog.text


def test_enter_key_on_selected_completion(monkeypatch):
    ci = setup_interface(monkeypatch)

    class DummyBuffer:
        def __init__(self):
            self.text = ""
            self.cancelled = False

        def insert_text(self, txt):
            self.text += txt

        def cancel_completion(self):
            self.cancelled = True

    buffer = DummyBuffer()
    event = types.SimpleNamespace(app=types.SimpleNamespace(current_buffer=buffer))
    ci._enter_key_on_selected_completion(event)
    assert buffer.text == " "
    assert buffer.cancelled is True


def test_toggle_functions(monkeypatch):
    ci = setup_interface(monkeypatch)
    messages = []
    monkeypatch.setattr(ci, "_prompt_handler_system_message", lambda m: messages.append(m))

    start = logger.level
    ci.toggle_debug(None)
    first = logger.level
    ci.toggle_debug(None)
    second = logger.level
    debug_msgs = messages[:2]
    assert first != start
    assert second != first
    assert all("Debugging" in msg for msg in debug_msgs)

    orig_toolbar = lair.config.get("chat.enable_toolbar")
    ci.toggle_toolbar(None)
    assert lair.config.get("chat.enable_toolbar") != orig_toolbar
    ci.toggle_toolbar(None)
    assert lair.config.get("chat.enable_toolbar") == orig_toolbar

    orig_multi = lair.config.get("chat.multiline_input")
    ci.toggle_multiline_input(None)
    assert lair.config.get("chat.multiline_input") != orig_multi
    ci.toggle_multiline_input(None)
    assert lair.config.get("chat.multiline_input") == orig_multi

    orig_md = lair.config.get("style.render_markdown")
    ci.toggle_markdown(None)
    assert lair.config.get("style.render_markdown") != orig_md
    ci.toggle_markdown(None)
    assert lair.config.get("style.render_markdown") == orig_md

    orig_tools = lair.config.get("tools.enabled")
    ci.toggle_tools(None)
    assert lair.config.get("tools.enabled") != orig_tools
    ci.toggle_tools(None)
    assert lair.config.get("tools.enabled") == orig_tools

    orig_verbose = lair.config.get("chat.verbose")
    ci.toggle_verbose(None)
    assert lair.config.get("chat.verbose") != orig_verbose
    ci.toggle_verbose(None)
    assert lair.config.get("chat.verbose") == orig_verbose

    orig_wrap = lair.config.get("style.word_wrap")
    ci.toggle_word_wrap(None)
    assert lair.config.get("style.word_wrap") != orig_wrap
    ci.toggle_word_wrap(None)
    assert lair.config.get("style.word_wrap") == orig_wrap


def test_handle_session_switch_keyboard_interrupt(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    # ensure no exception propagates
    ci._handle_session_switch()


def test_handle_session_set_alias_cancel(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: (_ for _ in ()).throw(EOFError()))
    # should simply return without changes
    ci._handle_session_set_alias()
    assert ci.chat_session.session_alias is None


def test_handle_session_set_title_cancel(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    ci._handle_session_set_title()
    # title should remain None
    assert ci.session_manager.sessions[ci.chat_session.session_id].get("title") is None


def test_handle_request_command_error(monkeypatch):
    ci = setup_interface(monkeypatch)
    called = []
    ci.commands = {"/fail": {"callback": lambda *a: (_ for _ in ()).throw(ValueError("boom"))}}
    monkeypatch.setattr(ci.reporting, "error", lambda m: called.append(m), raising=False)
    assert ci._handle_request_command("/fail arg") is False
    assert called and "Command failed" in called[0]


def test_handle_request_error(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(ci, "_handle_request_chat", lambda r: (_ for _ in ()).throw(RuntimeError("bad")))
    messages = []
    monkeypatch.setattr(ci.reporting, "error", lambda m: messages.append(m), raising=False)
    assert ci._handle_request("hi") is False
    assert "Chat failed" in messages[0]


def test_start_loop(monkeypatch):
    ci = setup_interface(monkeypatch)
    calls = [KeyboardInterrupt(), EOFError()]

    def fake_prompt():
        raise calls.pop(0)

    monkeypatch.setattr(ci, "_prompt", fake_prompt)
    errors = []
    monkeypatch.setattr(ci.reporting, "error", lambda m: errors.append(m), raising=False)
    with pytest.raises(SystemExit):
        ci.start()
    assert "Interrupt received" in errors[0]
