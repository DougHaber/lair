import argparse
import pytest

import lair
from lair.modules import chat as chat_mod, util as util_mod


class DummyChatSession:
    def __init__(self):
        self.called = False

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


def test_chat_module_info():
    info = chat_mod._module_info()
    assert info["class"] is chat_mod.Chat
    assert info["description"].startswith("Run the interactive")
    assert "cli" in info["tags"]


class DummySession:
    def __init__(self):
        self.session_title = None
        self.session_alias = None


class DummySessionManager:
    def __init__(self, raise_unknown=False, alias_available=True):
        self.raise_unknown = raise_unknown
        self.alias_available = alias_available
        self.add_called = False
        self.switched = False

    def switch_to_session(self, alias, chat_session):
        if self.raise_unknown:
            raise lair.sessions.UnknownSessionException("no session")
        self.switched = True

    def is_alias_available(self, alias):
        return self.alias_available

    def add_from_chat_session(self, chat_session):
        self.add_called = True


def test_init_session_manager_create(monkeypatch):
    util = make_util()
    manager = DummySessionManager(raise_unknown=True, alias_available=True)
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: manager)
    monkeypatch.setattr(lair.util, "safe_int", lambda v: None)
    args = argparse.Namespace(
        session="new",
        allow_create_session=True,
        read_only_session=False,
    )
    chat_session = DummySession()
    result = util._init_session_manager(chat_session, args)
    assert result is manager
    assert chat_session.session_alias == "new"
    assert manager.add_called


def test_init_session_manager_numeric_alias(monkeypatch):
    util = make_util()
    manager = DummySessionManager(raise_unknown=True, alias_available=False)
    monkeypatch.setattr(lair.sessions, "SessionManager", lambda: manager)
    monkeypatch.setattr(lair.util, "safe_int", lambda v: 5)
    args = argparse.Namespace(
        session="5",
        allow_create_session=True,
        read_only_session=False,
    )
    with pytest.raises(SystemExit):
        util._init_session_manager(DummySession(), args)


def test_util_run(monkeypatch):
    util = make_util()

    class DummyChat:
        def __init__(self):
            self.messages = None
            self.session_title = None
            self.session_alias = None

        def chat(self, messages):
            self.messages = messages
            return "```result```"

    chat_obj = DummyChat()

    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda session_type: chat_obj)
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)

    def fake_init(chat_session, args):
        chat_session.session_title = "N/A"
        return None

    monkeypatch.setattr(util, "_init_session_manager", fake_init)
    monkeypatch.setattr(util, "_get_instructions", lambda a: "INST")
    monkeypatch.setattr(util, "_get_user_messages", lambda a: [{"role": "user", "content": "MSG"}])
    monkeypatch.setattr(util, "clean_response", lambda r: r.strip("`") )
    outputs = []

    class DummyReporting:
        def llm_output(self, text):
            outputs.append(text)

    monkeypatch.setattr(lair.reporting, "Reporting", lambda: DummyReporting())

    backup = lair.config.active.copy()
    args = argparse.Namespace(
        session=None,
        allow_create_session=False,
        model=None,
        markdown=True,
        include_filenames=None,
        enable_tools=True,
        pipe=False,
        content=None,
        content_file=None,
        attachments=None,
        instructions=None,
        instructions_file=None,
        read_only_session=False,
    )

    util.run(args)
    lair.config.update(backup)

    assert outputs == ["result"]
    assert chat_obj.session_title == "N/A"
    assert chat_obj.messages[1]["content"] == "MSG"
