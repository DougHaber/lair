import importlib
import os
import shutil
import sys
import time
import types

import prompt_toolkit
import pytest

import lair
from lair.components.history.chat_history import ChatHistory
from lair.logging import logger
from tests.unit.test_chat_interface_extended import (
    make_interface as extended_make_interface,
)


def import_commands():
    mod = types.ModuleType("lair.cli.chat_interface")
    mod.ChatInterface = object
    sys.modules["lair.cli.chat_interface"] = mod
    return importlib.import_module("lair.cli.chat_interface_commands")


class DummyReporting:
    def __init__(self):
        self.messages = []

    def system_message(self, message, **kwargs):
        self.messages.append(("system", message))

    def user_error(self, message):
        self.messages.append(("error", message))

    def print_rich(self, *args, **kwargs):
        pass

    def table_system(self, *args, **kwargs):
        pass


class DummyChatSession:
    def __init__(self):
        self.history = ChatHistory()
        self.session_title = "title"
        self.last_prompt = "prompt"
        self.last_response = "response"


def make_interface():
    commands = import_commands()

    class CI(commands.ChatInterfaceCommands):
        def __init__(self):
            self.chat_session = DummyChatSession()
            self.reporting = DummyReporting()
            self.session_manager = None

    return CI()


def test_command_clear():
    ci = make_interface()
    ci.chat_session.history.add_message("user", "hi")
    ci.command_clear("/clear", [], "")
    assert ci.chat_session.history.num_messages() == 0
    assert ci.chat_session.session_title is None
    assert ("system", "Conversation history cleared") in ci.reporting.messages


def test_command_debug_toggle():
    ci = make_interface()
    orig = logger.level
    ci.command_debug("/debug", [], "")
    first = logger.level
    ci.command_debug("/debug", [], "")
    second = logger.level
    assert first != orig
    assert second != first


def test_command_history_slice():
    ci = make_interface()
    for i in range(5):
        ci.chat_session.history.add_message("user", str(i))
    ci.command_history_slice("/history-slice", ["1:3"], "1:3")
    msgs = ci.chat_session.history.get_messages()
    assert [m["content"] for m in msgs] == ["1", "2"]
    assert any("History updated" in m[1] for m in ci.reporting.messages)


def setup_interface(monkeypatch):
    ci = extended_make_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
    return ci


def test_init_starting_session_alias_used(monkeypatch, caplog):
    ci = setup_interface(monkeypatch)
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
    ci._handle_session_switch()


def test_handle_session_set_alias_cancel(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: (_ for _ in ()).throw(EOFError()))
    ci._handle_session_set_alias()
    assert ci.chat_session.session_alias is None


def test_handle_session_set_title_cancel(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    ci._handle_session_set_title()
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


def test_flash_and_toolbar(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", True)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((10, 20)))
    monkeypatch.setattr(time, "time", lambda: 0)
    ci._flash("1234567890abc", duration=1)
    monkeypatch.setattr(time, "time", lambda: 0.5)
    bar = ci._generate_toolbar()
    assert bar.value == "<bottom-toolbar.flash>1234567890</bottom-toolbar.flash>"


def test_toolbar_disabled(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", False)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((5, 20)))
    bar = ci._generate_toolbar()
    assert "<bottom-toolbar.off>" in bar.value


def test_toolbar_error_disables(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", True)
    lair.config.active["chat.toolbar_template"] = "{missing}"
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((5, 20)))
    monkeypatch.setattr(time, "time", lambda: 10)
    bar = ci._generate_toolbar()
    assert bar == ""
    assert lair.config.get("chat.enable_toolbar") is False


def test_generate_toolbar_flags_and_prompt(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.active.update(
        {
            "chat.multiline_input": True,
            "style.render_markdown": False,
            "tools.enabled": True,
            "chat.verbose": False,
            "style.word_wrap": True,
            "chat.prompt_template": "{session_id}:{session_alias}:{model}:{mode}:{flags}",
        }
    )
    ci.chat_session.session_alias = "al"
    flags = ci._generate_toolbar_template_flags()
    assert flags == (
        "<flag.on>L</flag.on><flag.off>m</flag.off><flag.on>T</flag.on><flag.off>v</flag.off><flag.on>W</flag.on>"
    )
    prompt = ci._generate_prompt()
    assert f"{ci.chat_session.session_id}:al" in prompt.value


def test_get_default_switch_session_id(monkeypatch):
    ci = setup_interface(monkeypatch)
    first = ci.chat_session.session_id
    ci._new_chat_session()
    second = ci.chat_session.session_id
    assert second != first
    ci.last_used_session_id = first
    assert ci._get_default_switch_session_id() == first
    ci.last_used_session_id = 99
    assert ci._get_default_switch_session_id() == first


def test_handle_session_set_alias_and_title(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "alias")
    ci._handle_session_set_alias()
    assert ci.chat_session.session_alias == "alias"
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "alias")
    ci._handle_session_set_alias()
    assert ("error", "ERROR: That alias is unavailable") in ci.reporting.messages
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "123")
    ci._handle_session_set_alias()
    assert ("error", "ERROR: Aliases may not be integers") in ci.reporting.messages
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "title")
    ci._handle_session_set_title()
    assert ci.session_manager.sessions[ci.chat_session.session_id]["title"] == "title"


def test_handle_session_switch(monkeypatch):
    ci = setup_interface(monkeypatch)
    start = ci.chat_session.session_id
    ci._new_chat_session()
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "")
    ci._handle_session_switch()
    assert ci.chat_session.session_id == start
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "unknown")
    original = ci.session_manager.switch_to_session

    def fake_switch(id_or_alias, chat_session):
        if id_or_alias == "unknown":
            raise lair.sessions.UnknownSessionException("Unknown")
        return original(id_or_alias, chat_session)

    monkeypatch.setattr(ci.session_manager, "switch_to_session", fake_switch)
    ci._handle_session_switch()
    assert ("error", "ERROR: Unknown session: unknown") in ci.reporting.messages


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


def test_switch_to_session_success(monkeypatch):
    ci = setup_interface(monkeypatch)
    first = ci.chat_session.session_id
    ci._new_chat_session()
    second = ci.chat_session.session_id
    ci._switch_to_session(first)
    assert ci.chat_session.session_id == first
    assert ci.last_used_session_id == second


def test_switch_to_session_unknown(monkeypatch):
    ci = setup_interface(monkeypatch)
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
    ci = setup_interface(monkeypatch)
    called = []
    monkeypatch.setattr(ci, "_switch_to_session", lambda sid, raise_exceptions=False: called.append(int(sid)))
    kb = ci._get_keybindings()
    handler = next(b.handler for b in kb.bindings if b.keys[0].name.lower() == "f5")
    event = types.SimpleNamespace(key_sequence=[types.SimpleNamespace(key="f5")])
    handler(event)
    assert called == [5]


def test_get_embedded_response_strips_newline(monkeypatch):
    ci = setup_interface(monkeypatch)
    msg = "<answer>(value\n)</answer>"
    assert ci._get_embedded_response(msg, 0) == "value"
