import importlib
import sys
import types

import click
from click.testing import CliRunner

STUB_MODULES = [
    "openai",
    "requests",
    "trafilatura",
    "PIL",
    "diffusers",
    "transformers",
    "torch",
    "comfy_script",
    "lair.comfy_caller",
]


def test_chat_command_invokes_interface(monkeypatch):
    for name in STUB_MODULES:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    import lair
    import lair.modules.chat as chat_mod

    run = importlib.import_module("lair.cli.run")

    class DummyCI:
        started = False
        args = None

        def __init__(self, starting_session_id_or_alias=None, create_session_if_missing=False):
            DummyCI.args = (starting_session_id_or_alias, create_session_if_missing)

        def start(self):
            DummyCI.started = True

    monkeypatch.setattr(lair.cli, "ChatInterface", DummyCI)

    def fake_init(parser):
        sub = parser.add_subparsers(dest="subcommand")
        chat_parser = sub.add_parser("chat")
        return {"chat": chat_mod.Chat(chat_parser)}

    monkeypatch.setattr(run, "init_subcommands", fake_init)

    @click.command(context_settings={"ignore_unknown_options": True})
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def cli(args):
        sys.argv = ["lair"] + list(args)
        run.start()

    result = CliRunner().invoke(cli, ["chat", "--session", "abc", "--allow-create-session"])
    assert result.exit_code == 0
    assert DummyCI.started
    assert DummyCI.args == ("abc", True)
