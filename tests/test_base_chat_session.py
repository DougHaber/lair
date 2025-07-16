import pytest

import lair
from lair.sessions.base_chat_session import BaseChatSession


class DummySession(BaseChatSession):
    def __init__(self):
        super().__init__()
        self.invoked = []
        self.invoke_return = "answer"
        self.invoke_tools_return = ("tools", [])
        self.raise_invoke = False
        self.raise_invoke_tools = False

    def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
        if self.raise_invoke:
            raise RuntimeError("invoke error")
        self.invoked.append(("invoke", messages, disable_system_prompt, model, temperature))
        return self.invoke_return

    def invoke_with_tools(self, messages=None, disable_system_prompt=False):
        if self.raise_invoke_tools:
            raise RuntimeError("invoke_with_tools error")
        self.invoked.append(("invoke_with_tools", messages, disable_system_prompt))
        return self.invoke_tools_return

    def list_models(self, ignore_errors=False):
        return []


def test_add_message_to_history(monkeypatch):
    session = DummySession()
    added = []
    monkeypatch.setattr(session.history, "add_messages", lambda msgs: added.append(msgs))
    session._add_message_to_history([{"role": "user", "content": "hi"}])
    assert added == [[{"role": "user", "content": "hi"}]]
    added_single = []
    monkeypatch.setattr(session.history, "add_message", lambda role, msg: added_single.append((role, msg)))
    session._add_message_to_history("hello")
    assert added_single == [("user", "hello")]


def test_invoke_chat_with_tools(monkeypatch):
    session = DummySession()
    lair.config.set("tools.enabled", True)
    result, tool_msgs = session._invoke_chat()
    assert result == "tools"
    assert tool_msgs == []
    assert session.invoked and session.invoked[0][0] == "invoke_with_tools"


def test_chat_exception_rollsback(monkeypatch):
    session = DummySession()
    session.raise_invoke = True
    lair.config.set("tools.enabled", False)
    called = []
    monkeypatch.setattr(session.history, "rollback", lambda: called.append(True) or session.history.clear())
    with pytest.raises(RuntimeError):
        session.chat("fail")
    assert called
    assert session.history.num_messages() == 0


def test_record_response(monkeypatch):
    session = DummySession()
    added_tools = []
    added_msgs = []
    committed = []
    monkeypatch.setattr(session.history, "add_tool_messages", lambda m: added_tools.append(m))
    monkeypatch.setattr(session.history, "add_message", lambda r, m: added_msgs.append((r, m)))
    monkeypatch.setattr(session.history, "commit", lambda: committed.append(True))
    tool_messages = [{"role": "tool", "content": "t", "tool_call_id": "1"}]
    session._record_response("ans", tool_messages)
    assert added_tools == [tool_messages]
    assert added_msgs == [("assistant", "ans")]
    assert committed


def test_auto_generate_title_early(monkeypatch):
    session = DummySession()
    lair.config.set("session.auto_generate_titles.enabled", True)
    assert session.auto_generate_title() is None
    assert not session.invoked


def test_auto_generate_title_missing_messages(monkeypatch):
    session = DummySession()
    lair.config.set("session.auto_generate_titles.enabled", True)
    session.history.add_message("system", "sys")
    session.history.add_message("user", "hi")
    logs = []
    monkeypatch.setattr(lair.sessions.base_chat_session.logger, "debug", lambda msg: logs.append(msg))
    assert session.auto_generate_title() is None
    assert logs and "Could not find" in logs[0]


def test_get_system_prompt(monkeypatch):
    session = DummySession()
    lair.config.set("session.system_prompt_template", "test")
    called = []
    monkeypatch.setattr(lair.util.prompt_template, "fill", lambda t: called.append(t) or "filled")
    assert session.get_system_prompt() == "filled"
    assert called == ["test"]


def test_serialization_helpers(monkeypatch):
    session = DummySession()
    actions = []
    monkeypatch.setattr(lair.sessions.serializer, "save", lambda s, f: actions.append(("save", f)))
    monkeypatch.setattr(lair.sessions.serializer, "load", lambda s, f: actions.append(("load", f)))
    monkeypatch.setattr(lair.sessions.serializer, "session_to_dict", lambda s: {"id": 1})
    monkeypatch.setattr(lair.sessions.serializer, "update_session_from_dict", lambda s, d: actions.append(("update", d)))
    session.save_to_file("f")
    session.load_from_file("f")
    assert session.to_dict() == {"id": 1}
    session.update_from_dict({"k": 1})
    assert actions == [("save", "f"), ("load", "f"), ("update", {"k": 1})]


def test_new_and_import_state():
    src = DummySession()
    src.session_id = 5
    src.session_alias = "alias"
    src.session_title = "title"
    src.last_prompt = "p"
    src.last_response = "r"
    src.history.add_message("user", "a")
    tgt = DummySession()
    tgt.import_state(src)
    assert tgt.session_id == 5
    assert tgt.session_alias == "alias"
    assert tgt.session_title == "title"
    assert tgt.last_prompt == "p"
    assert tgt.last_response == "r"
    assert tgt.history.get_messages() == src.history.get_messages()
    assert tgt.history is not src.history
    assert tgt.tool_set is src.tool_set
    tgt.new_session()
    assert tgt.session_id is None and tgt.session_alias is None
    assert tgt.session_title is None
    assert tgt.history.get_messages() == []
