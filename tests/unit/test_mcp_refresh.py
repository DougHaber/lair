import types

import lair
from lair.components.tools.mcp_tool import MCPTool
from tests.helpers.chat_interface import make_interface


def test_mcp_refresh_loads_manifest(monkeypatch):
    ci = make_interface(monkeypatch)
    tool = MCPTool()
    tool.add_to_tool_set(ci.chat_session.tool_set)
    ci.chat_session.tool_set.mcp_tool = tool
    lair.config.set("tools.enabled", True, no_event=True)
    lair.config.set("tools.mcp.enabled", True, no_event=True)
    lair.config.set("tools.mcp.providers", "http://server", no_event=True)
    lair.config.set("tools.mcp.timeout", 5.0, no_event=True)

    manifest = {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "echo",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ]
    }

    call_count = {"get": 0}

    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])
    monkeypatch.setattr(
        lair.components.tools.mcp_tool,
        "requests",
        types.SimpleNamespace(
            get=lambda *a, **k: (
                call_count.__setitem__("get", call_count["get"] + 1)
                or types.SimpleNamespace(status_code=200, json=lambda: manifest, raise_for_status=lambda: None)
            ),
            post=lambda *a, **k: types.SimpleNamespace(status_code=200, json=lambda: {}, raise_for_status=lambda: None),
        ),
    )

    ci.command_mcp_refresh("/mcp-refresh", [], "")
    assert "echo" in ci.chat_session.tool_set.tools
    assert call_count["get"] == 1
