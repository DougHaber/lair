import os
import json

import lmdb

import lair
import lair.util
import lair.sessions.serializer
from lair.logging import logger


# For clarity:
#   A `chat_session` is a ChatSession object
#   A `session` is a serialized session dict from lair.sessions.serializer


class UnknownSessionException(Exception):
    pass


class SessionManager:

    def __init__(self):
        self.database_path = os.path.expanduser(lair.config.get('database.sessions.path'))
        self.env = lmdb.open(self.database_path,
                             map_size=lair.config.get('database.sessions.size'))
        self.ensure_correct_map_size()
        self.prune_empty()  # TODO: refresh must repopulate or we can't remove open ones

    def ensure_correct_map_size(self):
        configured_size = lair.config.get('database.sessions.size')
        with self.env.begin():
            info = self.env.info()
            current_size = info['map_size']

        if configured_size and configured_size != current_size:
            with self.env.begin(write=True):
                self.env.set_mapsize(configured_size)

    def prune_empty(self):
        session_ids_to_delete = []

        for session in self.all_sessions():
            if len(session['history']) == 0:
                session_ids_to_delete.append(session['id'])

        with self.env.begin(write=True) as txn:
            for session_id in session_ids_to_delete:
                self.delete_session(session_id, txn=txn)

        logger.debug("SessionManager(): prune_empty() removed {len(session_ids_to_delete)} empty sessions")

    def _get_next_session_id(self):
        with self.env.begin() as txn:
            cursor = txn.cursor()
            prefix = b'session:'
            session_id = 1

            if cursor.set_range(prefix):
                for key, _ in cursor:
                    if not key.startswith(prefix):
                        break

                    current_id = int(key[len(prefix):].decode())  # Convert from zero-padded string
                    if current_id > session_id:
                        break

                    session_id = current_id + 1

            return session_id

    def get_session_id(self, id_or_alias):
        with self.env.begin() as txn:
            session_id = txn.get(f'alias:{id_or_alias}'.encode())
            if session_id:
                return int(session_id.decode())

            session_id = txn.get(f'session:{lair.util.safe_int(id_or_alias):08d}'.encode())
            if session_id:
                return int(id_or_alias)

        raise UnknownSessionException(f"Unknown session: {id_or_alias}")

    def all_sessions(self):
        with self.env.begin() as txn:
            cursor = txn.cursor()
            prefix = 'session:'.encode()
            if cursor.set_range(prefix):
                for key, value in cursor:
                    if not key.startswith(prefix):
                        break  # Stop once keys are no longer prefixed with 'session:'

                    yield json.loads(value.decode())

    def refresh_from_chat_session(self, chat_session):
        session = lair.sessions.serializer.session_to_dict(chat_session)
        session_id = session['id']
        with self.env.begin(write=True) as txn:
            prev_session_data = txn.get(f'session:{session_id:08d}'.encode())
            prev_session = json.loads(prev_session_data.decode())
            prev_alias = prev_session.get('alias')

            if prev_alias and prev_alias != chat_session.session_alias:
                txn.delete(f'alias:{prev_alias}'.encode())

            txn.put(f'session:{session_id:08d}'.encode(), json.dumps(session).encode())
            if chat_session.session_alias:
                txn.put(f'alias:{chat_session.session_alias}'.encode(), str(session_id).encode())

    def add_from_chat_session(self, chat_session):
        if chat_session.session_id is None:
            chat_session.session_id = self._get_next_session_id()

        session = lair.sessions.serializer.session_to_dict(chat_session)
        with self.env.begin(write=True) as txn:
            txn.put(f'session:{chat_session.session_id:08d}'.encode(),
                    json.dumps(session).encode())
            if chat_session.session_alias:
                txn.put(f'alias:{chat_session.session_alias}'.encode(),
                        str(chat_session.session_id).encode())

    def delete_session(self, id_or_alias, txn=None):
        session_id = self.get_session_id(id_or_alias)
        should_commit = txn is None  # Track if we need to start a transaction

        if should_commit:
            txn = self.env.begin(write=True)  # Create a new transaction if none is provided

        try:
            session_data = txn.get(f'session:{session_id:08d}'.encode())
            if session_data:
                session = json.loads(session_data.decode())

                alias = session.get('alias')
                if alias:
                    txn.delete(f'alias:{alias}'.encode())

                txn.delete(f'session:{session_id:08d}'.encode())
                logger.debug(f"SessionManager(): delete_session({session_id})")

            if should_commit:
                txn.commit()  # Commit only if we started the transaction
        except Exception:
            if should_commit:
                txn.abort()  # Abort if we started the transaction and something went wrong
            raise

    # def delete_session(self, id_or_alias):
    #     session_id = self.get_session_id(id_or_alias)
    #     with self.env.begin(write=True) as txn:
    #         session_data = txn.get(f'session:{session_id:08d}'.encode())
    #         session = json.loads(session_data.decode())

    #         alias = session.get('alias')
    #         if alias:
    #             txn.delete(f'alias:{alias}'.encode())

    #         txn.delete(f'session:{session_id:08d}'.encode())
    #         logger.debug("SessionManager(): delete_session({session_id})")

    def switch_to_session(self, id_or_alias, chat_session):
        session_id = self.get_session_id(id_or_alias)
        with self.env.begin() as txn:
            logger.debug("SessionManager(): switch_to_session({session_id})")
            session_data = txn.get(f'session:{session_id:08d}'.encode())
            session = json.loads(session_data.decode())
            lair.sessions.serializer.update_session_from_dict(chat_session, session)

    def set_alias(self, id_or_alias, new_alias):
        session_id = self.get_session_id(id_or_alias)

        with self.env.begin(write=True) as txn:
            session_data = txn.get(f'session:{session_id:08d}'.encode())
            session = json.loads(session_data.decode())

            prev_alias = session.get('alias')
            if prev_alias is not None:
                txn.delete(f'alias:{prev_alias}'.encode())

            session['alias'] = new_alias
            txn.put(f'session:{session_id:08d}'.encode(), json.dumps(session).encode())
            txn.put(f'alias:{new_alias}'.encode(), str(session_id).encode())

    def get_session_dict(self, id_or_alias):
        session_id = self.get_session_id(id_or_alias)
        with self.env.begin() as txn:
            session_data = txn.get(f'session:{session_id:08d}'.encode())
            return json.loads(session_data.decode())

        return None
