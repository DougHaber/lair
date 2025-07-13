import logging
import sys

from rich.console import Console
from rich.text import Text

logger = logging.getLogger("lair")
console = Console()


def init_logging(enable_debugging=False):
    handler = logging.StreamHandler()

    class LairLogFilter(logging.Filter):
        def filter(self, record):
            record.color = _log_color(record.levelname)
            record.prefix = f"{record.levelname}: " if record.levelname != "INFO" else ""
            return True

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.addFilter(LairLogFilter())
    logger.setLevel("DEBUG" if enable_debugging else "INFO")

    def exit_error(*args, **kwargs):
        logger.error(*args, **kwargs)
        sys.exit(1)

    handler.emit = lambda record: _emit_with_color(handler, record)
    logger.exit_error = exit_error


def _log_color(level_name):
    if level_name == "ERROR":
        return "red"
    if level_name == "DEBUG":
        return "dim"
    if level_name == "WARNING":
        return "yellow"
    return None


def _emit_with_color(handler, record):
    message = handler.format(record)
    if record.color:
        text = Text(record.prefix + message, style=record.color)
    else:
        text = Text(record.prefix + message)
    console.print(text)
