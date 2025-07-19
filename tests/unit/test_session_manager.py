import importlib
import sys
import pytest
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
