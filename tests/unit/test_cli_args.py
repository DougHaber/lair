import importlib
import sys
import types
from unittest import mock

import pytest

import lair


def import_run():
    for name in [
        "lair.cli.chat_interface",
        "openai",
        "requests",
        "trafilatura",
        "PIL",
        "diffusers",
        "transformers",
        "torch",
        "comfy_script",
        "lair.comfy_caller",
    ]:
        mod = types.ModuleType(name)
        if name == "lair.cli.chat_interface":
            mod.ChatInterface = object
        sys.modules.setdefault(name, mod)
    return importlib.import_module("lair.cli.run")


run = import_run()


class DummyCommand:
    def __init__(self, parser):
        parser.add_argument("--dummy", action="store_true")

    def run(self, args):
        pass


def fake_init(parser):
    sub = parser.add_subparsers(dest="subcommand")
    chat_parser = sub.add_parser("chat", help="chat help")
    return {"chat": DummyCommand(chat_parser)}


def test_parse_arguments_flags(monkeypatch):
    monkeypatch.setattr(run, "init_subcommands", fake_init)
    argv = ["prog", "--debug", "--disable-color", "--force-color", "-M", "mymode", "-m", "model", "-s", "a=b", "chat"]
    with mock.patch.object(sys, "argv", argv):
        args, cmd = run.parse_arguments()
    assert args.debug is True
    assert args.disable_color is True
    assert args.force_color is True
    assert args.mode == "mymode"
    assert args.model == "model"
    assert args.set == ["a=b"]
    assert args.subcommand == "chat"
    assert isinstance(cmd, DummyCommand)


def test_parse_arguments_version(monkeypatch, capsys):
    monkeypatch.setattr(run, "init_subcommands", lambda parser: {})
    monkeypatch.setattr(lair, "version", lambda: "1.2.3")
    argv = ["prog", "--version"]
    with pytest.raises(SystemExit) as exc, mock.patch.object(sys, "argv", argv):
        run.parse_arguments()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "1.2.3" in captured.out


def test_set_config_from_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr(lair.config, "set", lambda k, v, no_event=False: calls.append((k, v, no_event)))
    monkeypatch.setattr(lair.events, "fire", lambda e: calls.append(("fire", e)))
    run.set_config_from_arguments(["foo=bar"])
    assert calls == [("foo", "bar", True), ("fire", "config.update")]


def test_set_config_from_arguments_bad(monkeypatch):
    with pytest.raises(SystemExit):
        run.set_config_from_arguments(["invalid"])


def test_parse_arguments_no_subcommand(monkeypatch):
    monkeypatch.setattr(run, "init_subcommands", fake_init)
    argv = ["prog"]
    with pytest.raises(SystemExit) as exc, mock.patch.object(sys, "argv", argv):
        run.parse_arguments()
    assert exc.value.code == 1
