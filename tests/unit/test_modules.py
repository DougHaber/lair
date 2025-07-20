import argparse
import sys
from types import SimpleNamespace

import pytest

import lair
from lair.modules import chat as chat_mod
from lair.modules import util as util_mod
from lair.modules.util import logger


class DummyChatSession:
    def __init__(self):
        self.called = False
        self.session_alias = None
        self.session_title = None

    def chat(self, messages):
        self.called = True
        return "ok"


class DummyParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(prog="test", add_help=False)
        self.added = []

    def add_argument(self, *a, **kw):
        self.added.append((a, kw))
        return super().add_argument(*a, **kw)


def test_chat_module_run(monkeypatch):
    called = {}

    class DummyCI:
        def __init__(self, **kwargs):
            called["init"] = kwargs

        def start(self):
            called["start"] = True

    monkeypatch.setattr(lair.cli, "ChatInterface", DummyCI)
    parser = DummyParser()
    module = chat_mod.Chat(parser)
    args = argparse.Namespace(session="1", allow_create_session=True)
    module.run(args)
    assert called["init"]["starting_session_id_or_alias"] == "1"
    assert called["init"]["create_session_if_missing"]
    assert called["start"]


def test_chat_module_info():
    info = chat_mod._module_info()
    assert info["class"] is chat_mod.Chat and "cli" in info["tags"]


def make_util(parser=None):
    if parser is None:
        parser = DummyParser()
    return util_mod.Util(parser)


def test_util_get_instructions(tmp_path):
    file = tmp_path / "inst.txt"
    file.write_text("abc")
    util = make_util()
    args = argparse.Namespace(instructions_file=str(file), instructions=None)
    assert util._get_instructions(args) == "abc"
    args = argparse.Namespace(instructions=None, instructions_file=None)
    with pytest.raises(SystemExit):
        util._get_instructions(args)


def test_util_get_user_messages(monkeypatch, tmp_path):
    util = make_util()
    txt = tmp_path / "c.txt"
    txt.write_text("data")
    args = argparse.Namespace(pipe=False, content_file=str(txt), content=None, attachments=None)
    msgs = util._get_user_messages(args)
    assert any("data" in m["content"] for m in msgs if isinstance(m, dict))

    def fake_attach(files):
        return [], [lair.util.get_message("user", "x")]

    monkeypatch.setattr(lair.util, "get_attachments_content", fake_attach)
    args = argparse.Namespace(pipe=False, content=None, content_file=None, attachments=["a"])
    msgs = util._get_user_messages(args)
    assert {"role": "user", "content": "x"} in msgs


