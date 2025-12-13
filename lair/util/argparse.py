import argparse


class ArgumentParserExitException(Exception):
    """Custom Exception for argparse to throw on exit, instead of actually exiting"""
    pass


class ArgumentParserHelpException(Exception):
    pass


class ErrorRaisingArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser() that throws exceptions so that behaviors could be handled differently"""
    def error(self, message):
        """Throw ArgumentError() on errors"""
        raise argparse.ArgumentError(None, message)

    def exit(self, status=0, message=None):
        """Instead of exiting, throw an exception with the error"""
        if message:
            self._print_message(message)
        raise ArgumentParserExitException(None, None)

    def print_help(self, file=None):
        """Override print_help to raise an exception with the help message."""
        raise ArgumentParserHelpException(self.format_help())
