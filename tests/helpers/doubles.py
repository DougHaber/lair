from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lair
from lair.components.history import ChatHistory
from lair.components.tools import ToolSet


def stub_optional_dependencies() -> None:
    """
    Ensure optional third-party dependencies do not break imports during tests.

    The project intentionally keeps some integrations optional; tests that
    exercise unrelated code paths should not fail if those packages are
    missing from the environment.
    """
    optional_module_names = [
        "diffusers",
        "transformers",
        "torch",
        "PIL",
        "PIL.Image",
        "requests",
    ]

    for module_name in optional_module_names:
        if module_name not in sys.modules:
            sys.modules[module_name] = types.ModuleType(module_name)


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    """Minimal serialized session metadata used by in-memory session doubles."""

    id: int
    alias: str | None
    title: str | None
    mode: str
    model_name: str
    history: list[dict[str, Any]]


class UnknownSessionError(Exception):
    """Raised when a session cannot be resolved."""


UnknownSessionException = UnknownSessionError


class ChatSessionDouble:
    """Lightweight in-memory chat session used by the CLI tests."""

    def __init__(
        self,
        *,
        history: ChatHistory | None = None,
        tool_set: Any | None = None,
        models: list[dict[str, Any]] | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.session_id: int | None = None
        self.session_alias: str | None = None
        self.session_title: str | None = None

        self.last_prompt: str | None = None
        self.last_response: str | None = None

        self.history = history or ChatHistory()
        if messages is not None:
            self.history.set_history(messages)

        self.tool_set = tool_set or ToolSet()
        self._models = models or [{"id": "model-a"}]

    def chat(self, message: str | list[dict[str, Any]] | None = None) -> str:
        if message:
            if isinstance(message, str):
                self.history.add_message("user", message)
            else:
                self.history.add_messages(message)

        user_messages = [m.get("content") for m in self.history.get_messages() if m.get("role") == "user"]
        self.last_prompt = str(user_messages[-1]) if user_messages else None

        response = "ok"
        self.last_response = response
        self.history.add_message("assistant", response)
        self.history.commit()
        return response

    def new_session(self, preserve_alias: bool = False, preserve_id: bool = False) -> None:
        if not preserve_id:
            self.session_id = None
        if not preserve_alias:
            self.session_alias = None
        self.session_title = None
        self.last_prompt = None
        self.last_response = None
        self.history.clear()

    def import_state(self, other: ChatSessionDouble) -> None:
        self.session_id = other.session_id
        self.session_alias = other.session_alias
        self.session_title = other.session_title
        self.last_prompt = other.last_prompt
        self.last_response = other.last_response
        self.history.set_history(list(other.history.get_messages()))

    def list_models(self, *, ignore_errors: bool = False) -> list[dict[str, Any]] | None:
        return list(self._models)

    def save_to_file(self, filename: str) -> None:
        payload = {
            "id": self.session_id,
            "alias": self.session_alias,
            "title": self.session_title,
            "history": self.history.get_messages(),
        }
        Path(filename).write_text(json.dumps(payload))

    def load_from_file(self, filename: str) -> None:
        payload = json.loads(Path(filename).read_text())
        self.session_alias = payload.get("alias")
        self.session_title = payload.get("title")
        self.history.set_history(payload.get("history") or [])


class SessionManagerDouble:
    """In-memory replacement for ``lair.sessions.SessionManager`` used in tests."""

    def __init__(self) -> None:
        self.sessions: dict[int, dict[str, Any]] = {}
        self.aliases: dict[str, int] = {}
        self._next_session_id = 1

    def _serialize(self, chat_session: ChatSessionDouble) -> dict[str, Any]:
        return {
            "id": chat_session.session_id,
            "alias": chat_session.session_alias,
            "title": chat_session.session_title,
            "session": {"mode": lair.config.active_mode, "model_name": str(lair.config.get("model.name"))},
            "history": list(chat_session.history.get_messages()),
        }

    def add_from_chat_session(self, chat_session: ChatSessionDouble) -> None:
        if chat_session.session_id is None:
            chat_session.session_id = self._next_session_id
            self._next_session_id += 1

        snapshot = self._serialize(chat_session)
        session_id = int(snapshot["id"])

        previous = self.sessions.get(session_id)
        if previous and previous.get("alias") and previous.get("alias") != snapshot.get("alias"):
            self.aliases.pop(str(previous["alias"]), None)

        self.sessions[session_id] = snapshot
        if chat_session.session_alias:
            self.aliases[chat_session.session_alias] = session_id

    def refresh_from_chat_session(self, chat_session: ChatSessionDouble) -> None:
        self.add_from_chat_session(chat_session)

    def _resolve_session_id(self, id_or_alias: str | int) -> int | None:
        if isinstance(id_or_alias, int):
            return id_or_alias if id_or_alias in self.sessions else None

        resolved_alias = self.aliases.get(id_or_alias)
        if resolved_alias is not None:
            return resolved_alias

        if id_or_alias.isdigit():
            session_id = int(id_or_alias)
            return session_id if session_id in self.sessions else None

        return None

    def get_session_id(self, id_or_alias: str | int, raise_exception: bool = True) -> int | None:
        session_id = self._resolve_session_id(id_or_alias)
        if session_id is not None:
            return session_id

        if raise_exception:
            raise lair.sessions.UnknownSessionException(f"Unknown session: {id_or_alias}")
        return None

    def switch_to_session(self, id_or_alias: str | int, chat_session: ChatSessionDouble) -> None:
        session_id = self.get_session_id(id_or_alias)
        if session_id is None:
            raise lair.sessions.UnknownSessionException(f"Unknown session: {id_or_alias}")

        snapshot = self.sessions[session_id]
        chat_session.session_id = session_id
        chat_session.session_alias = snapshot.get("alias")
        chat_session.session_title = snapshot.get("title")
        chat_session.history.set_history(list(snapshot.get("history") or []))

    def all_sessions(self):
        return iter(self.sessions.values())

    def is_alias_available(self, alias: str | None) -> bool:
        if alias is None:
            return True
        if alias.isdigit():
            return False
        return alias not in self.aliases

    def set_alias(self, session_id: int, new_alias: str | None) -> None:
        snapshot = self.sessions.get(session_id)
        if snapshot is None:
            raise lair.sessions.UnknownSessionException(f"Unknown session: {session_id}")

        previous_alias = snapshot.get("alias")
        if previous_alias:
            self.aliases.pop(str(previous_alias), None)

        if new_alias:
            if not self.is_alias_available(new_alias):
                raise ValueError("Alias is unavailable")
            self.aliases[new_alias] = session_id

        snapshot["alias"] = new_alias

    def set_title(self, session_id: int, new_title: str | None) -> None:
        snapshot = self.sessions.get(session_id)
        if snapshot is None:
            raise lair.sessions.UnknownSessionException(f"Unknown session: {session_id}")
        snapshot["title"] = new_title

    def delete_sessions(self, session_list) -> None:
        if "all" in session_list:
            self.sessions.clear()
            self.aliases.clear()
            return

        for id_or_alias in session_list:
            session_id = self.get_session_id(id_or_alias)
            if session_id is None:
                continue

            snapshot = self.sessions.pop(session_id, None)
            if snapshot and snapshot.get("alias"):
                self.aliases.pop(str(snapshot["alias"]), None)

    def get_next_session_id(self, session_id: int | None) -> int | None:
        if not self.sessions:
            return None
        session_ids = sorted(self.sessions.keys())
        if session_id is None:
            return session_ids[0]
        if session_id not in self.sessions:
            return session_ids[0]
        current_index = session_ids.index(session_id)
        return session_ids[(current_index + 1) % len(session_ids)]

    def get_previous_session_id(self, session_id: int | None) -> int | None:
        if not self.sessions:
            return None
        session_ids = sorted(self.sessions.keys())
        if session_id is None:
            return session_ids[-1]
        if session_id not in self.sessions:
            return session_ids[-1]
        current_index = session_ids.index(session_id)
        return session_ids[(current_index - 1) % len(session_ids)]


class HistoryRecorder:
    """Compatibility shim kept for older tests that import it."""

    def __init__(self) -> None:
        self.records: list[tuple[str, Any]] = []


class RecordingReporting:
    """Minimal reporting API that records calls for assertions."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, Any]] = []
        self.tables: list[tuple[str, Any]] = []

    def style(self, text: str, *, style: str | None = None, **kwargs: object) -> str:
        if style:
            return f"{style}:{text}"
        return text

    def system_message(self, message: str, **kwargs: object) -> None:
        self.messages.append(("system", message))

    def user_error(self, message: str, **kwargs: object) -> None:
        self.messages.append(("error", message))

    def user_warning(self, message: str, **kwargs: object) -> None:
        self.messages.append(("warning", message))

    def error(self, message: str, **kwargs: object) -> None:
        self.messages.append(("error", message))

    def message(self, message: dict[str, Any], **kwargs: object) -> None:
        self.messages.append(("message", message))

    def llm_output(self, message: str, **kwargs: object) -> None:
        self.messages.append(("llm", message))

    def print_rich(self, *args: object, **kwargs: object) -> None:
        rendered = " ".join(str(part) for part in args)
        self.messages.append(("rich", rendered))

    def print_highlighted_json(self, json_str: str) -> None:
        self.messages.append(("json", json_str))

    def table_system(self, rows: list[list[Any]], **kwargs: object) -> None:
        self.tables.append(("table", rows))

    def table_from_dicts_system(self, rows_of_dicts: list[dict[str, Any]], **kwargs: object) -> None:
        self.tables.append(("dict", rows_of_dicts))

    def color_bool(
        self,
        value: bool,
        *,
        true_str: str = "true",
        false_str: str = "false",
        false_style: str | None = None,
        **kwargs: object,
    ) -> str:
        if value:
            return true_str
        if false_style:
            return f"{false_style}:{false_str}"
        return false_str
