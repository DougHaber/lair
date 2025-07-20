import copy
import gc

import pytest

import lair
from lair.components.history import schema
from lair.components.history.chat_history import ChatHistory, logger


@pytest.fixture(autouse=True)
def restore_config():
    original = lair.config.get("session.max_history_length", allow_not_found=True)
    yield
    lair.config.active["session.max_history_length"] = original
    gc.collect()


def test_validate_config_zero(monkeypatch):
    lair.config.active["session.max_history_length"] = 0
    warnings = []
    monkeypatch.setattr(logger, "warning", lambda msg: warnings.append(msg))
    ChatHistory()
    assert lair.config.active["session.max_history_length"] is None
    assert warnings and "Invalid value" in warnings[0]


def test_add_message_and_errors():
    hist = ChatHistory()
    with pytest.raises(ValueError):
        hist.add_message("tool", "bad")
    with pytest.raises(ValueError):
        hist.add_message("unknown", "bad")
    hist.add_message("user", "hello")
    assert hist.get_messages()[0]["content"] == "hello"


def test_add_tool_messages_and_error():
    hist = ChatHistory()
    msgs = [
        {"role": "tool", "content": None, "tool_call_id": "id"},
        {"role": "assistant", "content": "", "refusal": None, "tool_calls": []},
    ]
    hist.add_tool_messages(msgs)
    assert hist.get_messages()[0]["role"] == "tool"
    assert hist.get_messages()[0]["content"] == ""
    with pytest.raises(ValueError):
        hist.add_tool_messages([{"role": "user", "content": "x"}])


def test_copy_and_deepcopy_independent():
    hist = ChatHistory()
    hist.add_message("user", "one")
    shallow = copy.copy(hist)
    deep = copy.deepcopy(hist)
    hist.add_message("assistant", "two")
    assert len(shallow.get_messages()) == 1
    assert len(deep.get_messages()) == 1
    shallow._history[0]["content"] = "shallow"
    deep._history[0]["content"] = "deep"
    assert hist.get_messages()[0]["content"] == "shallow"
    shallow.add_message("user", "x")
    assert hist.num_messages() == 2
    assert deep.get_messages()[0]["content"] == "deep"


def test_get_messages_truncate_and_extra():
    lair.config.active["session.max_history_length"] = 2
    hist = ChatHistory()
    for i in range(3):
        hist.add_message("user", str(i))
    assert [m["content"] for m in hist.get_messages()] == ["1", "2"]
    extra = [{"role": "system", "content": "x"}]
    result = hist.get_messages(extra_messages=extra)
    assert result[-1] == extra[0]
    assert len(result) == 3
    out = hist.get_messages_as_jsonl_string()
    assert len(out.splitlines()) == 2


def test_set_history_truncate(monkeypatch):
    lair.config.active["session.max_history_length"] = 2
    called = []
    monkeypatch.setattr(schema, "validate_messages", lambda m: called.append(m))
    hist = ChatHistory()
    messages = [
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "user", "content": "c"},
    ]
    hist.set_history(messages)
    assert called and called[0] == messages
    assert [m["content"] for m in hist.get_messages()] == ["b", "c"]
    assert hist.finalized_index == 2


def test_commit_and_rollback():
    hist = ChatHistory()
    hist.add_message("user", "a")
    hist.rollback()
    assert hist.num_messages() == 0

    hist.add_message("user", "a")
    hist.add_message("user", "b")
    hist.commit()
    hist.add_message("user", "c")
    hist.rollback()
    assert [m["content"] for m in hist.get_messages()] == ["a", "b"]
