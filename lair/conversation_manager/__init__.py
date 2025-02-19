from .openai_conversation_manager import OpenAIConversationManager


def get_conversation_manager(session_type, *args, **kwargs):
    if session_type == 'openai_chat':
        return OpenAIConversationManager(*args, **kwargs)
    else:
        raise ValueError("Unknown session type: %s" % session_type)
