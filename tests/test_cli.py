import sys
import subprocess


def run_command(*args):
    cmd = [sys.executable, '-c', 'import lair.cli.run as run; run.start()']
    cmd.extend(args)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def test_help_command():
    result = run_command('--help')
    assert 'usage:' in result.stdout.lower()
    assert result.returncode == 0


def test_chat_help():
    result = run_command('chat', '--help')
    assert 'allow-create-session' in result.stdout.lower()
    assert result.returncode == 0
