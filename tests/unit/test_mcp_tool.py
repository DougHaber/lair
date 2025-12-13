import json
from types import SimpleNamespace

import lair
from lair.components.tools.mcp_tool import MCPTool
from lair.components.tools.tool_set import ToolSet


def _sse_response(data):
    return SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "text/event-stream"},
        raise_for_status=lambda: None,
        iter_lines=lambda decode_unicode=True: iter([f"data: {json.dumps({'jsonrpc': '2.0', 'result': data})}", ""]),
        json=lambda: {},
    )


def _json_response(data):
    return SimpleNamespace(
        status_code=200,
        headers={"Content-Type": "application/json"},
        json=lambda: {"result": data},
        raise_for_status=lambda: None,
        iter_lines=lambda decode_unicode=True: iter([]),
    )


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

    def fake_post(url, json, timeout, headers=None):
        if json["method"] == "tools/list":
            return _json_response(manifest)
        return _json_response({"called": json["params"]["name"], **json["params"]["arguments"]})

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tool.ensure_manifest()
    assert "echo" in ts.tools
    result = ts.call_tool("echo", {"a": 1}, "id")
    assert result["called"] == "echo" and result["a"] == 1


def test_manifest_plain_format(monkeypatch):
    tool, ts = make_tool(monkeypatch)

    manifest = {
        "tools": [
            {
                "name": "plain_echo",
                "description": "desc",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
    }
    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])

    def fake_post(url, json, timeout, headers=None):
        if json["method"] == "tools/list":
            return _json_response(manifest)
        return _json_response({"called": json["params"]["name"]})

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tool.ensure_manifest()
    assert "plain_echo" in ts.tools
    result = ts.call_tool("plain_echo", {}, "id")
    assert result["called"] == "plain_echo"


def test_manifest_sse_and_handshake(monkeypatch):
    tool, ts = make_tool(monkeypatch)

    page1 = {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "echo1",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ],
        "nextCursor": "n",
    }

    page2 = {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "echo2",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ]
    }

    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append((json["method"], headers))
        if json["method"] in {"initialize", "initialized"}:
            return _json_response({})
        if json["method"] == "tools/list":
            data = page2 if json.get("params", {}).get("cursor") else page1
            return _sse_response(data)
        if json["method"] == "tools/call":
            return _sse_response({"ok": True})
        return _json_response({})

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tool.ensure_manifest()
    assert {"echo1", "echo2"} <= set(ts.tools)
    result = ts.call_tool("echo1", {}, "id")
    assert result["ok"] is True
    assert calls[0][0] == "initialize" and "Accept" in calls[0][1]


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

    def fake_post(url, json, timeout, headers=None):
        if json["method"] == "tools/list":
            return _json_response(manifest)
        if json["method"] in {"initialize", "initialized"}:
            return _json_response({})
        return _json_response({})

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tools = ts.get_all_tools(load_manifest=True)
    assert {t["name"] for t in tools} == {"echo"}
    assert tools[0]["source"] == "http://server"


def test_invalid_tool_name_ignored(monkeypatch):
    tool, ts = make_tool(monkeypatch)

    manifest = {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "bad!name",
                    "description": "",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ]
    }
    monkeypatch.setattr(MCPTool, "_get_providers", lambda self: ["http://server"])

    def fake_post(url, json, timeout, headers=None):
        if json["method"] == "tools/list":
            return _json_response(manifest)
        return _json_response({})

    monkeypatch.setattr(lair.components.tools.mcp_tool, "requests", SimpleNamespace(post=fake_post))

    tool.ensure_manifest()
    assert "bad!name" not in ts.tools
