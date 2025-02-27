from .openai_chat_session import OpenAIChatSession
from .session_manager import SessionManager, UnknownSessionException


def get_chat_session(session_type, *args, **kwargs):
    if session_type == 'openai_chat':
        return OpenAIChatSession(*args, **kwargs)
    else:
        raise ValueError("Unknown session type: %s" % session_type)
