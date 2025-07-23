"""Utility functions and defaults for the built-in tooling system."""

from typing import Optional

from .file_tool import FileTool
from .mcp_tool import MCPTool
from .python_tool import PythonTool
from .search_tool import SearchTool
from .tmux_tool import TmuxTool
from .tool_set import ToolSet

DEFAULT_TOOLS = [
    FileTool,
    MCPTool,
    PythonTool,
    SearchTool,
    TmuxTool,
]

# Lookup for tool classes by their friendly names
TOOLS: dict[str, type] = {
    FileTool.name: FileTool,
    MCPTool.name: MCPTool,
    PythonTool.name: PythonTool,
    SearchTool.name: SearchTool,
    TmuxTool.name: TmuxTool,
}


def get_tool_class_by_name(name: str) -> Optional[type]:
    """
    Return the registered tool class for ``name`` if it exists.

    Args:
        name: The friendly name of the tool.

    Returns:
        The tool class or ``None`` if ``name`` is unknown.

    """
    return TOOLS.get(name)


def get_tool_classes_from_str(tool_names_str: str) -> None:
    """
    Build a list of classes from a comma-separated string of tool names.

    Args:
        tool_names_str: Comma-separated friendly tool names.

    Returns:
        None

    Raises:
        ValueError: If any tool name is not registered.

    """
    classes: list[type] = []
    for name in tool_names_str.split(","):
        name = name.strip()

        if name not in TOOLS:
            raise ValueError(f"Unknown tool name: {tool_names_str}")

        classes.append(TOOLS[name])

    return None


__all__ = [
    "FileTool",
    "MCPTool",
    "PythonTool",
    "SearchTool",
    "TmuxTool",
    "ToolSet",
    "DEFAULT_TOOLS",
    "TOOLS",
    "get_tool_class_by_name",
    "get_tool_classes_from_str",
]
