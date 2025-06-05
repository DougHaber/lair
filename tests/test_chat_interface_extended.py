import sys
import types
import importlib

import pytest  # noqa: F401


def make_interface(monkeypatch):
    # stub heavy optional dependencies before importing lair
    for name in [
        'diffusers', 'transformers', 'torch', 'comfy_script', 'lair.comfy_caller',
        'trafilatura', 'PIL', 'duckduckgo_search', 'pdfplumber', 'requests',
        'libtmux', 'lmdb'
    ]:
        sys.modules.setdefault(name, types.ModuleType(name))

    import lair
    from lair.components.history.chat_history import ChatHistory
    from lair.components.tools.tool_set import ToolSet
    from lair.sessions.base_chat_session import BaseChatSession

    class DummyChatSession(BaseChatSession):
        def __init__(self):
            super().__init__(history=ChatHistory(), tool_set=ToolSet(tools=[]))

        def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
            return 'ok'

        def invoke_with_tools(self, messages=None, disable_system_prompt=False):
            return 'ok', []

        def list_models(self, ignore_errors=False):
            return [{'id': 'model-a'}, {'id': 'model-b'}]

    class DummyReporting:
        def __init__(self):
            self.messages = []

        def system_message(self, message, **kwargs):
            self.messages.append(('system', message))

        def user_error(self, message):
            self.messages.append(('error', message))

        def print_rich(self, *args, **kwargs):
            pass

        def table_system(self, *args, **kwargs):
            pass

        def table_from_dicts_system(self, *args, **kwargs):
            pass

        def message(self, message):
            self.messages.append(('message', message))

        def llm_output(self, message):
            self.messages.append(('llm', message))

        def style(self, text, style=None):
            return text

    class SimpleSessionManager:
        def __init__(self):
            self.sessions = {}
            self.aliases = {}
            self.next_id = 1

        def add_from_chat_session(self, chat_session):
            if chat_session.session_id is None:
                chat_session.session_id = self.next_id
                self.next_id += 1
            self.sessions[chat_session.session_id] = lair.sessions.serializer.session_to_dict(chat_session)
            if chat_session.session_alias:
                self.aliases[chat_session.session_alias] = chat_session.session_id

        def refresh_from_chat_session(self, chat_session):
            self.sessions[chat_session.session_id] = lair.sessions.serializer.session_to_dict(chat_session)
            for alias, sid in list(self.aliases.items()):
                if sid == chat_session.session_id:
                    del self.aliases[alias]
            if chat_session.session_alias:
                self.aliases[chat_session.session_alias] = chat_session.session_id

        def get_session_id(self, id_or_alias, raise_exception=True):
            try:
                sid = int(id_or_alias)
                if sid in self.sessions:
                    return sid
            except ValueError:
                if id_or_alias in self.aliases:
                    return self.aliases[id_or_alias]
            if raise_exception:
                raise Exception('Unknown')
            return None

        def switch_to_session(self, id_or_alias, chat_session):
            sid = self.get_session_id(id_or_alias)
            lair.sessions.serializer.update_session_from_dict(chat_session, self.sessions[sid])

        def all_sessions(self):
            return self.sessions.values()

        def get_next_session_id(self, current):
            ids = sorted(self.sessions)
            return ids[(ids.index(current) + 1) % len(ids)] if ids else None

        def get_previous_session_id(self, current):
            ids = sorted(self.sessions)
            return ids[(ids.index(current) - 1) % len(ids)] if ids else None

        def delete_sessions(self, ids):
            for item in ids:
                sid = self.get_session_id(item)
                self.sessions.pop(sid, None)
                for a in list(self.aliases):
                    if self.aliases[a] == sid:
                        del self.aliases[a]

        def is_alias_available(self, alias):
            if alias is None:
                return True
            try:
                int(alias)
                return False
            except ValueError:
                pass
            return alias not in self.aliases

        def set_alias(self, id_or_alias, new_alias):
            if not self.is_alias_available(new_alias):
                raise ValueError
            sid = self.get_session_id(id_or_alias)
            for a in list(self.aliases):
                if self.aliases[a] == sid:
                    del self.aliases[a]
            if new_alias:
                self.aliases[new_alias] = sid
            self.sessions[sid]['alias'] = new_alias

        def set_title(self, id_or_alias, title):
            sid = self.get_session_id(id_or_alias)
            self.sessions[sid]['title'] = title

    monkeypatch.setattr(lair.sessions, 'get_chat_session', lambda t: DummyChatSession())
    monkeypatch.setattr(lair.sessions, 'SessionManager', SimpleSessionManager)
    monkeypatch.setattr(lair.reporting, 'Reporting', DummyReporting)

    lair.config.set('chat.history_file', None)

    ci_mod = importlib.import_module('lair.cli.chat_interface')
    importlib.reload(ci_mod)
    return ci_mod.ChatInterface()


def find_handler(ci, name):
    for b in ci._get_keybindings().bindings:
        if b.handler.__name__ == name:
            return b.handler
    raise AssertionError('handler not found')


def test_keybindings_and_chat(monkeypatch):
    import lair
    ci = make_interface(monkeypatch)

    assert ci._handle_request('hello')
    assert ci.chat_session.history.num_messages() > 0

    clear = find_handler(ci, 'session_clear')
    clear(None)
    assert ci.chat_session.history.num_messages() == 0

    new = find_handler(ci, 'session_new')
    new(None)
    first = ci.chat_session.session_id
    new(None)
    assert ci.chat_session.session_id == first + 1

    prev = find_handler(ci, 'session_previous')
    prev(None)
    assert ci.chat_session.session_id == first
    nxt = find_handler(ci, 'session_next')
    nxt(None)
    assert ci.chat_session.session_id == first + 1

    toggle = find_handler(ci, 'toggle_word_wrap')
    current = lair.config.get('style.word_wrap')
    toggle(None)
    assert lair.config.get('style.word_wrap') != current


def test_commands(monkeypatch):
    import lair
    ci = make_interface(monkeypatch)

    ci.command_model('/model', ['newmodel'], 'newmodel')
    assert lair.config.get('model.name') == 'newmodel'

    orig = ci.chat_session.session_id
    ci.command_session_new('/session-new', [], '')
    new_id = ci.chat_session.session_id
    assert new_id != orig

    ci.command_session('/session', [orig], str(orig))
    assert ci.chat_session.session_id == orig

    ci.command_session_alias('/session-alias', [orig, 'alias'], f'{orig} alias')
    assert ci.session_manager.get_session_id('alias') == orig

    ci.command_session_delete('/session-delete', [new_id], str(new_id))
    assert ci.session_manager.get_session_id(new_id, raise_exception=False) is None

    ci.chat_session.history.add_message('user', 'a')
    ci.chat_session.history.add_message('user', 'b')
    ci.command_history_slice('/history-slice', ['1:'], '1:')
    msgs = [m['content'] for m in ci.chat_session.history.get_messages()]
    assert msgs == ['b']

    ci.command_set('/set', ['style.word_wrap', 'false'], 'style.word_wrap false')
    assert lair.config.get('style.word_wrap') is False

    assert ci._handle_request('/model model-a')
    assert ci._handle_request('something')
