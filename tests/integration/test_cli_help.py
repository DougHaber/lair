import io
import os
import runpy
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

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
    argv = ["prog", *args]
    stdout = io.StringIO()
    orig_argv = sys.argv
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write(STUB_SCRIPT)
        tmp_name = tmp.name
    try:
        sys.argv = argv
        with redirect_stdout(stdout), redirect_stderr(stdout):
            try:
                runpy.run_path(tmp_name, run_name="__main__")
                code = 0
            except SystemExit as exc:
                code = exc.code
    finally:
        sys.argv = orig_argv
        os.remove(tmp_name)
    return subprocess.CompletedProcess(argv, code, stdout.getvalue(), "")


@pytest.mark.integration
def test_chat_help():
    result = run_command("chat", "--help")
    assert "allow-create-session" in result.stdout.lower()
    assert result.returncode == 0
