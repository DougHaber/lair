import importlib.metadata

import lair.components
import lair.events
from lair.config import Configuration
from lair.module_loader import ModuleLoader


def version():
    return importlib.metadata.version("lair")


config = Configuration()
