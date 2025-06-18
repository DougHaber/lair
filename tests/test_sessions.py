import types

import lair
from lair.sessions.base_chat_session import BaseChatSession
import sys

class DummySession(BaseChatSession):
    def __init__(self):
        super().__init__()
        self.called = False
    def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
        self.called = True
        return 'response'
    def invoke_with_tools(self, messages=None, disable_system_prompt=False):
        return 'tool-response', []
    def list_models(self, ignore_errors=False):
        return []


def test_chat_and_auto_title(monkeypatch):
    s = DummySession()
    monkeypatch.setattr(lair.events, 'fire', lambda *a, **k: None)
    lair.config.set('tools.enabled', False)
    lair.config.set('session.auto_generate_titles.enabled', False)
    assert s.chat('hi') == 'response'
    assert s.called


def test_openai_list_models(monkeypatch):
    class DummyModel:
        def __init__(self, id):
            self.id = id
            self.created = 0
            self.object = 'model'
            self.owned_by = 'me'
    class DummyOpenAI:
        def __init__(self, *a, **k):
            self.models = types.SimpleNamespace(list=lambda: [DummyModel('m')])
    monkeypatch.setitem(sys.modules, 'openai', types.SimpleNamespace(OpenAI=DummyOpenAI))
    import importlib
    import lair.sessions.openai_chat_session as ocs
    importlib.reload(ocs)
    session = ocs.OpenAIChatSession(history=None, tool_set=None)
    session.openai = DummyOpenAI()
    models = session.list_models()
    assert models[0]['id'] == 'm'
