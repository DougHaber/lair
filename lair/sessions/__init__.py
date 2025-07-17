from .openai_chat_session import OpenAIChatSession
from .session_manager import SessionManager, UnknownSessionException


def get_chat_session(session_type, *args, **kwargs):
    if session_type == "openai_chat":
        return OpenAIChatSession(*args, **kwargs)
    else:
        raise ValueError(f"Unknown session type: {session_type}")


__all__ = [
    "OpenAIChatSession",
    "SessionManager",
    "UnknownSessionException",
    "get_chat_session",
]
