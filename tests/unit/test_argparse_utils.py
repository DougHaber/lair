import argparse

import pytest

from lair.util.argparse import (
    ArgumentParserExitException,
    ArgumentParserHelpException,
    ErrorRaisingArgumentParser,
)


def test_required_argument_error():
    parser = ErrorRaisingArgumentParser()
    parser.add_argument("--foo", required=True)
    with pytest.raises(argparse.ArgumentError):
        parser.parse_args([])


def test_print_help_exception():
    parser = ErrorRaisingArgumentParser()
    with pytest.raises(ArgumentParserHelpException):
        parser.print_help()


def test_exit_exception():
    parser = ErrorRaisingArgumentParser()
    with pytest.raises(ArgumentParserExitException):
        parser.exit()


def test_help_flag(monkeypatch):
    parser = ErrorRaisingArgumentParser()
    with pytest.raises(ArgumentParserHelpException):
        parser.parse_args(["-h"])
