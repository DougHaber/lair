import os
import time
import shutil
import lair
import prompt_toolkit
from tests.test_chat_interface_extended import make_interface


def setup_interface(monkeypatch):
    # reuse extended make_interface but also stub run_in_terminal to run callback immediately
    ci = make_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit.application, "run_in_terminal", lambda f: f())
    return ci


def test_flash_and_toolbar(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", True)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((10, 20)))
    monkeypatch.setattr(time, "time", lambda: 0)
    ci._flash("1234567890abc", duration=1)
    monkeypatch.setattr(time, "time", lambda: 0.5)
    bar = ci._generate_toolbar()
    assert bar.value == "<bottom-toolbar.flash>1234567890</bottom-toolbar.flash>"


def test_toolbar_disabled(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", False)
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((5, 20)))
    bar = ci._generate_toolbar()
    assert "<bottom-toolbar.off>" in bar.value


def test_toolbar_error_disables(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.set("chat.enable_toolbar", True)
    lair.config.active["chat.toolbar_template"] = "{missing}"
    monkeypatch.setattr(shutil, "get_terminal_size", lambda: os.terminal_size((5, 20)))
    monkeypatch.setattr(time, "time", lambda: 10)
    bar = ci._generate_toolbar()
    assert bar == ""
    assert lair.config.get("chat.enable_toolbar") is False


def test_generate_toolbar_flags_and_prompt(monkeypatch):
    ci = setup_interface(monkeypatch)
    lair.config.active.update(
        {
            "chat.multiline_input": True,
            "style.render_markdown": False,
            "tools.enabled": True,
            "chat.verbose": False,
            "style.word_wrap": True,
            "chat.prompt_template": "{session_id}:{session_alias}:{model}:{mode}:{flags}",
        }
    )
    ci.chat_session.session_alias = "al"
    flags = ci._generate_toolbar_template_flags()
    assert flags == (
        "<flag.on>L</flag.on><flag.off>m</flag.off><flag.on>T</flag.on><flag.off>v</flag.off><flag.on>W</flag.on>"
    )
    prompt = ci._generate_prompt()
    assert f"{ci.chat_session.session_id}:al" in prompt.value


def test_get_default_switch_session_id(monkeypatch):
    ci = setup_interface(monkeypatch)
    first = ci.chat_session.session_id
    ci._new_chat_session()
    second = ci.chat_session.session_id
    assert second != first
    ci.last_used_session_id = first
    assert ci._get_default_switch_session_id() == first
    ci.last_used_session_id = 99
    assert ci._get_default_switch_session_id() == first


def test_handle_session_set_alias_and_title(monkeypatch):
    ci = setup_interface(monkeypatch)
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "alias")
    ci._handle_session_set_alias()
    assert ci.chat_session.session_alias == "alias"
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "alias")
    ci._handle_session_set_alias()
    assert ("error", "ERROR: That alias is unavailable") in ci.reporting.messages
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "123")
    ci._handle_session_set_alias()
    assert ("error", "ERROR: Aliases may not be integers") in ci.reporting.messages
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "title")
    ci._handle_session_set_title()
    assert ci.session_manager.sessions[ci.chat_session.session_id]["title"] == "title"


def test_handle_session_switch(monkeypatch):
    ci = setup_interface(monkeypatch)
    start = ci.chat_session.session_id
    ci._new_chat_session()
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "")
    ci._handle_session_switch()
    assert ci.chat_session.session_id == start
    monkeypatch.setattr(prompt_toolkit, "prompt", lambda *a, **k: "unknown")
    original = ci.session_manager.switch_to_session

    def fake_switch(id_or_alias, chat_session):
        if id_or_alias == "unknown":
            raise lair.sessions.UnknownSessionError("Unknown")
        return original(id_or_alias, chat_session)

    monkeypatch.setattr(ci.session_manager, "switch_to_session", fake_switch)
    ci._handle_session_switch()
    assert ("error", "ERROR: Unknown session: unknown") in ci.reporting.messages
