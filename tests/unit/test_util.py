import argparse

import pytest

import lair
from tests.unit.test_modules import DummyChatSession, make_util


class DummySessionManager:
    def __init__(self, *, raise_unknown=False, alias_available=True):
        self.raise_unknown = raise_unknown
        self.alias_available = alias_available
        self.added = False
        self.refreshed = False
        self.switched = False

    def switch_to_session(self, session, chat_session):
        self.switched = True
        if self.raise_unknown:
            raise lair.sessions.UnknownSessionException()

    def is_alias_available(self, alias):
        return self.alias_available

    def add_from_chat_session(self, chat_session):
        self.added = True

    def refresh_from_chat_session(self, chat_session):
        self.refreshed = True


def test_init_session_manager_none(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    chat.session_title = None
    args = argparse.Namespace(session=None, allow_create_session=False, read_only_session=False)
    result = util._init_session_manager(chat, args)
    assert result is None
    assert chat.session_title == "N/A"


def test_init_session_manager_unknown(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    chat.session_alias = None
    manager = DummySessionManager(raise_unknown=True)
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: manager)
    args = argparse.Namespace(session="1", allow_create_session=False, read_only_session=False)
    with pytest.raises(SystemExit):
        util._init_session_manager(chat, args)


def test_init_session_manager_create(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    manager = DummySessionManager(raise_unknown=True, alias_available=True)
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: manager)
    args = argparse.Namespace(session="new", allow_create_session=True, read_only_session=False)
    result = util._init_session_manager(chat, args)
    assert result is manager
    assert chat.session_alias == "new"
    assert manager.added


class ReportingRecorder:
    def __init__(self):
        self.message = None

    def llm_output(self, message):
        self.message = message


def test_run_markdown(monkeypatch):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda *a, **k: chat)
    manager = DummySessionManager()
    monkeypatch.setattr(util, "_init_session_manager", lambda cs, args: manager)
    monkeypatch.setattr(util, "_get_instructions", lambda a: "inst")
    monkeypatch.setattr(util, "_get_user_messages", lambda a: [])
    monkeypatch.setattr(util, "call_llm", lambda *a, **k: "answer")
    monkeypatch.setattr(util, "clean_response", lambda r: r + "-clean")
    recorder = ReportingRecorder()
    monkeypatch.setattr(lair.reporting, "Reporting", lambda: recorder)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    config_backup = lair.config.active.copy()
    args = argparse.Namespace(
        session="sid",
        allow_create_session=True,
        read_only_session=False,
        markdown=True,
        model=None,
        include_filenames=None,
        enable_tools=False,
        instructions="i",
        instructions_file=None,
        pipe=False,
        content=None,
        content_file=None,
        attachments=None,
    )
    util.run(args)
    assert manager.refreshed
    assert recorder.message == "answer-clean"
    lair.config.update(config_backup)


def test_run_plain(monkeypatch, capsys):
    util = make_util()
    chat = DummyChatSession()
    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda *a, **k: chat)
    monkeypatch.setattr(util, "_init_session_manager", lambda cs, args: None)
    monkeypatch.setattr(util, "_get_instructions", lambda a: "inst")
    monkeypatch.setattr(util, "_get_user_messages", lambda a: [])
    monkeypatch.setattr(util, "call_llm", lambda *a, **k: "text")
    monkeypatch.setattr(util, "clean_response", lambda r: r)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)
    args = argparse.Namespace(
        session=None,
        allow_create_session=False,
        read_only_session=False,
        markdown=False,
        model=None,
        include_filenames=None,
        enable_tools=True,
        instructions="i",
        instructions_file=None,
        pipe=False,
        content=None,
        content_file=None,
        attachments=None,
    )
    config_backup = lair.config.active.copy()
    util.run(args)
    out = capsys.readouterr().out.strip()
    assert out == "text"
    lair.config.update(config_backup)
