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
            if record.levelname == "ERROR":
                record.color = "red"
            elif record.levelname == "DEBUG":
                record.color = "dim"
            elif record.levelname == "WARNING":
                record.color = "yellow"
            else:
                record.color = None

            record.prefix = f"{record.levelname}: " if record.levelname != "INFO" else ""
            return True

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.addFilter(LairLogFilter())
    logger.setLevel("DEBUG" if enable_debugging else "INFO")

    def exit_error(*args, **kwargs):
        logger.error(*args, **kwargs)
        sys.exit(1)

    def emit_with_color(record):
        message = handler.format(record)
        if record.color:
            text = Text(record.prefix + message, style=record.color)
        else:
            text = Text(record.prefix + message)
        console.print(text)

    handler.emit = emit_with_color
    logger.exit_error = exit_error
