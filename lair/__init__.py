"""
Lair top-level package.

This package exposes the public API, including the configuration object and a
helper function for retrieving the installed version of the package.
"""

import importlib.metadata

from lair import events
from lair.config import Configuration


def version() -> str:
    """
    Return the installed version of ``lair``.

    Returns:
        str: The version string as defined in package metadata.

    """
    return importlib.metadata.version("lair")


config = Configuration()

__all__ = ["version", "config", "events"]
