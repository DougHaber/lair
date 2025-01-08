import lair
from lair.logging import logger


class ChatHistory():
    ALLOWED_ROLES = {'assistant', 'system', 'tool', 'user'}

    def __init__(self):
        self.history = []

        # In case session.max_history_length changes, call truncate on config updates
        lair.events.subscribe('config.update', lambda d: self._truncate())

    def add_message(self, role, message):
        if role not in self.ALLOWED_ROLES:
            raise ValueError("add_message(): Unknown role: %s" % role)

        self.history.append({
            "role": role,
            "content": message,
        })
        self._truncate()

    def get_messages(self, *, extra_messages=None):
        if extra_messages is None:
            return self.history
        else:
            return self.history + extra_messages

    def set_history(self, messages):
        '''Replace history with the provided messages'''
        self.history = messages
        self._truncate()

    def clear(self):
        '''Clear the history'''
        self.history = []

    def _truncate(self):
        max_length = lair.config.get('session.max_history_length')
        if max_length == 0:
            logger.warn("Invalid value for session.max_history_length. Must be greater than 0. Setting to 1")
            max_length = 1
            lair.config.active['session.max_history_length'] = 1

        if max_length is not None:
            self.history = self.history[-max_length:]
