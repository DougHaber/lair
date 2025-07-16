import importlib
import json
import sys
import types

import pytest

import lair


class FakeCursor:
    def __init__(self, env):
        self.env = env
        self.keys = []

    def set_range(self, prefix):
        self.keys = [k for k in sorted(self.env.data) if k >= prefix]
        return bool(self.keys)

    def __iter__(self):
        for key in self.keys:
            yield key, self.env.data[key]


class FakeTxn:
    def __init__(self, env, write=False):
        self.env = env
        self.write = write

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor(self.env)

    def get(self, key):
        return self.env.data.get(key)

    def put(self, key, value):
        self.env.data[key] = value

    def delete(self, key):
        self.env.data.pop(key, None)

    def commit(self):
        pass

    def abort(self):
        pass


class FakeEnv:
    def __init__(self, path, map_size):
        self.path = path
        self.map_size = map_size
        self.data = {}

    def begin(self, write=False):
        return FakeTxn(self, write)

    def info(self):
        return {"map_size": self.map_size}

    def set_mapsize(self, size):
        self.map_size = size


def make_manager(monkeypatch, tmp_path):
    lmdb_mod = types.SimpleNamespace(open=lambda p, map_size=0: FakeEnv(p, map_size))
    monkeypatch.setitem(sys.modules, "lmdb", lmdb_mod)
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=object))
    monkeypatch.setattr(lair.events, "fire", lambda *a, **k: None)

    import lair.sessions.session_manager as sm

    importlib.reload(sm)
    monkeypatch.setattr(lair.sessions, "SessionManager", sm.SessionManager)
    lair.config.set("database.sessions.path", str(tmp_path / "db"), no_event=True)
    lair.config.set("database.sessions.size", 1024, no_event=True)
    return sm.SessionManager(), sm


class DummyHistory:
    def __init__(self):
        self.messages = []

    def get_messages(self):
        return list(self.messages)

    def set_history(self, history):
        self.messages = list(history)


class DummyChatSession:
    def __init__(self):
        self.history = DummyHistory()
        self.session_id = None
        self.session_alias = None
        self.session_title = None
        self.last_prompt = None
        self.last_response = None


def test_add_refresh_and_switch(monkeypatch, tmp_path):
    manager, mod = make_manager(monkeypatch, tmp_path)
    chat = DummyChatSession()
    chat.session_alias = "alpha"
    chat.history.messages.append({"role": "user", "content": "hi"})
    manager.add_from_chat_session(chat)
    assert chat.session_id == 1
    assert manager.get_session_id("alpha") == 1

    chat.history.messages.append({"role": "assistant", "content": "ok"})
    chat.session_alias = "beta"
    manager.refresh_from_chat_session(chat)
    with pytest.raises(mod.UnknownSessionException):
        manager.get_session_id("alpha")
    assert manager.get_session_id("beta") == 1

    chat2 = DummyChatSession()
    manager.switch_to_session("beta", chat2)
    assert chat2.session_id == 1
    assert chat2.history.get_messages()[0]["content"] == "hi"
    assert not manager.is_alias_available("beta")
    assert manager.is_alias_available("gamma")

    manager.set_alias(1, "gamma")
    assert manager.get_session_id("gamma") == 1
    manager.set_title(1, "title")
    assert manager.get_session_dict(1)["title"] == "title"


def test_next_prev_delete(monkeypatch, tmp_path):
    manager, mod = make_manager(monkeypatch, tmp_path)
    with manager.env.begin(write=True) as txn:
        txn.put(b"session:00000001", json.dumps({"id": 1, "history": []}).encode())
        txn.put(b"session:00000003", json.dumps({"id": 3, "history": []}).encode())
    assert manager._get_next_session_id() == 2

    c1 = DummyChatSession()
    manager.add_from_chat_session(c1)
    c2 = DummyChatSession()
    manager.add_from_chat_session(c2)

    assert manager.get_next_session_id(c1.session_id) == 3
    assert manager.get_previous_session_id(c2.session_id) == 3

    manager.delete_sessions([c1.session_id])
    with pytest.raises(mod.UnknownSessionException):
        manager.get_session_id(c1.session_id)

    manager.delete_sessions(["all"])
    assert manager.get_next_session_id(c2.session_id) is None
