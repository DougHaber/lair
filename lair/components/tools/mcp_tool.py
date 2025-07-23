"""Tools provided by a remote MCP server over HTTP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

import requests

import lair
from lair.logging import logger

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    from .tool_set import ToolSet


class MCPTool:
    """Load and invoke tools from an MCP server."""

    name = "mcp"

    def __init__(self) -> None:
        """Initialize the tool without loading the manifest."""
        self.tool_set: ToolSet | None = None
        self.manifest_loaded = False
        self.last_providers: list[str] | None = None

    def add_to_tool_set(self, tool_set: ToolSet) -> None:
        """Register dynamic tools from the MCP manifest when needed."""
        self.tool_set = tool_set

    def refresh(self) -> None:
        """Force a reload of the manifest on the next request."""
        if self.tool_set is None:
            return
        self.manifest_loaded = False
        self.last_providers = None
        for name, meta in list(self.tool_set.tools.items()):
            if meta["class_name"] == self.__class__.__name__:
                del self.tool_set.tools[name]

    def _get_providers(self) -> list[str]:
        providers = str(lair.config.get("tools.mcp.providers", allow_not_found=True, default="")).splitlines()
        if not providers:
            providers = str(lair.config.get("tools.mcp.provider", allow_not_found=True, default="")).splitlines()
        return [p.strip() for p in providers if p.strip()]

    def _register_manifest(self, base_url: str, manifest: dict[str, Any]) -> None:
        for tool_def in manifest.get("tools", []):
            name = tool_def.get("function", {}).get("name")
            if not name or self.tool_set is None:
                continue
            self.tool_set.add_tool(
                class_name=self.__class__.__name__,
                name=name,
                flags=["tools.mcp.enabled"],
                definition=tool_def,
                handler=self._make_handler(base_url, name),
                metadata={"source": base_url},
            )

    def _make_handler(self, base_url: str, name: str) -> Callable[..., dict[str, Any]]:
        def handler(**arguments: object) -> dict[str, Any]:
            return self._call_tool(base_url, name, cast(dict[str, Any], arguments))

        return handler

    def _load_manifest(self) -> None:
        if self.tool_set is None:
            return
        timeout = cast(float, lair.config.get("tools.mcp.timeout"))
        providers = self._get_providers()
        self.last_providers = providers
        for base_url in providers:
            try:
                response = requests.get(f"{base_url}/manifest", timeout=timeout)
                response.raise_for_status()
                self._register_manifest(base_url, response.json())
            except Exception as error:  # noqa: BLE001 - log exception
                logger.warning(f"MCPTool: failed to load manifest from {base_url}: {error}")
        self.manifest_loaded = True

    def ensure_manifest(self) -> None:
        """Load the manifest if it has not been loaded."""
        providers = self._get_providers()
        if providers != self.last_providers:
            self.refresh()
            self.last_providers = providers
        if not self.manifest_loaded and lair.config.get("tools.mcp.enabled"):
            self._load_manifest()

    def _call_tool(self, base_url: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        timeout = cast(float, lair.config.get("tools.mcp.timeout"))
        try:
            response = requests.post(
                f"{base_url}/call",
                json={"name": name, "arguments": arguments},
                timeout=timeout,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except Exception as error:  # noqa: BLE001 - log exception
            logger.warning(f"MCPTool: call to {name} failed: {error}")
            return {"error": str(error)}
