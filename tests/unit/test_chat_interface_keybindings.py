from tests.helpers.chat_interface import make_interface


def find_handler(ci, name):
    for b in ci._get_keybindings().bindings:
        if b.handler.__name__ == name:
            return b.handler
    raise AssertionError("handler not found")


def test_keybindings_and_chat(monkeypatch):
    import lair

    ci = make_interface(monkeypatch)

    assert ci._handle_request("hello")
    assert ci.chat_session.history.num_messages() > 0

    clear = find_handler(ci, "session_clear")
    clear(None)
    assert ci.chat_session.history.num_messages() == 0

    new = find_handler(ci, "session_new")
    new(None)
    first = ci.chat_session.session_id
    new(None)
    assert ci.chat_session.session_id == first + 1

    prev = find_handler(ci, "session_previous")
    prev(None)
    assert ci.chat_session.session_id == first
    nxt = find_handler(ci, "session_next")
    nxt(None)
    assert ci.chat_session.session_id == first + 1

    toggle = find_handler(ci, "toggle_word_wrap")
    current = lair.config.get("style.word_wrap")
    toggle(None)
    assert lair.config.get("style.word_wrap") != current


def test_commands(monkeypatch):
    import lair

    ci = make_interface(monkeypatch)

    ci.command_model("/model", ["newmodel"], "newmodel")
    assert lair.config.get("model.name") == "newmodel"

    orig = ci.chat_session.session_id
    ci.command_session_new("/session-new", [], "")
    new_id = ci.chat_session.session_id
    assert new_id != orig

    ci.command_session("/session", [orig], str(orig))
    assert ci.chat_session.session_id == orig

    ci.command_session_alias("/session-alias", [orig, "alias"], f"{orig} alias")
    assert ci.session_manager.get_session_id("alias") == orig

    ci.command_session_delete("/session-delete", [new_id], str(new_id))
    assert ci.session_manager.get_session_id(new_id, raise_exception=False) is None

    ci.chat_session.history.add_message("user", "a")
    ci.chat_session.history.add_message("user", "b")
    ci.command_history_slice("/history-slice", ["1:"], "1:")
    msgs = [m["content"] for m in ci.chat_session.history.get_messages()]
    assert msgs == ["b"]

    ci.command_set("/set", ["style.word_wrap", "false"], "style.word_wrap false")
    assert lair.config.get("style.word_wrap") is False

    assert ci._handle_request("/model model-a")
    assert ci._handle_request("something")
