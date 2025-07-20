import contextlib
import io
import os
import runpy
import sys
import tempfile
from dataclasses import dataclass

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


@dataclass
class Completed:
    stdout: str
    returncode: int


def run_command(*args):
    argv_backup = sys.argv
    import lair.cli.run as run_module

    orig_init = getattr(run_module, "init_subcommands", None)
    sys.argv = [sys.executable, *args]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp:
                    temp.write(STUB_SCRIPT.encode())
                    path = temp.name
                try:
                    runpy.run_path(path, run_name="__main__")
                    returncode = 0
                finally:
                    os.unlink(path)
            except SystemExit as exc:
                returncode = exc.code if isinstance(exc.code, int) else 1
            finally:
                if orig_init is not None:
                    run_module.init_subcommands = orig_init
    finally:
        sys.argv = argv_backup
    return Completed(stdout=stdout.getvalue() + stderr.getvalue(), returncode=returncode)


def test_help_command():
    result = run_command("--help")
    assert "usage:" in result.stdout.lower()
    assert result.returncode == 0


def test_chat_help():
    result = run_command("chat", "--help")
    assert "allow-create-session" in result.stdout.lower()
    assert result.returncode == 0
