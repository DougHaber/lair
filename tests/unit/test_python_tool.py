import subprocess
import types

import lair
from lair.components.tools.python_tool import PythonTool


class DummyProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_generate_definition_uses_config(monkeypatch):
    monkeypatch.setitem(lair.config.active, "tools.python.timeout", 12)
    monkeypatch.setitem(lair.config.active, "tools.python.extra_modules", "foo")
    tool = PythonTool()
    definition = tool._generate_definition()
    desc = definition["function"]["description"]
    assert "extra_modules=foo" in desc
    assert "timeout=12" in desc
    assert definition["function"]["parameters"]["required"] == ["script"]


def test_format_output_strips_empty_values():
    tool = PythonTool()
    result = tool._format_output(stdout="  hi  ", stderr="\n", exit_status=0)
    assert result == {"stdout": "hi", "exit_status": 0}
    assert tool._format_output() == {}


def test_run_python_start_failure(monkeypatch):
    tool = PythonTool()
    monkeypatch.setitem(lair.config.active, "tools.python.docker_image", "img")

    def fake_run(*args, **kwargs):
        return DummyProc(returncode=1)

    monkeypatch.setattr("lair.components.tools.python_tool.subprocess.run", fake_run)
    out = tool.run_python("print(1)")
    assert out["error"].startswith("ERROR: Failed to start_container")
    assert out["exit_status"] == 1


def test_run_python_timeout(monkeypatch):
    tool = PythonTool()
    monkeypatch.setitem(lair.config.active, "tools.python.docker_image", "img")
    monkeypatch.setitem(lair.config.active, "tools.python.timeout", 5)
    calls = []

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        calls.append(cmd)
        if cmd[1] == "run":
            return DummyProc(stdout="cid\n")
        if cmd[1] == "wait":
            raise subprocess.TimeoutExpired(cmd, timeout=5)
        if cmd[1] == "rm":
            return DummyProc()
        raise AssertionError("unexpected")

    monkeypatch.setattr("lair.components.tools.python_tool.subprocess.run", fake_run)
    out = tool.run_python("print(1)")
    assert out["error"].startswith("ERROR: Timeout")
    assert [tool._docker, "rm", "-f", "cid"] in calls


def test_run_python_success(monkeypatch):
    tool = PythonTool()
    monkeypatch.setitem(lair.config.active, "tools.python.docker_image", "img")
    monkeypatch.setitem(lair.config.active, "tools.python.timeout", 3)
    calls = []

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        calls.append(cmd)
        if cmd[1] == "run":
            return DummyProc(stdout="cid\n")
        if cmd[1] == "wait":
            return DummyProc(stdout="not-int\n")
        if cmd[1] == "logs":
            return DummyProc(stdout="out\n", stderr="err\n")
        if cmd[1] == "rm":
            return DummyProc()
        raise AssertionError("unexpected")

    monkeypatch.setattr("lair.components.tools.python_tool.subprocess.run", fake_run)
    out = tool.run_python("print(1)")
    assert out["stdout"] == "out"
    assert out["stderr"] == "err"
    assert "exit_status" not in out
    assert [tool._docker, "rm", "-f", "cid"] in calls


def test_run_python_exception(monkeypatch):
    tool = PythonTool()
    monkeypatch.setitem(lair.config.active, "tools.python.docker_image", "img")
    events = []

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        if cmd[1] == "run":
            return DummyProc(stdout="cid\n")
        if cmd[1] == "wait":
            raise RuntimeError("boom")
        if cmd[1] == "rm":
            events.append("cleanup")
            return DummyProc()
        raise AssertionError("unexpected")

    monkeypatch.setattr("lair.components.tools.python_tool.subprocess.run", fake_run)
    warned = {}
    monkeypatch.setattr(
        "lair.components.tools.python_tool.logger",
        types.SimpleNamespace(warning=lambda msg: warned.setdefault("msg", msg)),
    )
    out = tool.run_python("print(1)")
    assert "boom" in out["error"]
    assert "cleanup" in events
    assert "boom" in warned["msg"]
