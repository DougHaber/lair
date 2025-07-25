from types import SimpleNamespace

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

    call_count = {"post": 0}

    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])

    def fake_post(url, json, timeout, headers=None):
        call_count["post"] += 1
        if json["method"] == "tools/list":
            return SimpleNamespace(
                status_code=200,
                headers={"Content-Type": "application/json"},
                json=lambda: {"result": manifest},
                raise_for_status=lambda: None,
            )
        return SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "application/json"},
            json=lambda: {"result": {}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    ci.command_mcp_refresh("/mcp-refresh", [], "")
    assert "echo" in ci.chat_session.tool_set.tools
    assert call_count["post"] == 3
    assert ("system", "MCP manifest refreshed") in ci.reporting.messages
    assert ("system", "http://server - 1 tool") in ci.reporting.messages


def test_mcp_refresh_no_providers(monkeypatch):
    ci = make_interface(monkeypatch)
    tool = MCPTool()
    tool.add_to_tool_set(ci.chat_session.tool_set)
    ci.chat_session.tool_set.mcp_tool = tool
    lair.config.set("tools.enabled", True, no_event=True)
    lair.config.set("tools.mcp.enabled", True, no_event=True)
    lair.config.set("tools.mcp.providers", "", no_event=True)

    ci.command_mcp_refresh("/mcp-refresh", [], "")
    assert ("warning", "No MCP providers configured") in ci.reporting.messages


def test_mcp_refresh_no_tools(monkeypatch):
    ci = make_interface(monkeypatch)
    tool = MCPTool()
    tool.add_to_tool_set(ci.chat_session.tool_set)
    ci.chat_session.tool_set.mcp_tool = tool
    lair.config.set("tools.enabled", True, no_event=True)
    lair.config.set("tools.mcp.enabled", True, no_event=True)
    lair.config.set("tools.mcp.providers", "http://server", no_event=True)
    lair.config.set("tools.mcp.timeout", 5.0, no_event=True)

    manifest = {"tools": []}

    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])

    def fake_post(url, json, timeout, headers=None):
        if json["method"] == "tools/list":
            return SimpleNamespace(
                status_code=200,
                headers={"Content-Type": "application/json"},
                json=lambda: {"result": manifest},
                raise_for_status=lambda: None,
            )
        return SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "application/json"},
            json=lambda: {"result": {}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    ci.command_mcp_refresh("/mcp-refresh", [], "")
    assert ("warning", "http://server - 0 tools") in ci.reporting.messages
    assert ("warning", "No tools found") in ci.reporting.messages
