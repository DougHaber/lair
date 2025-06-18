import argparse
import types
import pytest

import lair
import lair.cli.run as run


class DummyCommand:
    def __init__(self, parser):
        self.called = False

    def run(self, args):
        self.called = True


def make_loader(modules):
    class Loader:
        def __init__(self):
            self.modules = modules

        def load_modules_from_path(self, path):
            self.loaded_path = path

    return Loader


def test_init_subcommands_success(monkeypatch):
    modules = {"chat": {"description": "desc", "class": DummyCommand, "aliases": ["alias"]}}
    loader_cls = make_loader(modules)
    monkeypatch.setattr(run.lair.module_loader, "ModuleLoader", loader_cls)
    monkeypatch.setattr(run.lair.util, "get_lib_path", lambda p: "/unused")
    parser = argparse.ArgumentParser()

    commands = run.init_subcommands(parser)

    assert "chat" in commands
    assert "alias" in commands
    assert commands["chat"] is commands["alias"]
    assert isinstance(commands["chat"], DummyCommand)


def test_init_subcommands_failure(monkeypatch):
    class BadCommand:
        def __init__(self, parser):
            raise RuntimeError("boom")

    modules = {"bad": {"description": "d", "class": BadCommand, "aliases": []}}
    loader_cls = make_loader(modules)
    monkeypatch.setattr(run.lair.module_loader, "ModuleLoader", loader_cls)
    monkeypatch.setattr(run.lair.util, "get_lib_path", lambda p: "/unused")
    parser = argparse.ArgumentParser()
    with pytest.raises(Exception) as exc:
        run.init_subcommands(parser)
    assert "Failed to load module 'bad'" in str(exc.value)


def test_set_config_from_arguments_none(monkeypatch):
    events = []
    monkeypatch.setattr(lair.events, "fire", lambda e: events.append(e))
    run.set_config_from_arguments(None)
    run.set_config_from_arguments([])
    assert events == []


def test_start_normal(monkeypatch):
    args = argparse.Namespace(
        debug=True,
        disable_color=True,
        force_color=False,
        mode="mymode",
        model="themodel",
        set=["k=v"],
        subcommand="cmd",
    )
    cmd = DummyCommand(None)
    monkeypatch.setattr(run, "parse_arguments", lambda: (args, cmd))
    monkeypatch.setattr(run.lair.logging, "init_logging", lambda: None)
    called = {}
    monkeypatch.setattr(run.lair.config, "change_mode", lambda m: called.setdefault("mode", m))
    monkeypatch.setattr(run, "set_config_from_arguments", lambda s: called.setdefault("set", s))
    monkeypatch.setattr(run.lair.config, "set", lambda k, v: called.setdefault("model", (k, v)))

    class FakeReporting:
        def __init__(self, disable_color=False, force_color=False):
            called["reporting"] = (disable_color, force_color)

    monkeypatch.setattr(run.lair.reporting, "Reporting", FakeReporting)
    run.start()
    assert cmd.called
    assert called == {"mode": "mymode", "set": ["k=v"], "model": ("model.name", "themodel"), "reporting": (True, False)}


def test_start_keyboard_interrupt(monkeypatch):
    args = argparse.Namespace(
        debug=False, disable_color=False, force_color=False, mode=None, model=None, set=None, subcommand="cmd"
    )

    def raise_kb(args):
        raise KeyboardInterrupt

    cmd = types.SimpleNamespace(run=raise_kb)
    monkeypatch.setattr(run, "parse_arguments", lambda: (args, cmd))
    monkeypatch.setattr(run.lair.logging, "init_logging", lambda: None)
    with pytest.raises(SystemExit) as exc:
        run.start()
    assert "Received interrupt" in str(exc.value)


def test_start_exception_paths(monkeypatch):
    args = argparse.Namespace(
        debug=False, disable_color=False, force_color=False, mode=None, model=None, set=None, subcommand="cmd"
    )

    def boom(args):
        raise RuntimeError("bad")

    cmd = types.SimpleNamespace(run=boom)
    monkeypatch.setattr(run, "parse_arguments", lambda: (args, cmd))
    monkeypatch.setattr(run.lair.logging, "init_logging", lambda: None)
    monkeypatch.setattr(run.lair.util, "is_debug_enabled", lambda: False)
    monkeypatch.setattr(run.traceback, "print_exc", lambda: called.append("trace"))
    called = []
    with pytest.raises(SystemExit) as exc:
        run.start()
    assert "Enable debugging" in str(exc.value)
    assert called == []

    # Now with debug enabled -> prints traceback
    called.clear()
    monkeypatch.setattr(run.lair.util, "is_debug_enabled", lambda: True)
    with pytest.raises(SystemExit) as exc:
        run.start()
    assert exc.value.code == 1
    assert called == ["trace"]
