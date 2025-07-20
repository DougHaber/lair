import importlib
import json
import sys
import types

import pytest

import lair


def setup_openai(monkeypatch, create_fn):
    class DummyOpenAI:
        def __init__(self, *a, **k):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create_fn))
            self.models = types.SimpleNamespace(list=lambda: [])

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=DummyOpenAI))
    import lair.sessions.openai_chat_session as ocs

    importlib.reload(ocs)
    return ocs


class DummyMessage:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls or []
        self.content = content

    def dict(self):
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ],
        }


class DummyToolCall:
    def __init__(self, id, name, args):
        self.id = id
        self.function = types.SimpleNamespace(name=name, arguments=json.dumps(args))


class DummyAnswer:
    def __init__(self, msg):
        self.choices = [types.SimpleNamespace(message=msg)]


def test_process_tool_calls(monkeypatch):
    def create_fn(*a, **k):
        pass

    ocs = setup_openai(monkeypatch, create_fn)
    session = ocs.OpenAIChatSession(history=None, tool_set=None)
    session.tool_set = types.SimpleNamespace(call_tool=lambda n, a, i: {"v": a["n"]}, get_definitions=lambda: [])
    records = []
    session.reporting = types.SimpleNamespace(
        assistant_tool_calls=lambda m, show_heading=True: records.append("assistant"),
        tool_message=lambda m, show_heading=True: records.append("tool"),
        messages_to_str=lambda m: "",
    )
    lair.config.set("chat.verbose", True, no_event=True)
    messages = []
    tool_messages = []
    tc = DummyToolCall("1", "func", {"n": 3})
    msg = DummyMessage([tc])
    session._process_tool_calls(msg, messages, tool_messages)
    assert messages and tool_messages and "tool" in records and "assistant" in records


def test_invoke_with_tools(monkeypatch):
    cycle = {"count": 0}

    def create_fn(*, messages, model, temperature, max_completion_tokens, tools):
        if cycle["count"] == 0:
            cycle["count"] += 1
            return DummyAnswer(DummyMessage([DummyToolCall("1", "f", {"x": 2})]))
        return DummyAnswer(DummyMessage(content="done"))

    ocs = setup_openai(monkeypatch, create_fn)
    session = ocs.OpenAIChatSession(history=None, tool_set=None)
    session.tool_set = types.SimpleNamespace(call_tool=lambda n, a, i: {"res": 1}, get_definitions=lambda: [])
    result, tool_msgs = session.invoke_with_tools()
    assert result == "done" and tool_msgs[0]["role"] == "assistant"
    assert session.last_prompt


def test_invoke_uses_defaults(monkeypatch):
    def create_fn(*, messages, model, temperature, max_completion_tokens):
        create_fn.record = messages
        return DummyAnswer(DummyMessage(content="out"))

    ocs = setup_openai(monkeypatch, create_fn)
    session = ocs.OpenAIChatSession(history=None, tool_set=None)
    session.reporting = types.SimpleNamespace(messages_to_str=lambda m: "S")
    monkeypatch.setattr(session, "get_system_prompt", lambda: "SYS")
    session.history.add_message("user", "hi")

    result = session.invoke()
    assert result == "out" and create_fn.record[0]["role"] == "system"
    assert session.last_prompt == "S"

    session.openai = None
    with pytest.raises(RuntimeError):
        session.invoke(messages=[{"role": "user", "content": "x"}])


def test_list_models_error_handling(monkeypatch):
    def create_fn(*a, **k):
        return DummyAnswer(DummyMessage(content="x"))

    ocs = setup_openai(monkeypatch, create_fn)
    session = ocs.OpenAIChatSession(history=None, tool_set=None)
    session.openai = None
    with pytest.raises(RuntimeError):
        session.list_models()

    session.recreate_openai_client()

    def bad_list():
        raise ValueError("boom")

    session.openai.models = types.SimpleNamespace(list=bad_list)
    with pytest.raises(ValueError):
        session.list_models()
    session.openai.models = types.SimpleNamespace(list=bad_list)
    assert session.list_models(ignore_errors=True) is None
