"""Utility classes for managing and validating chat history."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from typing import Any, cast

import lair
import lair.components.history.schema
from lair.logging import logger


class ChatHistory:
    """Container for chat messages with optional rollback support."""

    ALLOWED_ROLES = {"assistant", "system", "tool", "user"}

    def __init__(self) -> None:
        """Initialize a new ``ChatHistory`` instance."""
        # This is the full non-truncated history. Truncation only occurs after commit().
        self._history: list[dict[str, Any]] = []

        # In the event that a chat attempt fails, the history needs to rollback.
        # To make this possible, the session chat() function calls commit()
        # which updates the finalized_index. In the event of a failure, a call
        # to rollback() is made, which truncates history beyond the finalized
        # index.
        self.finalized_index: int | None = None

        lair.events.subscribe("config.update", lambda d: self._validate_config(), instance=self)

        self._validate_config()

    def __copy__(self) -> ChatHistory:
        """Return a shallow copy of this history."""
        new_chat_history = ChatHistory()
        new_chat_history._history = copy.copy(self._history)
        new_chat_history.finalized_index = self.finalized_index
        return new_chat_history

    def __deepcopy__(self, memo: dict[int, Any]) -> ChatHistory:
        """Return a deep copy of this history."""
        new_chat_history = ChatHistory()
        new_chat_history._history = copy.deepcopy(self._history, memo)
        new_chat_history.finalized_index = self.finalized_index
        return new_chat_history

    def _validate_config(self) -> None:
        """Ensure ``session.max_history_length`` is valid."""
        max_length = lair.config.get("session.max_history_length")
        if max_length == 0:
            logger.warning("Invalid value for session.max_history_length. Must be greater than 0. Setting to null.")
            lair.config.active["session.max_history_length"] = None

    def add_tool_messages(self, messages: Iterable[dict[str, Any]]) -> None:
        """
        Append assistant or tool messages to the history.

        Args:
            messages: Sequence of messages from the API to add.

        Raises:
            ValueError: If a message role is not ``tool`` or ``assistant``.

        """
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

    def add_message(self, role: str, message: object, *, meta: dict[str, object] | None = None) -> None:
        """
        Append a single message to the history.

        Args:
            role: The role of the message sender.
            message: The message content.
            meta: Optional additional metadata to store.

        Raises:
            ValueError: If ``role`` is invalid.

        """
        if role == "tool":
            raise ValueError("add_message(): Role of tool is invalid. Use add_tool_message()")
        elif role not in self.ALLOWED_ROLES:
            raise ValueError(f"add_message(): Unknown role: {role}")

        self._history.append(
            {
                "role": role,
                "content": message,
            }
        )

    def add_messages(self, messages: Iterable[dict[str, Any]]) -> None:
        """Append multiple messages to the history."""
        for message in messages:
            self.add_message(message["role"], message.get("content"))

    def num_messages(self) -> int:
        """Return the number of stored messages."""
        return len(self._history)

    def get_messages(self, *, extra_messages: Iterable[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Return the message history, truncating as necessary."""
        max_length_obj = lair.config.get("session.max_history_length") or 0
        max_length = cast(int, max_length_obj)

        if extra_messages is None:
            return self._history[-max_length:]
        else:
            return self._history[-max_length:] + list(extra_messages)

    def get_messages_as_jsonl_string(self) -> str:
        """Return the history encoded as a JSON Lines string."""
        messages = self.get_messages()
        return "\n".join(json.dumps(message) for message in messages)

    def set_history(self, messages: list[dict[str, Any]]) -> None:
        """Replace history with the provided messages."""
        lair.components.history.schema.validate_messages(messages)

        self._history = messages
        self._truncate()
        self.finalized_index = len(self._history)

    def clear(self) -> None:
        """Clear the stored history."""
        self._history = []
        self.finalized_index = None

    def _truncate(self) -> None:
        """Trim the history if ``session.max_history_length`` is set."""
        # This should only be called by commit() or set_history()
        # The history normally is not stored truncated otherwise so that
        # it is possible to rollback to the previous state.
        max_length_obj = lair.config.get("session.max_history_length")
        if max_length_obj is not None:
            self._history = self._history[-cast(int, max_length_obj) :]

    def commit(self) -> None:
        """Mark the current history as being finalized."""
        self.finalized_index = len(self._history)
        logger.debug(f"Committing history (finalized_index={self.finalized_index})")

    def rollback(self) -> None:
        """Remove non-finalized items, typically after a chat attempt fails."""
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
