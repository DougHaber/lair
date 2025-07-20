import os

import libtmux
import pytest

import lair
from lair.components.tools.tmux_tool import TmuxTool


class DummyPane:
    def __init__(self, pane_id):
        self._pane_id = pane_id
        self.sent = []
        self.cmds = []
        self.captured = []

    def get(self, key):
        if key == "pane_id":
            return self._pane_id

    def send_keys(self, keys, enter=True, literal=True):
        self.sent.append((keys, enter, literal))

    def cmd(self, *args):
        self.cmds.append(args)

    def capture_pane(self):
        return self.captured


class DummyWindow:
    def __init__(self, window_id, name="window"):
        self._id = f"@{window_id}" if not str(window_id).startswith("@") else str(window_id)
        self._name = name
        self.attached_pane = DummyPane(f"%{window_id}")
        self.killed = False
        self.selected = False

    @property
    def active_pane(self):
        return self.attached_pane

    def get(self, key):
        if key == "window_id":
            return self._id
        if key == "window_name":
            return self._name

    def kill_window(self):
        self.killed = True

    def select_window(self):
        self.selected = True


class DummySession:
    def __init__(self):
        self.windows = []

    def new_window(self, window_name, attach=False):
        win = DummyWindow(len(self.windows) + 1, window_name)
        self.windows.append(win)
        return win

    def list_windows(self):
        return list(self.windows)


def setup_config(tmp_path):
    cfg = lair.config
    keys = [
        "tools.tmux.window_limit",
        "tools.tmux.capture_file_name",
        "tools.tmux.run.command",
        "tools.tmux.read_new_output.remove_echoed_commands",
        "tools.tmux.read_new_output.strip_escape_codes",
        "tools.tmux.read_new_output.max_size_default",
        "tools.tmux.read_new_output.max_size_limit",
    ]
    old = {k: cfg.get(k) for k in keys}
    cfg.set("tools.tmux.window_limit", 3, no_event=True)
    cfg.set("tools.tmux.capture_file_name", os.path.join(str(tmp_path), "cap-{window_id}.log"), no_event=True)
    cfg.set("tools.tmux.run.command", "echo hi", no_event=True)
    cfg.set("tools.tmux.read_new_output.remove_echoed_commands", True, no_event=True)
    cfg.set("tools.tmux.read_new_output.strip_escape_codes", False, no_event=True)
    cfg.set("tools.tmux.read_new_output.max_size_default", 1024, no_event=True)
    cfg.set("tools.tmux.read_new_output.max_size_limit", 8192, no_event=True)
    return old


def restore_config(values):
    for k, v in values.items():
        lair.config.set(k, v, no_event=True)


@pytest.fixture
def tool(tmp_path):
    old = setup_config(tmp_path)
    tool = TmuxTool()
    tool._ensure_connection = lambda: None
    tool.session = DummySession()
    yield tool
    restore_config(old)


def test_get_window_by_id_and_errors(tool):
    session = tool.session
    w1 = session.new_window("one")
    session.new_window("two")
    assert tool._get_window_by_id(w1.get("window_id")) is w1
    assert tool._get_window_by_id(w1.get("window_id").lstrip("@")) is w1
    assert tool._get_window_by_id(None) is None
    with pytest.raises(ValueError):
        tool._get_window_by_id("@99")


def test_get_output_modes(tool, monkeypatch):
    called = {}

    def fake_read(**kwargs):
        called["mode"] = "stream"
        return {"out": "stream"}

    def fake_cap(**kwargs):
        called["mode"] = "screen"
        return {"out": "screen"}

    monkeypatch.setattr(tool, "read_new_output", fake_read)
    monkeypatch.setattr(tool, "capture_output", fake_cap)
    assert tool._get_output("stream") == {"out": "stream"}
    assert called["mode"] == "stream"
    assert tool._get_output("screen") == {"out": "screen"}
    assert called["mode"] == "screen"
    with pytest.raises(ValueError):
        tool._get_output("bad")


