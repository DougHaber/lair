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
    monkeypatch.setattr(
        MCPTool,
        "_get_providers",
        lambda self: ["http://server"],
    )
    monkeypatch.setattr(
        lair.components.tools.mcp_tool,
        "requests",
        SimpleNamespace(
            get=lambda url, timeout: SimpleNamespace(
                status_code=200, json=lambda: manifest, raise_for_status=lambda: None
            ),
            post=lambda url, json, timeout: SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {"called": json["name"], **json["arguments"]},
            ),
        ),
    )

    tool.ensure_manifest()
    assert "echo" in ts.tools
    result = ts.call_tool("echo", {"a": 1}, "id")
    assert result["called"] == "echo" and result["a"] == 1
