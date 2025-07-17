import lair
from lair.sessions.base_chat_session import BaseChatSession


class PassThroughSession(BaseChatSession):
    def __init__(self):
        super().__init__()

    def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
        # call parent abstract method to execute pass line
        super().invoke(messages, disable_system_prompt)
        return "ok"

    def invoke_with_tools(self, messages=None, disable_system_prompt=False):
        super().invoke_with_tools(messages, disable_system_prompt)
        return "ok", []

    def list_models(self, ignore_errors=False):
        super().list_models(ignore_errors=ignore_errors)
        return []


def test_super_methods_execute():
    session = PassThroughSession()
    assert session.invoke() == "ok"
    assert session.invoke_with_tools() == ("ok", [])
    assert session.list_models() == []
