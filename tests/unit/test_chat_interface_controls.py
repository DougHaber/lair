import types
import os
import shutil
import time
import pytest
import lair
import prompt_toolkit
from tests.helpers.chat_interface import make_interface


def setup_interface(monkeypatch):
    ci = make_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
    ci.reporting.error = lambda msg: ci.reporting.messages.append(("error", msg))
    return ci


def test_enter_key_on_selected_completion(monkeypatch):
    ci = setup_interface(monkeypatch)

    class Buffer:
        def __init__(self):
            self.text = ""
            self.cancelled = False
        def insert_text(self, txt):
            self.text += txt
        def cancel_completion(self):
            self.cancelled = True
    buffer = Buffer()
    event = types.SimpleNamespace(app=types.SimpleNamespace(current_buffer=buffer))
    ci._enter_key_on_selected_completion(event)
    assert buffer.text == " " and buffer.cancelled


def test_toggle_actions(monkeypatch):
    ci = setup_interface(monkeypatch)
    messages = []
    monkeypatch.setattr(ci, "_prompt_handler_system_message", lambda m: messages.append(m))

    monkeypatch.setattr(lair.util, "is_debug_enabled", lambda: True)
    ci.toggle_debug(None)
    assert messages.pop() == "Debugging disabled"
    monkeypatch.setattr(lair.util, "is_debug_enabled", lambda: False)
    ci.toggle_debug(None)
    assert messages.pop() == "Debugging enabled"

    lair.config.set("chat.enable_toolbar", True)
    ci.toggle_toolbar(None)
    assert lair.config.get("chat.enable_toolbar") is False

    lair.config.set("chat.multiline_input", False)
    ci.toggle_multiline_input(None)
    assert lair.config.get("chat.multiline_input") is True

    lair.config.set("style.render_markdown", True)
    ci.toggle_markdown(None)
    assert lair.config.get("style.render_markdown") is False

    lair.config.set("tools.enabled", True)
    ci.toggle_tools(None)
    assert lair.config.get("tools.enabled") is False

    lair.config.set("chat.verbose", False)
    ci.toggle_verbose(None)
    assert lair.config.get("chat.verbose") is True

    lair.config.set("style.word_wrap", False)
    ci.toggle_word_wrap(None)
    assert lair.config.get("style.word_wrap") is True


def test_switch_to_session_unknown(monkeypatch):
    ci = setup_interface(monkeypatch)
    def raise_unknown(id_or_alias, chat_session):
        raise lair.sessions.UnknownSessionException("bad")
    monkeypatch.setattr(ci.session_manager, "switch_to_session", raise_unknown)
    captured = []
    monkeypatch.setattr(lair.logging.logger, "error", lambda msg: captured.append(msg))
    ci._switch_to_session("bad", raise_exceptions=False)
    assert any("Unknown session" in m for m in captured)


def test_start_interrupt_and_exit(monkeypatch):
    ci = setup_interface(monkeypatch)
    seq = [KeyboardInterrupt, EOFError]
    def fake_prompt():
        exc = seq.pop(0)
        raise exc()
    monkeypatch.setattr(ci, "_prompt", fake_prompt)
    with pytest.raises(SystemExit):
        ci.start()
    assert ("error", "Interrupt received") in ci.reporting.messages


def test_generate_toolbar_standard(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", True)
    lair.config.active["chat.toolbar_template"] = "<bottom-toolbar.text>{mode}</bottom-toolbar.text>"
    monkeypatch.setattr(time, "time", lambda: 10)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((5, 20)))
    bar = ci._generate_toolbar()
    assert "<bottom-toolbar.text>" in bar.value
