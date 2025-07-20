"""Manage chat session metadata in LMDB."""

from __future__ import annotations

import importlib
import json
import os
from collections.abc import Iterator, Sequence
from typing import Any

import lair
import lair.sessions.serializer
import lair.util
from lair.logging import logger

from .base_chat_session import BaseChatSession

lmdb: Any = importlib.import_module("lmdb")

# For clarity:
#   A `chat_session` is a ChatSession object
#   A `session` is a serialized session dict from lair.sessions.serializer


class UnknownSessionError(Exception):
    """Raised when a session ID or alias cannot be resolved."""


UnknownSessionException = UnknownSessionError


class SessionManager:
    """Provide an interface for storing and retrieving chat sessions."""

    def __init__(self) -> None:
        """Initialize the manager and ensure the backing store is ready."""
        self.database_path = os.path.expanduser(lair.config.get("database.sessions.path"))
        self.env = lmdb.open(self.database_path, map_size=lair.config.get("database.sessions.size"))
        self.ensure_correct_map_size()
        self.prune_empty()

    def ensure_correct_map_size(self) -> None:
        """Ensure the database map size matches the configured value."""
        configured_size = lair.config.get("database.sessions.size")
        with self.env.begin():
            info = self.env.info()
            current_size = info["map_size"]

        if configured_size and configured_size != current_size:
            with self.env.begin(write=True):
                self.env.set_mapsize(configured_size)

    def prune_empty(self) -> None:
        """Delete sessions that contain no history."""
        session_list: list[int] = []

        for session in self.all_sessions():
            if len(session["history"]) == 0:
                session_list.append(session["id"])

        self.delete_sessions(session_list)
        logger.debug(f"SessionManager(): prune_empty() removed {len(session_list)} empty sessions")

    def _get_next_session_id(self) -> int:
        """Return the next available numeric session identifier."""
        with self.env.begin() as txn:
            cursor = txn.cursor()
            prefix = b"session:"
            session_id = 1

            if cursor.set_range(prefix):
                for key, _ in cursor:
                    if not key.startswith(prefix):
                        break

                    current_id = int(key[len(prefix) :].decode())  # Convert from zero-padded string
                    if current_id > session_id:
                        break

                    session_id = current_id + 1

            return session_id

    def get_session_id(self, id_or_alias: str | int, raise_exception: bool = True) -> int | None:
        """Resolve a session ID or alias.

        Args:
            id_or_alias: Numeric ID or alias string to look up.
            raise_exception: Whether to raise :class:`UnknownSessionError` when the session
                cannot be resolved.

        Returns:
            int | None: The resolved session ID, or ``None`` if ``raise_exception`` is ``False`` and
                the session does not exist.

        """
        with self.env.begin() as txn:
            session_id = txn.get(f"alias:{id_or_alias}".encode())
            if session_id:
                return int(session_id.decode())

            session_id_int = lair.util.safe_int(id_or_alias)
            if isinstance(session_id_int, int):
                session_id = txn.get(f"session:{session_id_int:08d}".encode())
                if session_id:
                    return int(id_or_alias)

        if raise_exception:
            raise UnknownSessionError(f"Unknown session: {id_or_alias}")
        else:
            return None

    def all_sessions(self) -> Iterator[dict[str, Any]]:
        """Iterate over all stored sessions."""
        with self.env.begin() as txn:
            cursor = txn.cursor()
            prefix = b"session:"
            if cursor.set_range(prefix):
                for key, value in cursor:
                    if not key.startswith(prefix):
                        break  # Stop once keys are no longer prefixed with 'session:'

                    yield json.loads(value.decode())

    def get_next_session_id(self, session_id: int) -> int | None:
        """Return the identifier of the session after ``session_id``."""
        sessions = list(self.all_sessions())
        if len(sessions) > 0:
            for i, session in enumerate(sessions):
                if session["id"] == session_id:
                    return sessions[(i + 1) % len(sessions)]["id"]

            return sessions[0]["id"]
        else:
            return None  # No sessions found

    def get_previous_session_id(self, session_id: int) -> int | None:
        """Return the identifier of the session before ``session_id``."""
        sessions = list(self.all_sessions())
        if len(sessions) > 0:
            for i, session in enumerate(sessions):
                if session["id"] == session_id:
                    return sessions[(i - 1) % len(sessions)]["id"]

            return sessions[0]["id"]
        else:
            return None  # No sessions found

    def refresh_from_chat_session(self, chat_session: BaseChatSession) -> None:
        """Update a stored session from the given chat session."""
        if not chat_session.session_id:
            self.add_from_chat_session(chat_session)
            return

        session = lair.sessions.serializer.session_to_dict(chat_session)
        session_id = session["id"]
        logger.debug(f"SessionManager(): refresh_from_chat_session({session_id})")
        with self.env.begin() as txn:
            prev_session_data = txn.get(f"session:{session_id:08d}".encode())
            if not prev_session_data:  # If the session doesn't exist, create it
                self.add_from_chat_session(chat_session)
                return

        with self.env.begin(write=True) as txn:
            prev_session = json.loads(prev_session_data.decode())
            prev_alias = prev_session.get("alias")

            if prev_alias and prev_alias != chat_session.session_alias:
                txn.delete(f"alias:{prev_alias}".encode())

            txn.put(f"session:{session_id:08d}".encode(), json.dumps(session).encode())
            if chat_session.session_alias:
                txn.put(f"alias:{chat_session.session_alias}".encode(), str(session_id).encode())

    def add_from_chat_session(self, chat_session: BaseChatSession) -> None:
        """Persist ``chat_session`` as a new session if needed."""
        if chat_session.session_id is None:
            object.__setattr__(chat_session, "session_id", self._get_next_session_id())

        session = lair.sessions.serializer.session_to_dict(chat_session)
        with self.env.begin(write=True) as txn:
            txn.put(f"session:{chat_session.session_id:08d}".encode(), json.dumps(session).encode())
            if chat_session.session_alias:
                txn.put(f"alias:{chat_session.session_alias}".encode(), str(chat_session.session_id).encode())

    def delete_session(self, id_or_alias: str | int, txn: lmdb.Transaction | None = None) -> None:
        """Delete a session.

        Args:
            id_or_alias: The numeric ID or alias of the session to delete.
            txn: Optional existing LMDB transaction to use.

        """
        session_id = self.get_session_id(id_or_alias)
        should_commit = txn is None  # Track if we need to start a transaction

        if should_commit:
            txn = self.env.begin(write=True)  # Create a new transaction if none is provided

        if txn is None:
            raise RuntimeError("Transaction is unexpectedly None")

        try:
            session_data = txn.get(f"session:{session_id:08d}".encode())
            session = json.loads(session_data.decode())

            alias = session.get("alias")
            if alias:
                txn.delete(f"alias:{alias}".encode())

            txn.delete(f"session:{session_id:08d}".encode())
            logger.debug(f"SessionManager(): delete_session({session_id})")

            if should_commit:
                txn.commit()  # Commit only if we started the transaction
        except Exception:
            if should_commit:
                txn.abort()  # Abort if we started the transaction and something went wrong
            raise

    def delete_sessions(self, session_list: Sequence[str | int]) -> None:
        """Delete multiple sessions."""
        with self.env.begin(write=True) as txn:
            if "all" in session_list:
                for session in self.all_sessions():
                    self.delete_session(session["id"], txn=txn)
            else:
                for session_id in session_list:
                    self.delete_session(session_id, txn=txn)

    def switch_to_session(self, id_or_alias: str | int, chat_session: BaseChatSession) -> None:
        """Load session data into ``chat_session``."""
        session_id = self.get_session_id(id_or_alias)
        with self.env.begin() as txn:
            logger.debug(f"SessionManager(): switch_to_session({session_id})")
            session_data = txn.get(f"session:{session_id:08d}".encode())
            session = json.loads(session_data.decode())
            lair.sessions.serializer.update_session_from_dict(chat_session, session)

    def is_alias_available(self, alias: str) -> bool:
        """Return ``True`` if ``alias`` is not already in use."""
        if isinstance(lair.util.safe_int(alias), int):
            return False

        try:
            if self.get_session_id(alias):
                return False
        except UnknownSessionError:
            return True

        return False

    def set_alias(self, id_or_alias: str | int, new_alias: str) -> None:
        """Assign ``new_alias`` to the specified session."""
        if not self.is_alias_available(new_alias):
            raise ValueError("SessionManager(): set_alias(): Alias conflict: Unable to set alias")

        session_id = self.get_session_id(id_or_alias)

        with self.env.begin(write=True) as txn:
            session_data = txn.get(f"session:{session_id:08d}".encode())
            session = json.loads(session_data.decode())

            prev_alias = session.get("alias")
            if prev_alias is not None:
                txn.delete(f"alias:{prev_alias}".encode())

            session["alias"] = new_alias
            txn.put(f"session:{session_id:08d}".encode(), json.dumps(session).encode())
            txn.put(f"alias:{new_alias}".encode(), str(session_id).encode())

    def set_title(self, id_or_alias: str | int, new_title: str) -> None:
        """Update the title of a session."""
        session_id = self.get_session_id(id_or_alias)

        with self.env.begin(write=True) as txn:
            session_data = txn.get(f"session:{session_id:08d}".encode())
            session = json.loads(session_data.decode())

            session["title"] = new_title
            txn.put(f"session:{session_id:08d}".encode(), json.dumps(session).encode())

    def get_session_dict(self, id_or_alias: str | int) -> dict[str, Any] | None:
        """Return a stored session as a dictionary."""
        session_id = self.get_session_id(id_or_alias)
        with self.env.begin() as txn:
            session_data = txn.get(f"session:{session_id:08d}".encode())
            return json.loads(session_data.decode())

        return None
