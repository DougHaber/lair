"""Utilities for dynamically loading and validating modules."""

import importlib
import os
import re
import types
from typing import cast

import jsonschema

from lair.logging import logger


class ModuleLoader:
    """Load modules from disk and expose them as commands."""

    MODULE_INFO_SCHEMA = {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "class": {},
            "tags": {"type": "array", "items": {"type": "string"}},
            "aliases": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["class"],
    }

    def __init__(self) -> None:
        """Initialize the loader."""
        self.modules: dict[str, dict] = {}
        self.commands: dict[str, type] = {}

    def _get_module_files(self, path: str) -> list[str]:
        """Return all module files contained within ``path``."""
        module_files: list[str] = []

        for root, _dirs, files in os.walk(os.path.abspath(path)):
            for name in files:
                if name.endswith(".py") and name != "__init__.py" and not name.startswith("."):
                    module_files.append(f"{root}/{name}")

        return module_files

    def _get_module_name(self, module: types.ModuleType, module_path: str) -> str:
        """Return the module's name relative to ``module_path``.

        Args:
            module: Imported module object.
            module_path: Base directory modules are loaded from.

        Returns:
            Module name relative to ``module_path`` without the extension.

        """
        absolute_module_file = os.path.abspath(cast(str, module.__file__)).replace("_", "-")
        absolute_module_path = os.path.abspath(module_path)

        return re.sub("^" + re.escape(absolute_module_path) + "/", "", re.sub(r"\.pyc?$", "", absolute_module_file))

    def _register_module(self, module: types.ModuleType, module_path: str) -> None:
        """Add ``module`` to the registry after validation."""
        module_info = module._module_info()
        name = self._get_module_name(module, module_path)
        module_info.update({"name": name})

        if name in self.modules:
            raise Exception(f"Unable to register repeat name: {name}")
        elif name in self.commands:
            raise Exception(f"Unable to register repeat command name: {name}")
        else:
            logger.debug(f"Registered module: {name}")
            self.modules[name] = module_info
            self.commands[name] = module_info["class"]

            for alias in module_info.get("aliases", []):
                if alias in self.commands:
                    raise Exception(f"Unable to register repeat command / alias: {name}")
                self.commands[alias] = module_info["class"]

    def _validate_module(self, module: types.ModuleType) -> None:
        """Verify that ``module`` contains a valid ``_module_info`` function."""
        if not hasattr(module, "_module_info"):
            raise Exception("_module_info not defined")
        if not isinstance(module._module_info, types.FunctionType):
            raise Exception("_module_info not a function")

        try:
            jsonschema.validate(instance=module._module_info(), schema=ModuleLoader.MODULE_INFO_SCHEMA)
        except jsonschema.ValidationError as error:
            raise Exception(f"Invalid _module_info: {error}") from error

    def import_file(self, filename: str, module_path: str) -> None:
        """Import a Python file and register it as a module."""
        logger.debug(f"Importing file: {filename}")

        try:
            spec = importlib.util.spec_from_file_location(filename, filename)
            if spec is None or spec.loader is None:
                raise ImportError(f"Failed to load spec for {filename}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self._validate_module(module)
            self._register_module(module, module_path)
        except Exception as error:
            logger.warning(f"Error loading module from file '{filename}': {error}")
            return

    def load_modules_from_path(self, module_path: str) -> None:
        """Load and register all modules found under ``module_path``."""
        logger.debug(f"Loading modules from path: {module_path}")
        files = self._get_module_files(module_path)

        for filename in sorted(files):
            self.import_file(filename, module_path)