def test_run_creates_window_and_logs(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(TmuxTool, "_get_output", lambda self, **k: {"ok": True})
    monkeypatch.setattr(os, "getpid", lambda: 12345)
    monkeypatch.setattr("time.sleep", lambda x: None)
    result = tool.run(delay=0, return_mode="stream")
    assert result["ok"] is True
    assert "window_id" in result
    assert tool.active_window in tool.session.windows
    pane = tool.active_window.attached_pane
    log_file = tool.log_files[pane.get("pane_id")]
    assert os.path.isfile(log_file)
    assert ("pipe-pane", "-o", f"cat >> {log_file}") in pane.cmds

    # window limit error
    tool.session.windows = [object()] * lair.config.get("tools.tmux.window_limit")
    err = tool.run(return_mode="stream")
    assert "limit reached" in err["error"]

    # invalid return_mode
    tool.session.windows = []
    err2 = tool.run(return_mode="bad")
    assert "return_mode" in err2["error"]


def test_send_keys_valid_and_errors(tool, monkeypatch):
    # no windows
    err = tool.send_keys("ls")
    assert "No active" in err["error"]

    # create a window
    monkeypatch.setattr(TmuxTool, "_get_output", lambda self, **k: {"done": True})
    monkeypatch.setattr("time.sleep", lambda x: None)
    tool.run()
    pane = tool.active_window.attached_pane
    res = tool.send_keys("abc", enter=False, literal=False, return_mode="screen", delay=0)
    assert res["done"] is True
    assert pane.sent[-1] == ("abc", False, False)

    # invalid return_mode
    bad = tool.send_keys("abc", return_mode="bad")
    assert "return_mode" in bad["error"]


def test_capture_output_and_errors(tool):
    with pytest.raises(RuntimeError):
        tool.capture_output()
    tool.session.new_window("one")
    tool.active_window = tool.session.windows[0]
    pane = tool.active_window.attached_pane
    pane.captured = ["a", "b"]
    out = tool.capture_output()
    assert out["current_screen"] == "a\nb"


def test_read_new_output_flow(tool, tmp_path):
    win = tool.session.new_window("one")
    tool.active_window = win
    pane = win.attached_pane
    log = tmp_path / "log.txt"
    tool.log_files[pane.get("pane_id")] = str(log)
    tool.log_offsets[pane.get("pane_id")] = 0
    data = b"cmd\nprompt\nhello\nworld\n"
    log.write_bytes(data)
    first = tool.read_new_output()
    assert first["output"] == "hello\nworld"

    # append more with echoed command
    with open(log, "ab") as f:
        f.write(b"ls\nresult\n")
    second = tool.read_new_output(prune_line="ls")
    assert second["output"] == "result\n"

    # start with carriage return and large size
    with open(log, "ab") as f:
        f.write(b"\ranother line\n")
    third = tool.read_new_output(max_size=8)
    assert third["output"].endswith("line\n")

    # connection lost
    del tool.log_files[pane.get("pane_id")]
    with pytest.raises(RuntimeError):
        tool.read_new_output()


def test_kill_attach_and_list(tool):
    tool.session.new_window("one")
    tool.session.new_window("two")
    w1, w2 = tool.session.windows
    tool.active_window = w1

    msg = tool.kill(window_id=w1.get("window_id"))
    assert "closed" in msg["message"] and w1.killed

    listed = tool.list_windows()["windows"]
    assert any(d["window_name"] == "two" for d in listed)

    attached = tool.attach_window(window_id=w2.get("window_id"))
    assert "Attached" in attached["message"] and tool.active_window is w2 and w2.selected

    # errors when no windows
    tool.session.windows.clear()
    err = tool.kill(window_id="@1")
    assert "No active tmux windows" in err["error"]
    err2 = tool.attach_window(window_id="@1")
    assert "No tmux windows" in err2["error"]


def test_ensure_connection_and_failure(tmp_path, monkeypatch):
    new_tool = TmuxTool()
    old = setup_config(tmp_path)
    calls = []

    class DummyServer:
        def __init__(self, fail=False):
            self.fail = fail
            self.sessions = []

        def list_sessions(self):
            if self.fail:
                raise RuntimeError("nope")

    def connect_first():
        calls.append("c")
        new_tool.server = DummyServer(fail=len(calls) == 1)
        new_tool.session = DummySession()

    monkeypatch.setattr(new_tool, "_connect_to_tmux", connect_first)
    new_tool.server = None
    new_tool._ensure_connection()
    assert len(calls) == 2  # called twice due to retry

    def connect_fail():
        raise RuntimeError("boom")

    new_tool.server = DummyServer(fail=True)
    monkeypatch.setattr(new_tool, "_connect_to_tmux", connect_fail)
    with pytest.raises(RuntimeError):
        new_tool._ensure_connection()
    restore_config(old)


def test_read_new_output_no_windows(tool):
    with pytest.raises(RuntimeError):
        tool.read_new_output()


def test_get_log_file_name_creates_dirs(tool, tmp_path, monkeypatch):
    cfg_value = os.path.join(str(tmp_path), "logs/cap-{window_id}.log")
    lair.config.set("tools.tmux.capture_file_name", cfg_value, no_event=True)
    window = DummyWindow(5)
    path = tool.get_log_file_name_and_create_directories(window)
    assert os.path.isdir(os.path.dirname(path))
    assert path.endswith("cap-@5.log")


def test_definition_generators(tool):
    assert tool._generate_run_definition()["function"]["name"] == "run"
    assert tool._generate_send_keys_definition()["function"]["name"] == "send_keys"
    assert tool._generate_capture_output_definition()["function"]["name"] == "capture_output"
    assert tool._generate_read_new_output_definition()["function"]["name"] == "read_new_output"
    assert tool._generate_kill_definition()["function"]["name"] == "kill"
    assert tool._generate_list_windows_definition()["function"]["name"] == "list_windows"
    assert tool._generate_attach_window_definition()["function"]["name"] == "attach_window"


def test_clean_new_data_options(tool, monkeypatch):
    lair.config.set("tools.tmux.read_new_output.strip_escape_codes", True, no_event=True)
    sample = b"line1\nline2\nremain\n"
    assert tool._clean_new_data(sample, 0, None) == "remain"

    called = {}

    def fake_strip(text):
        called["hit"] = True
        return text.replace("ESC", "")

    monkeypatch.setattr(lair.util, "strip_escape_codes", fake_strip)
    second = tool._clean_new_data(b"cmd\nres1\n", 1, "cmd")
    assert second == "res1\n"
    third = tool._clean_new_data(b"ESC\r", 1, None)
    assert called["hit"] and third == ""


def test_run_send_keys_and_window_errors(tool, monkeypatch):
    tool.session.new_window = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("oops"))
    err = tool.run()
    assert err["error"] == "oops"

    tool.session = DummySession()
    tool.active_window = tool.session.new_window("one")
    monkeypatch.setattr(tool, "_get_window_by_id", lambda wid: (_ for _ in ()).throw(RuntimeError("bad")))
    res = tool.send_keys("k", window_id=1)
    assert res["error"] == "bad"

    monkeypatch.setattr(tool, "_get_window_by_id", lambda wid: (_ for _ in ()).throw(RuntimeError("boom")))
    out = tool.kill(window_id="@1")
    assert out["error"] == "boom"

    monkeypatch.setattr(tool, "_ensure_connection", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    lst = tool.list_windows()
    assert lst["error"] == "fail"
    monkeypatch.setattr(tool, "_ensure_connection", lambda: None)
    monkeypatch.setattr(tool, "_get_window_by_id", lambda wid: (_ for _ in ()).throw(RuntimeError("attach")))
    att = tool.attach_window(window_id="@1")
    assert att["error"] == "attach"


class SimpleServer:
    def __init__(self):
        self.sessions = []
        self.new_session_called = False

    def new_session(self, session_name, attach=False):
        self.new_session_called = True
        sess = DummySession()
        sess.name = session_name
        self.sessions.append(sess)
        return sess


def test_connect_to_tmux_creates_and_reuses(tmp_path, monkeypatch):
    old = setup_config(tmp_path)
    server = SimpleServer()
    monkeypatch.setattr(libtmux, "Server", lambda: server)
    tool = TmuxTool()
    tool._connect_to_tmux()
    assert tool.server is server
    assert tool.session in server.sessions
    assert server.new_session_called
    assert tool.log_files == {}
    assert tool.log_offsets == {}

    # existing session reused
    server2 = SimpleServer()
    exist = DummySession()
    exist.name = lair.config.get("tools.tmux.session_name")
    server2.sessions.append(exist)
    monkeypatch.setattr(libtmux, "Server", lambda: server2)
    tool2 = TmuxTool()
    tool2._connect_to_tmux()
    assert tool2.session is exist
    assert not server2.new_session_called
    restore_config(old)
