import argparse

import pytest

import lair
from lair.modules import chat as chat_mod
from lair.modules import util as util_mod


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
