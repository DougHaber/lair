from .openai_chat_session import OpenAIChatSession
from .session_manager import SessionManager, UnknownSessionError


def get_chat_session(session_type, *args, **kwargs):
    if session_type == "openai_chat":
        return OpenAIChatSession(*args, **kwargs)
    else:
        raise ValueError("Unknown session type: %s" % session_type)


__all__ = [
    "OpenAIChatSession",
    "SessionManager",
    "UnknownSessionError",
    "get_chat_session",
]
