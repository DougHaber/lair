"""Helper functions for serializing and persisting chat sessions."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import lair

if TYPE_CHECKING:
    from .base_chat_session import BaseChatSession


def session_to_dict(chat_session: BaseChatSession) -> dict[str, object]:
    """Convert a chat session into a dictionary representation.

    Args:
        chat_session: The session instance to serialize.

    Returns:
        dict[str, object]: The serialized session state.

    """
    return {
        "version": "0.2",
        "settings": lair.config.get_modified_config(),
        "id": chat_session.session_id,
        "alias": chat_session.session_alias,
        "title": chat_session.session_title,
        "session": {
            "mode": lair.config.active_mode,
            "model_name": lair.config.get("model.name"),
            "last_prompt": chat_session.last_prompt,
            "last_response": chat_session.last_response,
        },
        "history": chat_session.history.get_messages(),
    }


def save(chat_session: BaseChatSession, filename: str) -> None:
    """Write a serialized chat session to disk.

    Args:
        chat_session: The session instance to save.
        filename: Path to the destination file.

    """
    with open(filename, "w") as state_file:
        state = session_to_dict(chat_session)
        state_file.write(json.dumps(state))


def _load__v0_2(chat_session: BaseChatSession, state: dict[str, Any]) -> None:
    """Load session state from version 0.2 format."""
    lair.config.change_mode(state["session"]["mode"])
    lair.config.update(state["settings"])
    chat_session.last_prompt = state["session"]["last_prompt"]
    chat_session.last_response = state["session"]["last_response"]
    chat_session.session_id = state["id"]
    chat_session.session_alias = state["alias"]
    chat_session.session_title = state["title"]
    chat_session.history.set_history(state["history"])


def update_session_from_dict(chat_session: BaseChatSession, state: dict[str, Any]) -> None:
    """Update an existing session from a serialized dictionary.

    Args:
        chat_session: The session instance to update.
        state: The serialized session state.

    Raises:
        Exception: If the state version is missing or unsupported.

    """
    if "version" not in state:
        raise Exception("Session state is missing 'version'")
    elif state["version"] == "0.2":
        _load__v0_2(chat_session, state)
    elif state["version"] == "0.1":
        raise Exception("Importing sessions from v0.1 format is no longer supported.")
    else:
        raise Exception(f"Session state uses unknown version: {state['version']}")


def load(chat_session: BaseChatSession, filename: str) -> None:
    """Load a chat session from disk.

    Args:
        chat_session: The session instance to populate.
        filename: Path to the file containing serialized state.

    """
    with open(filename) as state_file:
        contents = state_file.read()
        state = json.loads(contents)

    update_session_from_dict(chat_session, state)
