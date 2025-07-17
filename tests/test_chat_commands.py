import argparse
import pytest
from tests.test_chat_interface_extended import make_interface
import lair


# Helpers


def setup_ci(monkeypatch):
    ci = make_interface(monkeypatch)
    monkeypatch.setattr(lair.util, "save_file", lambda *a, **k: None)
    monkeypatch.setattr(lair.util, "edit_content_in_editor", lambda *a, **k: '[{"role":"user","content":"x"}]\n')
    monkeypatch.setattr(lair.util, "decode_jsonl", lambda s: [{"role": "user", "content": "x"}])
    monkeypatch.setattr(ci.chat_session, "load_from_file", lambda *a, **k: None)
    monkeypatch.setattr(ci.chat_session, "save_to_file", lambda *a, **k: None)
    monkeypatch.setattr(ci.chat_session.tool_set, "get_all_tools", lambda: [])
    monkeypatch.setattr(ci, "print_tools_report", lambda *a, **k: None)
    monkeypatch.setattr(ci, "print_models_report", lambda *a, **k: None)
    monkeypatch.setattr(ci, "print_config_report", lambda *a, **k: None)
    monkeypatch.setattr(ci, "print_history", lambda *a, **k: None)
    monkeypatch.setattr(ci, "print_help", lambda *a, **k: None)
    monkeypatch.setattr(ci, "_rebuild_chat_session", lambda *a, **k: None)
    orig_get = ci.session_manager.get_session_id

    def patched_get(id_or_alias, raise_exception=True):
        try:
            return orig_get(id_or_alias, raise_exception)
        except Exception as error:
            if raise_exception:
                raise lair.sessions.session_manager.UnknownSessionError("Unknown") from error
            return None

    monkeypatch.setattr(ci.session_manager, "get_session_id", patched_get)
    return ci


COMMANDS = [
    ("clear", [], ["extra"]),
    ("debug", [], ["extra"]),
    ("extract", [], ["1", "f", "x"]),
    ("help", [], ["a"]),
    ("history", [], ["a"]),
    ("history_edit", [], ["a"]),
    ("history_slice", ["1:"], []),
    ("last_prompt", [], ["a", "b"]),
    ("last_response", [], ["a", "b"]),
    ("list_models", [], ["a"]),
    ("list_settings", [], ["--bad"]),
    ("list_tools", [], ["a"]),
    ("load", [], None),
    ("messages", [], ["file1", "file2"]),
    ("mode", ["openai"], ["a", "b"]),
    ("model", ["m"], ["a", "b"]),
    ("prompt", [], None),
    ("reload_settings", [], ["a"]),
    ("save", [], None),
    ("session", [], ["a", "b"]),
    ("session_alias", ["1", "alias"], ["1", "alias", "x"]),
    ("session_delete", ["1"], []),
    ("session_new", [], ["x"]),
    ("session_title", ["1", "title"], []),
    ("set", ["style.word_wrap", "false"], ["bad.key", "val"]),
]


@pytest.mark.parametrize("name,valid_args,invalid_args", COMMANDS)
def test_chat_commands(monkeypatch, name, valid_args, invalid_args):
    ci = setup_ci(monkeypatch)
    if name in {"extract", "last_prompt", "last_response"}:
        ci.chat_session.last_response = "<answer>(data)</answer>"
        ci.chat_session.last_prompt = "prompt"
    method = getattr(ci, f"command_{name}")

    ci.reporting.messages.clear()
    method("/" + name.replace("_", "-"), valid_args, " ".join(valid_args))
    assert not any(m[0] == "error" for m in ci.reporting.messages)

    if invalid_args is not None:
        ci.reporting.messages.clear()
        if name == "list_settings":
            with pytest.raises(argparse.ArgumentError):
                method("/" + name.replace("_", "-"), invalid_args, " ".join(invalid_args))
        else:
            method("/" + name.replace("_", "-"), invalid_args, " ".join(invalid_args))
            assert any(m[0] == "error" for m in ci.reporting.messages)
