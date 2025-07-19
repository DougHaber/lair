import argparse
import pytest

import lair
from lair.modules import chat as chat_mod, util as util_mod

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
    base = dict(
        session=None,
        allow_create_session=False,
        read_only_session=False,
        instructions=None,
        instructions_file=None,
        pipe=False,
        content=None,
        content_file=None,
        attachments=None,
        enable_tools=False,
        markdown=False,
        include_filenames=None,
        model=None,
    )
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
    manager.switch_to_session = lambda alias, cs: (_ for _ in ()).throw(lair.sessions.UnknownSessionException("missing"))
    monkeypatch.setattr(lair.util, "safe_int", lambda v: v)
    result = util._init_session_manager(chat, make_args(session="new", allow_create_session=True))
    assert result is manager and chat.session_alias == "new" and manager.add_called
