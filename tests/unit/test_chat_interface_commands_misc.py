from __future__ import annotations

import importlib
import re
import sys
import types
from contextlib import contextmanager

import pytest

import lair

from tests.helpers import ChatSessionDouble, RecordingReporting, SessionManagerDouble


def import_commands():
    module = types.ModuleType("lair.cli.chat_interface")
    module.ChatInterface = object
    sys.modules["lair.cli.chat_interface"] = module
    return importlib.import_module("lair.cli.chat_interface_commands")


commands = import_commands()


class UnknownSessionError(Exception):
    """Exception raised when a session id or alias cannot be resolved."""


class _TestingSessionManager(SessionManagerDouble):
    """Session manager that mirrors production behaviour but raises test-specific errors."""

    def get_session_id(self, id_or_alias, raise_exception=True):  # type: ignore[override]
        result = super().get_session_id(id_or_alias, raise_exception=False)
        if result is None:
            if raise_exception:
                raise UnknownSessionError("Unknown")
            return None
        return result


class DummyCI(commands.ChatInterfaceCommands):
    """Concrete ``ChatInterfaceCommands`` wired to in-memory doubles."""

    def __init__(self):
        self.chat_session = ChatSessionDouble()
        self.reporting = RecordingReporting()
        self.session_manager = _TestingSessionManager()
        self.commands: dict[str, dict[str, object]] = {}
        self.session_manager.add_from_chat_session(self.chat_session)

    def _rebuild_chat_session(self):
        return None

    def print_modes_report(self):
        return None

    def print_current_model_report(self):
        return None

    def print_config_report(self, *args, **kwargs):
        return None

    def _new_chat_session(self):
        self.chat_session = ChatSessionDouble()
        self.session_manager.add_from_chat_session(self.chat_session)

    def _switch_to_session(self, id_or_alias):
        session_id = self.session_manager.get_session_id(id_or_alias)
        self.chat_session.session_id = session_id

    def _get_embedded_response(self, message, position):
        matches = re.findall(r"\((.*?)\)", message)
        if abs(position) > len(matches) - 1:
            return None
        return matches[position]


@contextmanager
def dummy_defer():
    yield


@pytest.fixture(autouse=True)
def patch_unknown(monkeypatch):
    dummy_module = types.ModuleType("lair.sessions.session_manager")
    dummy_module.UnknownSessionException = UnknownSessionError
    sys.modules["lair.sessions.session_manager"] = dummy_module
    yield
    sys.modules.pop("lair.sessions.session_manager", None)


def make_ci():
    return DummyCI()


def test_register_command_duplicate():
    ci = make_ci()
    ci.register_command("/t", lambda *a: None, "d")
    assert "/t" in ci.commands
    with pytest.raises(Exception) as exc_info:
        ci.register_command("/t", lambda *a: None, "d")
    assert "Already registered" in str(exc_info.value)


def test_extract_variants(monkeypatch, caplog):
    ci = make_ci()
    ci.chat_session.last_response = "(foo)"
    monkeypatch.setattr(lair.util, "safe_int", lambda x: x)
    with caplog.at_level("ERROR"):
        ci.command_extract("/extract", ["x"], "x")
    assert "Position must be an integer" in caplog.text

    caplog.clear()
    saved = {}
    monkeypatch.setattr(lair.util, "safe_int", int)
    monkeypatch.setattr(lair.util, "save_file", lambda filename, content: saved.update({filename: content}))
    ci.command_extract("/extract", ["0", "f"], "0 f")
    assert saved["f"].strip() == "foo"
    assert any("Section saved" in message for _, message in ci.reporting.messages)

    caplog.clear()
    with caplog.at_level("ERROR"):
        ci.command_extract("/extract", ["1"], "1")
    assert "No matching section" in caplog.text

    caplog.clear()
    ci.chat_session.last_response = None
    with caplog.at_level("ERROR"):
        ci.command_extract("/extract", [], "")
    assert "Last response is not set" in caplog.text


def test_history_edit_paths(monkeypatch, caplog):
    ci = make_ci()
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *args, **kwargs: None)
    ci.command_history_edit("/history-edit", [], "")
    assert ("error", "History was not modified.") in ci.reporting.messages

    ci.reporting.messages.clear()
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *args, **kwargs: "bad")

    def bad_decode(_) -> list[dict[str, object]]:
        raise ValueError("oops")

    monkeypatch.setattr(lair.util, "decode_jsonl", bad_decode)
    with caplog.at_level("ERROR"):
        ci.command_history_edit("/history-edit", [], "")
    assert "Failed to decode edited history JSONL" in caplog.text

    caplog.clear()
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *args, **kwargs: "   ")
    monkeypatch.setattr(lair.util, "decode_jsonl", lambda _: [])
    ci.command_history_edit("/history-edit", [], "")
    assert any("History updated" in message for _, message in ci.reporting.messages)


