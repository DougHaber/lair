import types
import sys
import re
from contextlib import contextmanager

import pytest

import importlib
import lair


def import_commands():
    mod = types.ModuleType("lair.cli.chat_interface")
    mod.ChatInterface = object
    sys.modules["lair.cli.chat_interface"] = mod
    return importlib.import_module("lair.cli.chat_interface_commands")


commands = import_commands()


class DummyReporting:
    def __init__(self):
        self.messages = []

    def system_message(self, message, **kwargs):
        self.messages.append(("system", message))

    def user_error(self, message):
        self.messages.append(("error", message))

    def llm_output(self, message):
        self.messages.append(("llm", message))

    def print_rich(self, message):
        self.messages.append(("rich", message))

    def print_highlighted_json(self, message):
        self.messages.append(("json", message))

    def style(self, text, style=None):
        return text


class SimpleHistory:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    def num_messages(self):
        return len(self.messages)

    def get_messages(self):
        return list(self.messages)

    def get_messages_as_jsonl_string(self):
        import json

        return "\n".join(json.dumps(m) for m in self.messages)

    def set_history(self, messages):
        self.messages = list(messages)

    def clear(self):
        self.messages = []


class DummyChatSession:
    def __init__(self):
        self.history = SimpleHistory()
        self.session_id = 1
        self.session_alias = None
        self.session_title = None
        self.last_prompt = None
        self.last_response = None
        self.saved = None
        self.loaded = None

    def save_to_file(self, filename):
        self.saved = filename

    def load_from_file(self, filename):
        self.loaded = filename

    def import_state(self, other):
        pass


class UnknownSessionException(Exception):
    pass


class DummySessionManager:
    def __init__(self):
        self.sessions = {1: {"alias": None, "title": None}}
        self.aliases = {}

    def get_session_id(self, id_or_alias, raise_exception=True):
        try:
            sid = int(id_or_alias)
            if sid in self.sessions:
                return sid
        except ValueError:
            if id_or_alias in self.aliases:
                return self.aliases[id_or_alias]
        if raise_exception:
            raise UnknownSessionException("Unknown")
        return None

    def is_alias_available(self, alias):
        if alias is None:
            return True
        try:
            int(alias)
            return False
        except ValueError:
            return alias not in self.aliases

    def set_alias(self, sid, new_alias):
        sid = self.get_session_id(sid)
        for a in list(self.aliases):
            if self.aliases[a] == sid:
                del self.aliases[a]
        if new_alias:
            self.aliases[new_alias] = sid
        self.sessions.setdefault(sid, {})["alias"] = new_alias

    def delete_sessions(self, items):
        for item in items:
            sid = self.get_session_id(item)
            self.sessions.pop(sid, None)
            for a in list(self.aliases):
                if self.aliases[a] == sid:
                    del self.aliases[a]

    def set_title(self, sid, title):
        sid = self.get_session_id(sid)
        self.sessions.setdefault(sid, {})["title"] = title


@contextmanager
def dummy_defer():
    yield


class DummyCI(commands.ChatInterfaceCommands):
    def __init__(self):
        self.chat_session = DummyChatSession()
        self.reporting = DummyReporting()
        self.session_manager = DummySessionManager()
        self.commands = {}

    def _rebuild_chat_session(self):
        pass

    # minimal stubs used in tests
    def print_modes_report(self):
        pass

    def print_current_model_report(self):
        pass

    def print_config_report(self, *a, **k):
        pass

    def _new_chat_session(self):
        self.chat_session = DummyChatSession()
        self.session_manager.sessions[self.chat_session.session_id] = {}

    def _switch_to_session(self, id_or_alias):
        self.chat_session.session_id = self.session_manager.get_session_id(id_or_alias)

    def _get_embedded_response(self, message, position):
        matches = re.findall(r"\((.*?)\)", message)
        if abs(position) > len(matches) - 1:
            return None
        return matches[position]


@pytest.fixture(autouse=True)
def patch_unknown(monkeypatch):
    dummy_mod = types.ModuleType("lair.sessions.session_manager")
    dummy_mod.UnknownSessionException = UnknownSessionException
    sys.modules["lair.sessions.session_manager"] = dummy_mod
    yield
    sys.modules.pop("lair.sessions.session_manager", None)


def make_ci():
    return DummyCI()


def test_register_command_duplicate():
    ci = make_ci()
    ci.register_command("/t", lambda *a: None, "d")
    assert "/t" in ci.commands
    with pytest.raises(Exception):
        ci.register_command("/t", lambda *a: None, "d")


def test_extract_variants(monkeypatch, caplog):
    ci = make_ci()
    ci.chat_session.last_response = "(foo)"
    # invalid position
    monkeypatch.setattr(lair.util, "safe_int", lambda x: x)
    with caplog.at_level("ERROR"):
        ci.command_extract("/extract", ["x"], "x")
    assert "Position must be an integer" in caplog.text
    caplog.clear()
    # save to file
    saved = {}
    monkeypatch.setattr(lair.util, "safe_int", int)
    monkeypatch.setattr(lair.util, "save_file", lambda f, c: saved.update({f: c}))
    ci.command_extract("/extract", ["0", "f"], "0 f")
    assert saved["f"].strip() == "foo"
    assert any("Section saved" in m[1] for m in ci.reporting.messages)
    caplog.clear()
    # no section
    with caplog.at_level("ERROR"):
        ci.command_extract("/extract", ["1"], "1")
    assert "No matching section" in caplog.text
    caplog.clear()
    # last_response missing
    ci.chat_session.last_response = None
    with caplog.at_level("ERROR"):
        ci.command_extract("/extract", [], "")
    assert "Last response is not set" in caplog.text


