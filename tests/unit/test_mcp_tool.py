from types import SimpleNamespace

import lair
from lair.components.tools.mcp_tool import MCPTool
from lair.components.tools.tool_set import ToolSet


def make_tool(monkeypatch):
    lair.config.set("tools.enabled", True, no_event=True)
    lair.config.set("tools.mcp.enabled", True, no_event=True)
    lair.config.set("tools.mcp.providers", "http://server", no_event=True)
    lair.config.set("tools.mcp.timeout", 5.0, no_event=True)
    ts = ToolSet(tools=[])
    tool = MCPTool()
    tool.add_to_tool_set(ts)
    ts.mcp_tool = tool
    return tool, ts


def test_manifest_loads_and_call(monkeypatch):
    tool, ts = make_tool(monkeypatch)

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
    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])

    def fake_post(url, json, timeout):
        if json["method"] == "tools/list":
            return SimpleNamespace(status_code=200, json=lambda: {"result": manifest}, raise_for_status=lambda: None)
        return SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"result": {"called": json["params"]["name"], **json["params"]["arguments"]}},
        )

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tool.ensure_manifest()
    assert "echo" in ts.tools
    result = ts.call_tool("echo", {"a": 1}, "id")
    assert result["called"] == "echo" and result["a"] == 1


def test_get_all_tools_loads_manifest(monkeypatch):
    tool, ts = make_tool(monkeypatch)
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
    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])

    def fake_post(url, json, timeout):
        if json["method"] == "tools/list":
            return SimpleNamespace(status_code=200, json=lambda: {"result": manifest}, raise_for_status=lambda: None)
        return SimpleNamespace(status_code=200, json=lambda: {"result": {}}, raise_for_status=lambda: None)

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tools = ts.get_all_tools(load_manifest=True)
    assert {t["name"] for t in tools} == {"echo"}
    assert tools[0]["source"] == "http://server"
