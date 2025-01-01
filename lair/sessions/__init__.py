from .openai_chat_session import OpenAIChatSession


def get_session(session_type, *args, **kwargs):
    if session_type == 'openai_chat':
        return OpenAIChatSession(*args, **kwargs)
    else:
        raise ValueError("Unknown session type: %s" % session_type)
