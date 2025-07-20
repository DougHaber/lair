"""Utilities for managing tool classes and invoking their handlers."""

from collections.abc import Callable, Iterable
from typing import Any

import lair.components.tools
from lair.logging import logger


class ToolSet:
    """Container for managing and invoking individual tools."""

    def __init__(self, *, tools: list[type] | None = None) -> None:
        """Initialize the tool set.

        Args:
            tools: List of tool classes to include. When ``None`` the default
                tools defined by :mod:`lair.components.tools` are used.

        """
        self.requested_tools: list[type] | None = None
        self.tools: dict[str, dict[str, Any]] = {}
        self._init_tools(tools)

    def _init_tools(self, tools: list[type] | None) -> None:
        """Instantiate each tool class and register its tools.

        Args:
            tools: List of tool classes to instantiate. If ``None`` the default
                tool list is used.

        """
        self.requested_tools = lair.components.tools.DEFAULT_TOOLS if tools is None else tools

        for tool in self.requested_tools:
            tool().add_to_tool_set(self)

    def update_tools(self, tools: list[type] | None = None) -> None:
        """Recreate the tool set with the provided tool classes.

        Args:
            tools: List of tool classes to include. When ``None`` the default
                tools are loaded.

        """
        self._init_tools(tools)

    def add_tool(
        self,
        *,
        name: str,
        flags: list[str],
        definition: dict[str, Any] | None = None,
        definition_handler: Callable[[], dict[str, Any]] | None = None,
        handler: Callable[..., dict[str, Any]],
        class_name: str,
    ) -> None:
        """Register a new tool in the collection.

        Args:
            name: Unique name used to call the tool.
            flags: Configuration flags required for the tool to be enabled.
            definition: Structured definition of the function in OpenAI format.
            definition_handler: Callable returning a definition at runtime.
                Takes precedence over ``definition`` when provided.
            handler: Callable executed when the tool is invoked.
            class_name: Name of the implementing class.

        Raises:
            ValueError: If a tool with the same name already exists or if both
                ``definition`` and ``definition_handler`` are missing.

        """
        if name in self.tools:
            raise ValueError(f"ToolSet.add_tool(): A tool named '{name}' is already registered")
        elif not (definition or definition_handler):
            raise ValueError("ToolSet.add_tool(): Either a definition or a definition_handler must be provided")

        self.tools[name] = {
            "class_name": class_name,
            "definition": definition,
            "definition_handler": definition_handler,
            "flags": flags,
            "handler": handler,
            "name": name,
        }

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tools that are currently enabled."""
        if not lair.config.get("tools.enabled"):
            return []

        enabled_tools = []
        for tool in self.tools.values():
            if not self.all_flags_enabled(tool["flags"]):
                continue

            enabled_tools.append(tool)

        return enabled_tools

    def all_flags_enabled(self, flags: Iterable[str]) -> bool:
        """Return ``True`` if all configuration flags evaluate to truthy."""
        return all(lair.config.get(flag) for flag in flags)

    def get_all_tools(self) -> list[dict[str, Any]] | None:
        """Return metadata for all tools with an ``enabled`` field."""
        all_tools = []
        for tool in self.tools.values():
            tool["enabled"] = lair.config.get("tools.enabled") and self.all_flags_enabled(tool["flags"]) is True
            all_tools.append(tool)

        return all_tools or None

    def _get_definition(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Return the structured definition for ``tool``."""
        return tool["definition_handler"]() if tool["definition_handler"] else tool["definition"]

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return definitions for all enabled tools."""
        tools = self.get_tools()
        return [self._get_definition(tool) for tool in tools]

    def call_tool(self, name: str, arguments: dict[str, Any], tool_call_id: str) -> dict[str, Any]:
        """Invoke a tool handler with the provided arguments.

        Args:
            name: The name of the tool to call.
            arguments: Arguments to pass to the tool handler.
            tool_call_id: Identifier for the tool call used for logging.

        Returns:
            A dictionary containing the tool output or an ``error`` key when the
            call fails or the tool is unknown.

        """
        logger.debug(f"Tool call: {name}({arguments})  [{tool_call_id}]")
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}"}

        try:
            return self.tools[name]["handler"](**arguments)
        except Exception as error:
            return {"error": f"Call failed: {error}"}