def test_call_llm_and_clean(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    result = util.call_llm(chat_session=chat, instructions="i", user_messages=[], enable_tools=False)
    assert result == "ok" and chat.called
    cleaned = util.clean_response("```txt\nhello\n```")
    assert cleaned == "hello\n"


class DummySessionManager:
    def __init__(self, *, alias_available=True):
        self.alias_available = alias_available
        self.add_called = False

    def switch_to_session(self, alias, chat_session):
        raise lair.sessions.UnknownSessionException("missing")

    def is_alias_available(self, alias):
        return self.alias_available

    def add_from_chat_session(self, chat_session):
        self.add_called = True


def make_args(**overrides):
    base = {
        "session": None,
        "allow_create_session": False,
        "read_only_session": False,
        "instructions": None,
        "instructions_file": None,
        "pipe": False,
        "content": None,
        "content_file": None,
        "attachments": None,
        "enable_tools": False,
        "markdown": False,
        "include_filenames": None,
        "model": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_init_session_manager_no_session(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: DummySessionManager())
    result = util._init_session_manager(chat, make_args())
    assert result is None and chat.session_title == "N/A"


def test_init_session_manager_alias_unavailable(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    manager = DummySessionManager(alias_available=False)
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: manager)
    monkeypatch.setattr(lair.util, "safe_int", lambda v: int(v) if v.isdigit() else v)
    errors = []
    monkeypatch.setattr(logger, "error", lambda msg: errors.append(msg))
    with pytest.raises(SystemExit):
        util._init_session_manager(chat, make_args(session="1", allow_create_session=True))
    assert any("may not be integers" in e for e in errors)


def test_init_session_manager_success(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    manager = DummySessionManager()
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: manager)
    manager.switch_to_session = lambda alias, cs: (_ for _ in ()).throw(
        lair.sessions.UnknownSessionException("missing")
    )
    monkeypatch.setattr(lair.util, "safe_int", lambda v: v)
    result = util._init_session_manager(chat, make_args(session="new", allow_create_session=True))
    assert result is manager and chat.session_alias == "new" and manager.add_called


def test_util_run_stdout(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda session_type: chat)
    monkeypatch.setattr(util, "_init_session_manager", lambda cs, args: None)
    orig_get = lair.config.get
    monkeypatch.setattr(lair.config, "get", lambda k: "tmpl" if k == "util.system_prompt_template" else orig_get(k))
    monkeypatch.setattr(util, "_get_instructions", lambda a: "i")
    monkeypatch.setattr(util, "_get_user_messages", lambda a: [])
    monkeypatch.setattr(util, "call_llm", lambda *a, **k: "resp")
    monkeypatch.setattr(util, "clean_response", lambda r: r)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    written = []
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(write=lambda s: written.append(s), flush=lambda: None))
    util.run(make_args())
    assert written == ["resp\n"]


def test_util_run_markdown_with_session(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    calls = []
    manager = SimpleNamespace(refresh_from_chat_session=lambda cs: calls.append("refresh"))
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda session_type: chat)
    monkeypatch.setattr(util, "_init_session_manager", lambda cs, args: manager)
    orig_get = lair.config.get
    monkeypatch.setattr(
        lair.config,
        "get",
        lambda k: "tmpl" if k == "util.system_prompt_template" else orig_get(k),
    )
    monkeypatch.setattr(util, "_get_instructions", lambda a: "i")
    monkeypatch.setattr(util, "_get_user_messages", lambda a: [])
    monkeypatch.setattr(util, "call_llm", lambda *a, **k: "resp")
    monkeypatch.setattr(util, "clean_response", lambda r: r)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    monkeypatch.setattr(lair.config, "set", lambda *a, **k: None)
    updated = []
    monkeypatch.setattr(lair.config, "update", lambda cfg: updated.append(True))
    reporter = SimpleNamespace(llm_output=lambda r: calls.append(r))
    monkeypatch.setattr(lair.reporting, "Reporting", lambda: reporter)
    util.run(make_args(markdown=True))
    assert "resp" in calls and updated


def test_util_module_info_func():
    info = util_mod._module_info()
    assert info["class"] is util_mod.Util
    assert info["description"].startswith("Make simple calls") and isinstance(info["tags"], list)


def test_get_instructions_from_argument():
    util = make_util()
    args = argparse.Namespace(instructions="xyz", instructions_file=None)
    assert util._get_instructions(args) == "xyz"


def test_get_user_messages_pipe(monkeypatch):
    util = make_util()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(read=lambda: "pipe"))
    args = argparse.Namespace(pipe=True, content_file=None, content=None, attachments=None)
    msgs = util._get_user_messages(args)
    assert any("pipe" in m.get("content", "") for m in msgs)


def test_get_user_messages_content():
    util = make_util()
    args = argparse.Namespace(pipe=False, content_file=None, content="text", attachments=None)
    msgs = util._get_user_messages(args)
    assert any("text" in m.get("content", "") for m in msgs)


class _SM:
    def __init__(self):
        pass

    def switch_to_session(self, alias, chat_session):
        raise lair.sessions.UnknownSessionException("missing")

    def is_alias_available(self, alias):
        return False

    def add_from_chat_session(self, chat_session):
        pass


def test_init_session_manager_unknown_no_create(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: _SM())
    errors = []
    monkeypatch.setattr(logger, "error", lambda msg: errors.append(msg))
    with pytest.raises(SystemExit):
        util._init_session_manager(chat, make_args(session="a"))
    assert any("Unknown session" in e for e in errors)


def test_init_session_manager_read_only(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: _SM())
    errors = []
    monkeypatch.setattr(logger, "error", lambda msg: errors.append(msg))
    with pytest.raises(SystemExit):
        util._init_session_manager(chat, make_args(session="a", allow_create_session=True, read_only_session=True))
    assert any("read-only-session" in e for e in errors)


def test_init_session_manager_alias_used(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: _SM())
    monkeypatch.setattr(lair.util, "safe_int", lambda v: v)
    errors = []
    monkeypatch.setattr(logger, "error", lambda msg: errors.append(msg))
    with pytest.raises(SystemExit):
        util._init_session_manager(chat, make_args(session="alias", allow_create_session=True))
    assert any("Alias is already used" in e for e in errors)


def test_util_run_sets_model_and_include(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda session_type: chat)
    monkeypatch.setattr(util, "_init_session_manager", lambda cs, args: None)
    orig_get = lair.config.get
    monkeypatch.setattr(lair.config, "get", lambda k: "tmpl" if k == "util.system_prompt_template" else orig_get(k))
    monkeypatch.setattr(util, "_get_instructions", lambda a: "i")
    monkeypatch.setattr(util, "_get_user_messages", lambda a: [])
    monkeypatch.setattr(util, "call_llm", lambda *a, **k: "resp")
    monkeypatch.setattr(util, "clean_response", lambda r: r)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    sets = []
    monkeypatch.setattr(lair.config, "set", lambda k, v: sets.append((k, v)))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(write=lambda s: None, flush=lambda: None))
    util.run(make_args(model="model-x", include_filenames=True))
    assert ("model.name", "model-x") in sets
    assert ("misc.provide_attachment_filenames", True) in sets
