import importlib
import sys
import pytest
import json
import lair
from lair.components.history.chat_history import ChatHistory


class DummyEnv:
    def __init__(self, path, map_size=0):
        self.path = path
        self.map_size = map_size
        self.db: dict[bytes, bytes] = {}

    def begin(self, write=False):
        return DummyTxn(self, write)

    def info(self):
        return {"map_size": self.map_size}

    def set_mapsize(self, size):
        self.map_size = size


class DummyCursor:
    def __init__(self, db):
        self.db = db
        self.items: list[tuple[bytes, bytes]] = []

    def set_range(self, prefix):
        self.items = [(k, v) for k, v in sorted(self.db.items()) if k >= prefix]
        return bool(self.items)

    def __iter__(self):
        for item in self.items:
            yield item


class DummyTxn:
    def __init__(self, env, write):
        self.env = env
        self.write = write
        self.writes: dict[bytes, bytes | None] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.write and exc_type is None:
            self.commit()
        else:
            self.abort()
        return False

    def cursor(self):
        return DummyCursor(self.env.db)

    def get(self, key):
        if key in self.writes:
            return self.writes[key]
        return self.env.db.get(key)

    def put(self, key, value):
        self.writes[key] = value

    def delete(self, key):
        self.writes[key] = None

    def commit(self):
        for k, v in self.writes.items():
            if v is None:
                self.env.db.pop(k, None)
            else:
                self.env.db[k] = v
        self.writes.clear()

    def abort(self):
        self.writes.clear()


class DummyLMDB:
    def open(self, path, map_size=0):
        return DummyEnv(path, map_size)


class DummySession:
    def __init__(self):
        self.session_id = None
        self.session_alias = None
        self.session_title = None
        self.last_prompt = None
        self.last_response = None
        self.history = ChatHistory()


def setup_manager(monkeypatch, tmp_path):
    sys.modules["lmdb"] = DummyLMDB()
    module = importlib.import_module("lair.sessions.session_manager")
    import lair.events

    lair.events._event_handlers.clear()
    lair.events._subscriptions.clear()
    lair.events._instance_subscriptions.clear()
    monkeypatch.setattr(
        lair.config,
        "active",
        {
            **lair.config.active,
            "database.sessions.path": str(tmp_path / "db"),
            "database.sessions.size": 100,
        },
    )
    module = importlib.reload(module)
    return module.SessionManager()


def test_add_and_switch(monkeypatch, tmp_path):
    manager = setup_manager(monkeypatch, tmp_path)
    s1 = DummySession()
    s1.history.add_message("user", "hi")
    manager.add_from_chat_session(s1)
    assert s1.session_id == 1

    s2 = DummySession()
    manager.add_from_chat_session(s2)
    assert s2.session_id == 2
    assert manager.get_next_session_id(1) == 2
    assert manager.get_previous_session_id(1) == 2

    manager.set_alias(1, "alias1")
    manager.set_title(2, "title2")
    assert manager.get_session_id("alias1") == 1
    assert manager.get_session_dict(2)["title"] == "title2"

    new_session = DummySession()
    manager.switch_to_session("alias1", new_session)
    assert new_session.session_id == 1
    assert new_session.history.get_messages() == s1.history.get_messages()

    manager.delete_session("alias1")
    err = importlib.import_module("lair.sessions.session_manager").UnknownSessionError
    with pytest.raises(err):
        manager.get_session_id(1)


def test_prune_and_alias_checks(monkeypatch, tmp_path):
    manager = setup_manager(monkeypatch, tmp_path)
    s_empty = DummySession()
    manager.add_from_chat_session(s_empty)
    manager.prune_empty()
    assert manager.get_session_id(1, raise_exception=False) is None

    assert not manager.is_alias_available("1")
    assert manager.is_alias_available("new")


def test_map_size_and_next_id(monkeypatch, tmp_path):
    manager = setup_manager(monkeypatch, tmp_path)
    manager.env.map_size = 50
    lair.config.set("database.sessions.size", 70, no_event=True)
    called = []

    def set_mapsize(size):
        called.append(size)
        manager.env.map_size = size

    manager.env.set_mapsize = set_mapsize
    manager.ensure_correct_map_size()
    assert called == [70] and manager.env.map_size == 70

    manager.env.db[b"session:00000001"] = b"{}"
    manager.env.db[b"session:00000003"] = b"{}"
    assert manager._get_next_session_id() == 2


def test_refresh_and_delete_all(monkeypatch, tmp_path):
    manager = setup_manager(monkeypatch, tmp_path)
    sess = DummySession()
    sess.session_id = 1
    sess.session_alias = "new"
    sess.history.add_message("user", "hi")
    manager.env.db[b"session:00000001"] = json.dumps({"id": 1, "alias": "old", "history": []}).encode()
    manager.env.db[b"alias:old"] = b"1"
    manager.refresh_from_chat_session(sess)
    assert manager.env.db[b"alias:new"] == b"1" and b"alias:old" not in manager.env.db

    new_sess = DummySession()
    manager.refresh_from_chat_session(new_sess)
    assert new_sess.session_id == 2

    s1 = DummySession()
    manager.add_from_chat_session(s1)
    s2 = DummySession()
    manager.add_from_chat_session(s2)
    assert len(list(manager.all_sessions())) >= 2
    manager.delete_sessions(["all"])
    assert list(manager.all_sessions()) == []


def test_delete_session_error_and_alias_conflict(monkeypatch, tmp_path):
    manager = setup_manager(monkeypatch, tmp_path)
    sess = DummySession()
    sess.history.add_message("user", "hi")
    manager.add_from_chat_session(sess)
    session_id = sess.session_id

    class FailTxn(DummyTxn):
        def delete(self, key):
            raise RuntimeError("boom")

        def abort(self):
            self.aborted = True
            super().abort()

    used = {}

    def begin(write=False):
        txn = FailTxn(manager.env, write) if write else DummyTxn(manager.env, False)
        if write:
            used["txn"] = txn
        return txn

    manager.env.begin = begin
    with pytest.raises(RuntimeError):
        manager.delete_session(session_id)
    assert used["txn"].aborted

    s2 = DummySession()
    manager.env.begin = lambda write=False: DummyTxn(manager.env, write)
    manager.add_from_chat_session(s2)
    manager.set_alias(session_id, "alias")
    with pytest.raises(ValueError):
        manager.set_alias(s2.session_id, "alias")
