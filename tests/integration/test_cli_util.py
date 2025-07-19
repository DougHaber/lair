import importlib
import sys
import types

import click
from click.testing import CliRunner

import lair

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


class DummySession:
    def chat(self, messages):
        self.messages = messages
        return "reply"


class DummyReporting:
    def __init__(self, outputs):
        self.outputs = outputs
        self.outputs["instance"] = self

    def llm_output(self, msg):
        self.outputs["msg"] = msg

    def print_rich(self, msg):
        self.outputs["msg"] = msg


def test_util_command_basic(monkeypatch):
    for name in STUB_MODULES:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    monkeypatch.setattr(lair.sessions, "get_chat_session", lambda *a, **k: DummySession())

    outputs = {}
    monkeypatch.setattr(lair.reporting, "Reporting", lambda *a, **k: DummyReporting(outputs))

    import lair.modules.util as util_mod

    monkeypatch.setattr(util_mod.Util, "call_llm", lambda self, *a, **k: "text")
    monkeypatch.setattr(util_mod.Util, "_get_user_messages", lambda self, a: [])
    monkeypatch.setattr(util_mod.Util, "_get_instructions", lambda self, a: "i")
    monkeypatch.setattr(util_mod.Util, "clean_response", lambda self, r: r)

    run = importlib.import_module("lair.cli.run")

    def fake_init(parser):
        sub = parser.add_subparsers(dest="subcommand")
        util_parser = sub.add_parser("util")
        return {"util": util_mod.Util(util_parser)}

    monkeypatch.setattr(run, "init_subcommands", fake_init)

    @click.command(context_settings={"ignore_unknown_options": True})
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def cli(args):
        sys.argv = ["lair"] + list(args)
        run.start()

    result = CliRunner().invoke(cli, ["util", "--instructions", "i", "--markdown"])
    assert result.exit_code == 0
    assert outputs.get("msg") == "text"
