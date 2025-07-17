import io
import os
import runpy
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace

import pytest

STUB_SCRIPT = """
import sys, types
for name in [
    'lair.cli.chat_interface', 'openai', 'requests', 'trafilatura', 'PIL',
    'diffusers', 'transformers', 'torch', 'comfy_script', 'lair.comfy_caller'
]:
    mod = types.ModuleType(name)
    if name == 'lair.cli.chat_interface':
        mod.ChatInterface = object
    sys.modules[name] = mod
import lair.cli.run as run
class Dummy:
    def __init__(self, parser):
        pass
    def run(self, args):
        pass

def fake_init_subcommands(parser):
    sub = parser.add_subparsers(dest='subcommand')
    chat_parser = sub.add_parser('chat', help='Chat interface')
    chat_parser.add_argument('--allow-create-session', action='store_true')
    return {'chat': Dummy(chat_parser)}
run.init_subcommands = fake_init_subcommands
run.start()
"""


def run_command(*args):
    buffer = io.StringIO()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(STUB_SCRIPT)
        path = tmp.name
    try:
        with redirect_stdout(buffer), redirect_stderr(buffer):
            original_argv = sys.argv
            sys.argv = [path] + list(args)
            with pytest.raises(SystemExit) as exc_info:
                runpy.run_path(path, run_name="__main__")
            sys.argv = original_argv
    finally:
        os.remove(path)
    return SimpleNamespace(returncode=exc_info.value.code, stdout=buffer.getvalue())


def test_help_command():
    result = run_command("--help")
    assert "usage:" in result.stdout.lower()
    assert result.returncode == 0


def test_chat_help():
    result = run_command("chat", "--help")
    assert "allow-create-session" in result.stdout.lower()
    assert result.returncode == 0
