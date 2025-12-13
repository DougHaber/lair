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


def test_auto_generate_title_missing_parts(monkeypatch):
    session = DummySession()
    lair.config.set("session.auto_generate_titles.enabled", True, no_event=True)
    session.history.add_message("assistant", "only assistant")
    assert session.auto_generate_title() is None
    session.history.clear()
    session.history.add_message("user", "only user")
    assert session.auto_generate_title() is None


def test_serialization_helpers(monkeypatch, tmp_path):
    session = DummySession()
    calls = {}

    def fake_save(obj, filename):
        calls["save"] = filename

    def fake_load(obj, filename):
        calls["load"] = filename

    def fake_to_dict(obj):
        calls["to_dict"] = True
        return {"k": 1}

    def fake_update(obj, state):
        calls["update"] = state

    monkeypatch.setattr(lair.sessions.serializer, "save", fake_save)
    monkeypatch.setattr(lair.sessions.serializer, "load", fake_load)
    monkeypatch.setattr(lair.sessions.serializer, "session_to_dict", fake_to_dict)
    monkeypatch.setattr(lair.sessions.serializer, "update_session_from_dict", fake_update)

    file1 = tmp_path / "state1.json"
    file2 = tmp_path / "state2.json"
    session.save_to_file(file1)
    session.load_from_file(file2)
    assert calls["save"] == file1 and calls["load"] == file2
    assert session.to_dict() == {"k": 1}
    session.update_from_dict({"a": 2})
    assert calls["update"] == {"a": 2}


def test_auto_generate_title_two_user_messages(monkeypatch):
    session = DummySession()
    lair.config.set("session.auto_generate_titles.enabled", True, no_event=True)
    session.history.add_message("user", "first")
    session.history.add_message("user", "second")
    assert session.auto_generate_title() is None


def test_get_system_prompt(monkeypatch):
    session = DummySession()
    lair.config.set("session.system_prompt_template", "PROMPT", no_event=True)
    assert session.get_system_prompt() == "PROMPT"


def test_base_methods_exposed():
    session = DummySession()
    assert BaseChatSession.invoke(session) is None
    assert BaseChatSession.invoke_with_tools(session) is None
    assert BaseChatSession.list_models(session) is None
