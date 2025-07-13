import importlib.metadata

from lair import events
from lair.config import Configuration


def version():
    return importlib.metadata.version("lair")


config = Configuration()

__all__ = ["version", "config", "events"]
