"""Chat session initialization helpers."""

from __future__ import annotations

from lair.components.history import ChatHistory
from lair.components.tools import ToolSet

from .base_chat_session import BaseChatSession
from .openai_chat_session import OpenAIChatSession
from .session_manager import SessionManager, UnknownSessionError

# Backwards compatibility
UnknownSessionException = UnknownSessionError


def get_chat_session(
    session_type: str,
    *,
    history: ChatHistory | None = None,
    tool_set: ToolSet | None = None,
) -> BaseChatSession:
    """Instantiate a concrete chat session implementation.

    Args:
        session_type: The type of session to create. Currently only ``"openai_chat"``
            is supported.
        history: Optional chat history to attach to the session.
        tool_set: Optional tool set used by the session.

    Returns:
        BaseChatSession: The initialized chat session instance.

    Raises:
        ValueError: If ``session_type`` does not reference a known session
            implementation.

    """
    if session_type == "openai_chat":
        return OpenAIChatSession(history=history, tool_set=tool_set)

    raise ValueError(f"Unknown session type: {session_type}")


__all__ = [
    "OpenAIChatSession",
    "SessionManager",
    "UnknownSessionError",
    "UnknownSessionException",
    "get_chat_session",
]
