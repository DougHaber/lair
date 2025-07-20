"""Colorized logging utilities used throughout Lair."""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

from rich.console import Console
from rich.text import Text

logger = logging.getLogger("lair")
console = Console()


def init_logging(enable_debugging: bool = False) -> None:
    """Configure the ``lair`` logger.

    Args:
        enable_debugging: If ``True``, set the log level to ``DEBUG``. Otherwise ``INFO``.

    """
    handler = logging.StreamHandler()

    class LairLogFilter(logging.Filter):
        """Add color and prefix attributes to log records."""

        def filter(self, record: logging.LogRecord) -> bool:
            cast(Any, record).color = _log_color(record.levelname)
            cast(Any, record).prefix = f"{record.levelname}: " if record.levelname != "INFO" else ""
            return True

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.addFilter(LairLogFilter())
    logger.setLevel("DEBUG" if enable_debugging else "INFO")

    def exit_error(*args: object, **kwargs: object) -> None:
        """Log an error message and exit with status 1."""
        logger.error(*cast(Any, args), **cast(Any, kwargs))
        sys.exit(1)

    cast(Any, handler).emit = lambda record: _emit_with_color(handler, record)
    cast(Any, logger).exit_error = exit_error


def _log_color(level_name: str) -> str | None:
    """Return the rich color for a log level."""
    if level_name == "ERROR":
        return "red"
    if level_name == "DEBUG":
        return "dim"
    if level_name == "WARNING":
        return "yellow"
    return None


def _emit_with_color(handler: logging.Handler, record: logging.LogRecord) -> None:
    """Emit a log record using ``rich`` for colorized output."""
    message = handler.format(record)
    prefix = cast(Any, record).prefix
    color = cast(Any, record).color
    text = Text(prefix + message, style=color) if color else Text(prefix + message)
    console.print(text)
