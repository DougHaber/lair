import contextlib
import importlib
import io
import sys
import types
from types import SimpleNamespace

STUB_MODULES = [
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
]


class Dummy:
    def __init__(self, parser):
        pass

    def run(self, args):
        pass


def run_command(*args):
    argv_backup = sys.argv
    sys.argv = ["cli", *args]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        for name in STUB_MODULES:
            mod = types.ModuleType(name)
            if name == "lair.cli.chat_interface":
                mod.ChatInterface = object
            sys.modules[name] = mod

        import lair.cli.run as run_mod

        def fake_init_subcommands(parser):
            sub = parser.add_subparsers(dest="subcommand")
            chat_parser = sub.add_parser("chat", help="Chat interface")
            chat_parser.add_argument("--allow-create-session", action="store_true")
            return {"chat": Dummy(chat_parser)}

        run_mod.init_subcommands = fake_init_subcommands
        run_mod.start()
        importlib.reload(run_mod)
    sys.argv = argv_backup
    return SimpleNamespace(stdout=buffer.getvalue(), returncode=0)


def test_help_command():
    result = run_command("--help")
    assert "usage:" in result.stdout.lower()
    assert result.returncode == 0


def test_chat_help():
    result = run_command("chat", "--help")
    assert "allow-create-session" in result.stdout.lower()
    assert result.returncode == 0
