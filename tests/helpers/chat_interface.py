import importlib
import sys
import types

import pytest  # noqa: F401

import lair
from lair.components.history.chat_history import ChatHistory
from lair.components.tools.tool_set import ToolSet
from lair.sessions.base_chat_session import BaseChatSession

_STUB_MODULES = [
    "diffusers",
    "transformers",
    "torch",
    "comfy_script",
    "lair.comfy_caller",
    "trafilatura",
    "PIL",
    "duckduckgo_search",
    "requests",
    "libtmux",
    "lmdb",
]


def _stub_optional_dependencies() -> None:
    for name in _STUB_MODULES:
        sys.modules.setdefault(name, types.ModuleType(name))


class DummyChatSession(BaseChatSession):
    def __init__(self) -> None:
        super().__init__(history=ChatHistory(), tool_set=ToolSet(tools=[]))

    def invoke(self, messages=None, disable_system_prompt=False, model=None, temperature=None):
        return "ok"

    def invoke_with_tools(self, messages=None, disable_system_prompt=False):
        return "ok", []

    def list_models(self, ignore_errors=False):
        return [{"id": "model-a"}, {"id": "model-b"}]


class DummyReporting:
    def __init__(self) -> None:
        self.messages = []

    def system_message(self, message, **kwargs) -> None:  # noqa: D401 - simple wrapper
        self.messages.append(("system", message))

    def user_error(self, message) -> None:
        self.messages.append(("error", message))

    def print_rich(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        pass

    def table_system(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        pass

    def table_from_dicts_system(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        pass

    def message(self, message) -> None:
        self.messages.append(("message", message))

    def llm_output(self, message) -> None:
        self.messages.append(("llm", message))

    def style(self, text, style=None):
        return text


class SimpleSessionManager:
    def __init__(self) -> None:
        self.sessions = {}
        self.aliases = {}
        self.next_id = 1

    def add_from_chat_session(self, chat_session) -> None:
        if chat_session.session_id is None:
            chat_session.session_id = self.next_id
            self.next_id += 1
        self.sessions[chat_session.session_id] = lair.sessions.serializer.session_to_dict(chat_session)
        if chat_session.session_alias:
            self.aliases[chat_session.session_alias] = chat_session.session_id

    def refresh_from_chat_session(self, chat_session) -> None:
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
            raise Exception("Unknown")
        return None

    def switch_to_session(self, id_or_alias, chat_session) -> None:
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

    def delete_sessions(self, ids) -> None:
        for item in ids:
            sid = self.get_session_id(item)
            self.sessions.pop(sid, None)
            for alias in list(self.aliases):
                if self.aliases[alias] == sid:
                    del self.aliases[alias]

    def is_alias_available(self, alias):
        if alias is None:
            return True
        try:
            int(alias)
            return False
        except ValueError:
            pass
        return alias not in self.aliases

    def set_alias(self, id_or_alias, new_alias) -> None:
        if new_alias and not self.is_alias_available(new_alias):
            raise ValueError
        sid = self.get_session_id(id_or_alias)
        for alias in list(self.aliases):
            if self.aliases[alias] == sid:
                del self.aliases[alias]
        if new_alias:
            self.aliases[new_alias] = sid
        self.sessions.setdefault(sid, {})["alias"] = new_alias

    def set_title(self, id_or_alias, title) -> None:
        sid = self.get_session_id(id_or_alias)
        self.sessions[sid]["title"] = title


def make_interface(monkeypatch):
    _stub_optional_dependencies()

    import lair

    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda t: DummyChatSession())
    monkeypatch.setattr(lair.sessions, "SessionManager", SimpleSessionManager)
    monkeypatch.setattr(lair.reporting, "Reporting", DummyReporting)
    import prompt_toolkit.application

    monkeypatch.setattr(
        prompt_toolkit.application,
        "run_in_terminal",
        lambda func, *args, **kwargs: func(),
    )

    lair.config.set("chat.history_file", None)

    ci_mod = importlib.import_module("lair.cli.chat_interface")
    importlib.reload(ci_mod)
    return ci_mod.ChatInterface()
