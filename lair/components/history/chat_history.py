import copy
import json

import lair
import lair.components.history.schema
from lair.logging import logger


class ChatHistory:
    ALLOWED_ROLES = {"assistant", "system", "tool", "user"}

    def __init__(self):
        # This is the full non-truncated history. Truncation only occurs after commit().
        self._history = []

        # In the event that a chat attempt fails, the history needs to rollback.
        # To make this possible, the session chat() function calls commit()
        # which updates the finalized_index. In the event of a failure, a call
        # to rollback() is made, which truncates history beyond the finalized
        # index.
        self.finalized_index = None

        lair.events.subscribe("config.update", lambda d: self._validate_config(), instance=self)

        self._validate_config()

    def __copy__(self):
        new_chat_history = ChatHistory()
        new_chat_history._history = copy.copy(self._history)
        new_chat_history.finalized_index = self.finalized_index
        return new_chat_history

    def __deepcopy__(self, memo):
        new_chat_history = ChatHistory()
        new_chat_history._history = copy.deepcopy(self._history, memo)
        new_chat_history.finalized_index = self.finalized_index
        return new_chat_history

    def _validate_config(self):
        max_length = lair.config.get("session.max_history_length")
        if max_length == 0:
            logger.warning("Invalid value for session.max_history_length. Must be greater than 0. Setting to null.")
            lair.config.active["session.max_history_length"] = None

    def add_tool_messages(self, messages):
        for message in messages:
            if message["role"] == "tool":
                self._history.append(
                    {
                        "role": "tool",
                        "content": message["content"] or "",
                        "tool_call_id": message["tool_call_id"],
                    }
                )
            elif message["role"] == "assistant":
                self._history.append(
                    {
                        "role": "assistant",
                        "content": message["content"] or "",
                        "refusal": message["refusal"],
                        "tool_calls": message["tool_calls"],
                    }
                )
            else:
                raise ValueError(
                    "ChatHistory(): add_tool_messages() received a message with "
                    "a role that wasn't 'tool' or 'assistant'"
                )

    def add_message(self, role, message, *, meta=None):
        if role == "tool":
            raise ValueError("add_message(): Role of tool is invalid. Use add_tool_message()")
        elif role not in self.ALLOWED_ROLES:
            raise ValueError("add_message(): Unknown role: %s" % role)

        self._history.append(
            {
                "role": role,
                "content": message,
            }
        )

    def add_messages(self, messages):
        for message in messages:
            self.add_message(message["role"], message["content"])

    def num_messages(self):
        return len(self._history)

    def get_messages(self, *, extra_messages=None):
        """
        Return the message history, truncating as necessary
        """
        max_length = lair.config.get("session.max_history_length") or 0

        if extra_messages is None:
            return self._history[-max_length:]
        else:
            return self._history[-max_length:] + extra_messages

    def get_messages_as_jsonl_string(self):
        messages = self.get_messages()
        return "\n".join(json.dumps(message) for message in messages)

    def set_history(self, messages):
        """Replace history with the provided messages"""
        lair.components.history.schema.validate_messages(messages)

        self._history = messages
        self._truncate()
        self.finalized_index = len(self._history)

    def clear(self):
        """Clear the history"""
        self._history = []
        self.finalized_index = None

    def _truncate(self):
        """
        If max_history_length is set, trim the history
        """
        # This should only be called by commit() or set_history()
        # The history normally is not stored truncated otherwise so that
        # it is possible to rollback to the previous state.
        max_length = lair.config.get("session.max_history_length")
        if max_length is not None:
            self._history = self._history[-max_length:]

    def commit(self):
        """
        Mark the current history as being finalized
        """
        self.finalized_index = len(self._history)
        logger.debug(f"Committing history (finalized_index={self.finalized_index})")

    def rollback(self):
        """
        Remove any non-finalized items in the history, such as after a chat attempt fails
        """
        if self.finalized_index is None:
            logger.debug(f"Rolling back history (finalized_index=null, removing={len(self._history)})")
            self.clear()
        else:
            logger.debug(
                "Rolling back history "
                f"(finalized_index={self.finalized_index}, "
                f"removing={len(self._history) - self.finalized_index})"
            )
            self._history = self._history[0 : self.finalized_index]
