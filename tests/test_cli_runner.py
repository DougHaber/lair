import sys
import types
import importlib
import click
from click.testing import CliRunner

STUB_MODULES = [
    'lair.cli.chat_interface',
    'openai',
    'requests',
    'trafilatura',
    'PIL',
    'diffusers',
    'transformers',
    'torch',
    'comfy_script',
    'lair.comfy_caller',
]


def test_cli_runner_chat_command(monkeypatch):
    for name in STUB_MODULES:
        mod = types.ModuleType(name)
        if name == 'lair.cli.chat_interface':
            mod.ChatInterface = object
        monkeypatch.setitem(sys.modules, name, mod)

    import lair.reporting  # ensure submodule is registered
    run = importlib.import_module('lair.cli.run')

    called = {'flag': False}

    class Dummy:
        def __init__(self, parser):
            pass

        def run(self, args):
            called['flag'] = True

    def fake_init_subcommands(parser):
        sub = parser.add_subparsers(dest='subcommand')
        chat_parser = sub.add_parser('chat', help='chat help')
        return {'chat': Dummy(chat_parser)}

    monkeypatch.setattr(run, 'init_subcommands', fake_init_subcommands)

    @click.command(context_settings={'ignore_unknown_options': True})
    @click.argument('args', nargs=-1, type=click.UNPROCESSED)
    def cli(args):
        sys.argv = ['lair'] + list(args)
        run.start()

    runner = CliRunner()
    result = runner.invoke(cli, ['chat'])

    assert result.exit_code == 0
    assert called['flag']
