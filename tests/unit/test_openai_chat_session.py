import types
import importlib
import sys
import lair

import json
import pytest


def setup_session(monkeypatch, responses=None, tool_set=None):
    """Helper to create OpenAIChatSession with patched openai."""
    if responses is None:
        responses = []

    # Prepare dummy OpenAI client
    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            self.calls = []
            self.responses = list(responses)

            def create(**kwargs):
                self.calls.append(kwargs)
                return self.responses.pop(0)

            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
            self.models = types.SimpleNamespace(list=lambda: [])

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=DummyOpenAI))
    import lair.sessions.openai_chat_session as ocs

    importlib.reload(ocs)
    session = ocs.OpenAIChatSession(history=None, tool_set=tool_set)
    session.openai = DummyOpenAI()
    return session


def make_message(content=None, tool_calls=None):
    if tool_calls is None:
        tool_calls = []

    def to_dict():
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        }

    return types.SimpleNamespace(content=content, tool_calls=tool_calls, dict=to_dict)


class DummyToolCall:
    def __init__(self, name="t", args=None, id="id1"):
        self.function = types.SimpleNamespace(name=name, arguments=json_dump(args or {}))
        self.id = id


def json_dump(obj):
    import json

    return json.dumps(obj)


def test_invoke_uses_history_and_config(monkeypatch):
    lair.config.set("session.system_prompt_template", "SYS", no_event=True)
    lair.config.set("model.name", "m", no_event=True)
    lair.config.set("model.temperature", 0.5, no_event=True)
    lair.config.set("model.max_tokens", 5, no_event=True)

    answer_msg = make_message(content=" ok ")
    response_obj = types.SimpleNamespace(choices=[types.SimpleNamespace(message=answer_msg)])

    session = setup_session(monkeypatch, responses=[response_obj])
    session.history.add_message("user", "hi")

    reply = session.invoke()

    call = session.openai.calls[0]
    assert call["model"] == "m"
    assert call["temperature"] == 0.5
    assert call["max_completion_tokens"] == 5
    assert reply == "ok"
    assert call["messages"][0]["role"] == "system" and call["messages"][0]["content"] == "SYS"
    assert call["messages"][1]["content"] == "hi"


def test_process_tool_calls(monkeypatch):
    lair.config.set("chat.verbose", True, no_event=True)
    session = setup_session(monkeypatch)
    captured = []
    session.reporting = types.SimpleNamespace(
        assistant_tool_calls=lambda m, show_heading=True: captured.append(("a", m)),
        tool_message=lambda m, show_heading=True: captured.append(("t", m)),
        messages_to_str=lambda m: "",
    )
    session.tool_set = types.SimpleNamespace(call_tool=lambda n, a, i: a)

    messages = []
    tool_messages = []
    tc = DummyToolCall(args={"x": 1}, id="1")
    session._process_tool_calls(make_message(content=None, tool_calls=[tc]), messages, tool_messages)

    assert captured and captured[0][0] == "a"
    assert messages[1]["role"] == "tool" and json.loads(messages[1]["content"])["x"] == 1
    # when verbose off, no extra capture
    lair.config.set("chat.verbose", False, no_event=True)
    captured.clear()
    session._process_tool_calls(make_message(tool_calls=[tc]), [], [])
    assert not captured


def test_invoke_with_tools_cycle(monkeypatch):
    tool_set = types.SimpleNamespace(call_tool=lambda n, a, i: {"echo": a}, get_definitions=lambda: [{"name": "tool"}])
    tc = DummyToolCall(args={"y": 2}, id="1")
    msg_tool = make_message(content=None, tool_calls=[tc])
    msg_final = make_message(content="done", tool_calls=[])
    response_obj1 = types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg_tool)])
    response_obj2 = types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg_final)])

    session = setup_session(monkeypatch, responses=[response_obj1, response_obj2], tool_set=tool_set)
    session.history.add_message("user", "ask")

    reply, tool_messages = session.invoke_with_tools()
    assert reply == "done"
    assert len(tool_messages) == 2  # assistant message + tool response
    assert session.openai.calls and len(session.openai.calls) == 2


def test_list_models_error(monkeypatch):
    session = setup_session(monkeypatch)
    session.openai.models = types.SimpleNamespace(list=lambda: (_ for _ in ()).throw(RuntimeError("fail")))

    result = session.list_models(ignore_errors=True)
    assert result is None
    with pytest.raises(RuntimeError):
        session.list_models(ignore_errors=False)
