from __future__ import annotations

import importlib

import lair
import lair.reporting
import lair.sessions
from prompt_toolkit import application

from tests.helpers import ChatSessionDouble, RecordingReporting, SessionManagerDouble, stub_optional_dependencies


def make_interface(monkeypatch):
    """Return a fully patched :class:`lair.cli.chat_interface.ChatInterface` for tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture used to replace runtime dependencies.

    Returns:
        A ``ChatInterface`` instance wired to lightweight doubles so tests can
        exercise command logic without touching external systems.
    """
    stub_optional_dependencies()

    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda target: ChatSessionDouble())
    monkeypatch.setattr(lair.sessions, "SessionManager", SessionManagerDouble)
    monkeypatch.setattr(lair.reporting, "Reporting", RecordingReporting)
    monkeypatch.setattr(application, "run_in_terminal", lambda func, *args, **kwargs: func())

    lair.config.set("chat.history_file", None)

    ci_module = importlib.import_module("lair.cli.chat_interface")
    importlib.reload(ci_module)
    return ci_module.ChatInterface()
