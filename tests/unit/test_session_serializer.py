import json

import pytest

from lair.components.history import ChatHistory
from lair.components.tools import ToolSet
from lair.sessions import serializer
from lair.sessions.base_chat_session import BaseChatSession


class DummySession(BaseChatSession):
    def __init__(self):
        super().__init__(history=ChatHistory(), tool_set=ToolSet(tools=[]))

    def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
        return "invoke"

    def invoke_with_tools(self, messages=None, disable_system_prompt=False):
        return "invoke-tools", []

    def list_models(self, ignore_errors=False):
        return []


def create_session():
    s = DummySession()
    s.session_id = 5
    s.session_alias = "alias"
    s.session_title = "title"
    s.last_prompt = "p"
    s.last_response = "r"
    s.history.add_message("user", "hi")
    return s


def test_save_and_load(tmp_path):
    s1 = create_session()
    file_path = tmp_path / "state.json"
    serializer.save(s1, file_path)
    assert json.loads(file_path.read_text())["id"] == 5
    s2 = DummySession()
    serializer.load(s2, file_path)
    assert s2.session_title == "title" and s2.history.get_messages()[0]["content"] == "hi"


def test_update_session_from_dict_errors():
    s = DummySession()
    for bad in [{}, {"version": "0.1"}, {"version": "1.0"}]:
        with pytest.raises(RuntimeError):
            try:
                serializer.update_session_from_dict(s, bad)
            except Exception as exc:
                raise RuntimeError from exc
