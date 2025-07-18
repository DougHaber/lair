import sys
import subprocess

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
    cmd = [sys.executable, "-c", STUB_SCRIPT]
    cmd.extend(args)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def test_help_command():
    result = run_command("--help")
    assert "usage:" in result.stdout.lower()
    assert result.returncode == 0


def test_chat_help():
    result = run_command("chat", "--help")
    assert "allow-create-session" in result.stdout.lower()
    assert result.returncode == 0