def test_last_prompt_and_response(monkeypatch, caplog):
    ci = make_ci()
    with caplog.at_level("WARNING"):
        ci.command_last_prompt("/last-prompt", [], "")
    assert "No last prompt found" in caplog.text

    caplog.clear()
    ci.chat_session.last_prompt = "prompt"
    saved = {}
    monkeypatch.setattr(lair.util, "save_file", lambda filename, content: saved.update({filename: content}))
    ci.command_last_prompt("/last-prompt", ["p"], "p")
    assert saved["p"].strip() == "prompt"

    caplog.clear()
    with caplog.at_level("WARNING"):
        ci.command_last_response("/last-response", [], "")
    assert "No last response found" in caplog.text

    caplog.clear()
    ci.chat_session.last_response = "resp"
    monkeypatch.setattr(lair.util, "save_file", lambda filename, content: saved.update({filename: content}))
    ci.command_last_response("/last-response", ["r"], "r")
    assert saved["r"].strip() == "resp"


def test_list_settings_help(monkeypatch):
    ci = make_ci()
    monkeypatch.setattr(commands, "ErrorRaisingArgumentParser", commands.ErrorRaisingArgumentParser)
    monkeypatch.setattr(commands, "ArgumentParserHelpException", commands.ArgumentParserHelpException)
    monkeypatch.setattr(commands, "ArgumentParserExitException", commands.ArgumentParserExitException)

    result: list[str] = []
    monkeypatch.setattr(ci.reporting, "system_message", lambda message, **kwargs: result.append(message))
    ci.command_list_settings("/list-settings", [], "--help")
    assert result and "usage" in result[0]


def test_load_alias_conflict(monkeypatch):
    ci = make_ci()
    ci.chat_session.session_alias = "a"
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: False)
    monkeypatch.setattr(ci.chat_session, "load_from_file", lambda _: None)
    monkeypatch.setattr(lair.events, "defer_events", lambda: dummy_defer())
    ci.command_load("/load", ["file"], "file")
    assert ci.chat_session.session_alias is None
    assert any("Session loaded" in message for _, message in ci.reporting.messages)


def test_messages(monkeypatch, caplog):
    ci = make_ci()
    with caplog.at_level("WARNING"):
        ci.command_messages("/messages", [], "")
    assert "No messages found" in caplog.text

    caplog.clear()
    ci.chat_session.history.add_message("user", "hi")
    saved = {}
    monkeypatch.setattr(lair.util, "save_file", lambda filename, content: saved.update({filename: content}))
    ci.command_messages("/messages", ["out"], "out")
    assert "out" in saved

    ci.reporting.messages.clear()
    caplog.clear()
    ci.command_messages("/messages", [], "")
    assert any(kind == "json" for kind, _ in ci.reporting.messages)


def test_mode_and_model(monkeypatch):
    ci = make_ci()
    called: list[str | tuple[str, str]] = []
    monkeypatch.setattr(ci, "print_modes_report", lambda: called.append("m"))
    ci.command_mode("/mode", [], "")
    assert called == ["m"]

    called.clear()
    monkeypatch.setattr(lair.config, "change_mode", lambda mode: called.append(mode))
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda target: ChatSessionDouble())
    ci.command_mode("/mode", ["openai"], "openai")
    assert "openai" in called

    output: list[object] = []
    monkeypatch.setattr(ci, "print_current_model_report", lambda: output.append("p"))
    ci.command_model("/model", [], "")
    assert output == ["p"]

    monkeypatch.setattr(lair.config, "set", lambda key, value: output.append((key, value)))
    ci.command_model("/model", ["m"], "m")
    assert ("model.name", "m") in output


def test_prompt_and_session_alias(monkeypatch):
    ci = make_ci()
    monkeypatch.setattr(lair.config, "set", lambda key, value: ci.reporting.system_message(key + value))
    ci.command_prompt("/prompt", ["hello"], "hello")
    assert any("session.system_prompt_templatehello" in message for _, message in ci.reporting.messages)

    ci.reporting.messages.clear()
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: False)
    monkeypatch.setattr(lair.util, "safe_int", int)
    ci.command_session_alias("/session-alias", ["1", "2"], "1 2")
    assert ("error", "ERROR: Aliases may not be integers") in ci.reporting.messages

    ci.reporting.messages.clear()
    monkeypatch.setattr(lair.util, "safe_int", lambda value: value)
    ci.command_session_alias("/session-alias", ["1", "dup"], "1 dup")
    assert ("error", "ERROR: That alias is unavailable") in ci.reporting.messages


def test_set_unknown(monkeypatch):
    ci = make_ci()
    monkeypatch.setattr(ci, "print_config_report", lambda: ci.reporting.system_message("config"))
    ci.command_set("/set", [], "")
    assert ("system", "config") in ci.reporting.messages

    ci.reporting.messages.clear()
    ci.command_set("/set", ["bad"], "bad")
    assert ("error", "ERROR: Unknown key: bad") in ci.reporting.messages