def test_history_edit_paths(monkeypatch, caplog):
    ci = make_ci()
    # editor cancelled
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *a, **k: None)
    ci.command_history_edit("/history-edit", [], "")
    assert ("error", "History was not modified.") in ci.reporting.messages
    ci.reporting.messages.clear()
    # decode error
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *a, **k: "bad")
    def bad_decode(_):
        raise ValueError("oops")
    monkeypatch.setattr(lair.util, "decode_jsonl", bad_decode)
    with caplog.at_level("ERROR"):
        ci.command_history_edit("/history-edit", [], "")
    assert "Failed to decode edited history JSONL" in caplog.text
    caplog.clear()
    # blank string
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *a, **k: "   ")
    monkeypatch.setattr(lair.util, "decode_jsonl", lambda s: [])
    ci.command_history_edit("/history-edit", [], "")
    assert any("History updated" in m[1] for m in ci.reporting.messages)


def test_last_prompt_and_response(monkeypatch, caplog):
    ci = make_ci()
    # no last prompt
    with caplog.at_level("WARNING"):
        ci.command_last_prompt("/last-prompt", [], "")
    assert "No last prompt found" in caplog.text
    caplog.clear()
    # save prompt
    ci.chat_session.last_prompt = "prompt"
    saved = {}
    monkeypatch.setattr(lair.util, "save_file", lambda f, c: saved.update({f: c}))
    ci.command_last_prompt("/last-prompt", ["p"], "p")
    assert saved["p"].strip() == "prompt"
    caplog.clear()
    # last response none
    with caplog.at_level("WARNING"):
        ci.command_last_response("/last-response", [], "")
    assert "No last response found" in caplog.text
    caplog.clear()
    # save response
    ci.chat_session.last_response = "resp"
    monkeypatch.setattr(lair.util, "save_file", lambda f, c: saved.update({f: c}))
    ci.command_last_response("/last-response", ["r"], "r")
    assert saved["r"].strip() == "resp"


def test_list_settings_help(monkeypatch):
    ci = make_ci()
    monkeypatch.setattr(commands, "ErrorRaisingArgumentParser", commands.ErrorRaisingArgumentParser)
    monkeypatch.setattr(commands, "ArgumentParserHelpException", commands.ArgumentParserHelpException)
    monkeypatch.setattr(commands, "ArgumentParserExitException", commands.ArgumentParserExitException)
    result = []
    monkeypatch.setattr(ci.reporting, "system_message", lambda m, **k: result.append(m))
    ci.command_list_settings("/list-settings", [], "--help")
    assert result and "usage" in result[0]

def test_load_alias_conflict(monkeypatch):
    ci = make_ci()
    ci.chat_session.session_alias = "a"
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda alias: False)
    monkeypatch.setattr(ci.chat_session, "load_from_file", lambda f: None)
    monkeypatch.setattr(lair.events, "defer_events", lambda: dummy_defer())
    ci.command_load("/load", ["file"], "file")
    assert ci.chat_session.session_alias is None
    assert any("Session loaded" in m[1] for m in ci.reporting.messages)


def test_messages(monkeypatch, caplog):
    ci = make_ci()
    # no messages
    with caplog.at_level("WARNING"):
        ci.command_messages("/messages", [], "")
    assert "No messages found" in caplog.text
    caplog.clear()
    ci.chat_session.history.add_message("user", "hi")
    saved = {}
    monkeypatch.setattr(lair.util, "save_file", lambda f, c: saved.update({f: c}))
    ci.command_messages("/messages", ["out"], "out")
    assert "out" in saved
    ci.reporting.messages.clear()
    caplog.clear()
    ci.command_messages("/messages", [], "")
    assert any(m[0] == "json" for m in ci.reporting.messages)


def test_mode_and_model(monkeypatch):
    ci = make_ci()
    called = []
    monkeypatch.setattr(ci, "print_modes_report", lambda: called.append("m"))
    ci.command_mode("/mode", [], "")
    assert called == ["m"]
    called.clear()
    monkeypatch.setattr(lair.config, "change_mode", lambda x: called.append(x))
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda t: DummyChatSession())
    ci.command_mode("/mode", ["openai"], "openai")
    assert "openai" in called
    out = []
    monkeypatch.setattr(ci, "print_current_model_report", lambda: out.append("p"))
    ci.command_model("/model", [], "")
    assert out == ["p"]
    monkeypatch.setattr(lair.config, "set", lambda k, v: out.append((k, v)))
    ci.command_model("/model", ["m"], "m")
    assert ("model.name", "m") in out


def test_prompt_and_session_alias(monkeypatch):
    ci = make_ci()
    monkeypatch.setattr(lair.config, "set", lambda k, v: ci.reporting.system_message(k + v))
    ci.command_prompt("/prompt", ["hello"], "hello")
    assert any("session.system_prompt_templatehello" in m[1] for m in ci.reporting.messages)
    ci.reporting.messages.clear()
    monkeypatch.setattr(ci.session_manager, "is_alias_available", lambda a: False)
    monkeypatch.setattr(lair.util, "safe_int", int)
    ci.command_session_alias("/session-alias", ["1", "2"], "1 2")
    assert ("error", "ERROR: Aliases may not be integers") in ci.reporting.messages
    ci.reporting.messages.clear()
    monkeypatch.setattr(lair.util, "safe_int", lambda x: x)
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

