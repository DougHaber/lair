import pytest

import lair
from lair.components.history import ChatHistory
from lair.components.tools import ToolSet
from lair.sessions.base_chat_session import BaseChatSession


class DummySession(BaseChatSession):
    def __init__(self):
        super().__init__(history=ChatHistory(), tool_set=ToolSet(tools=[]))
        self.invoked = []

    def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
        self.invoked.append(("invoke", messages, disable_system_prompt))
        return "response"

    def invoke_with_tools(self, messages=None, disable_system_prompt=False):
        self.invoked.append(("tools", messages, disable_system_prompt))
        return "tool-response", [{"role": "assistant", "content": "tool", "refusal": None, "tool_calls": []}]

    def list_models(self, ignore_errors=False):
        return []


def test_add_message_to_history():
    session = DummySession()
    session._add_message_to_history("hello")
    session._add_message_to_history([{"role": "user", "content": "hi"}])
    assert [m["content"] for m in session.history.get_messages()] == ["hello", "hi"]


def test_invoke_chat_toggle_tools(monkeypatch):
    session = DummySession()
    lair.config.set("tools.enabled", False, no_event=True)
    result, tools = session._invoke_chat()
    assert result == "response" and tools is None
    lair.config.set("tools.enabled", True, no_event=True)
    result, tools = session._invoke_chat()
    assert result == "tool-response" and tools
    assert session.invoked[-1][0] == "tools"


def test_record_response_commits():
    session = DummySession()
    tool_msgs = [{"role": "assistant", "content": "tool", "refusal": None, "tool_calls": []}]
    session._record_response("answer", tool_msgs)
    msgs = session.history.get_messages()
    assert msgs[-1]["content"] == "answer" and session.history.finalized_index == len(msgs)


def test_chat_rollback_on_error(monkeypatch):
    session = DummySession()
    lair.config.set("tools.enabled", False, no_event=True)
    monkeypatch.setattr(session, "_invoke_chat", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    called = []
    original = session.history.rollback

    def wrapped():
        called.append(True)
        original()

    monkeypatch.setattr(session.history, "rollback", wrapped)
    with pytest.raises(RuntimeError):
        session.chat("bad")
    assert called and session.history.num_messages() == 0


def test_auto_generate_title(monkeypatch):
    session = DummySession()
    lair.config.set("session.auto_generate_titles.enabled", True, no_event=True)
    # Fails due to not enough messages
    assert session.auto_generate_title() is None
    # Now add messages and succeed
    session.history.add_message("user", "hi")
    session.history.add_message("assistant", "hello")
    monkeypatch.setattr(session, "invoke", lambda **kw: "A Title")
    assert session.auto_generate_title() == "A Title"
    assert session.session_title == "A Title"


def test_new_and_import_state():
    s1 = DummySession()
    s1.session_id = 1
    s1.session_alias = "alias"
    s1.session_title = "title"
    s1.last_prompt = "p"
    s1.last_response = "r"
    s1.history.add_message("user", "hi")
    s2 = DummySession()
    s2.import_state(s1)
    assert s2.session_id == 1 and s2.history.get_messages()[0]["content"] == "hi"
    s1.history.add_message("user", "new")
    assert len(s2.history.get_messages()) == 1
    s2.new_session()
    assert s2.session_id is None and s2.history.num_messages() == 0
