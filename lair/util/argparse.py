"""Extensions for Python's ``argparse`` that raise exceptions instead of exiting."""

import argparse
from typing import IO, TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from _typeshed import SupportsWrite as _SupportsWrite

    SupportsWriteStr = _SupportsWrite[str]
else:
    SupportsWriteStr = IO[str]


class ArgumentParserExitError(Exception):
    """Exception raised when the parser attempts to exit."""

    pass


class ArgumentParserHelpError(Exception):
    """Exception raised when help output is requested."""

    pass


# Backwards compatibility
ArgumentParserExitException = ArgumentParserExitError
ArgumentParserHelpException = ArgumentParserHelpError


class ErrorRaisingArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises exceptions instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise :class:`argparse.ArgumentError` instead of exiting.

        Args:
            message: The error message to display.

        Raises:
            argparse.ArgumentError: Always raised with ``message``.

        """
        raise argparse.ArgumentError(None, message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        """Raise :class:`ArgumentParserExitError` instead of exiting.

        Args:
            status: Exit status code. This value is ignored.
            message: Optional exit message to print before raising.

        Raises:
            ArgumentParserExitError: Always raised to signal a parser exit.

        """
        if message:
            self._print_message(message)
        raise ArgumentParserExitError(None, None)

    def print_help(self, file: SupportsWriteStr | None = None) -> NoReturn:
        """Raise :class:`ArgumentParserHelpError` with formatted help text.

        Args:
            file: Unused file handle provided for compatibility with the base
                class.

        Raises:
            ArgumentParserHelpError: Always raised with the formatted help text.

        """
        raise ArgumentParserHelpError(self.format_help())
