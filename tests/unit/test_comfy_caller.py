import base64
import importlib
import sys
import types

import pytest

import lair


def get_comfy_caller():
    if "lair.comfy_caller" in sys.modules:
        mod = importlib.reload(sys.modules["lair.comfy_caller"])
    else:
        mod = importlib.import_module("lair.comfy_caller")
    return mod.ComfyCaller


class DummyThread:
    def __init__(self, alive=True):
        self.alive = alive
        self.ident = 123

    def is_alive(self):
        return self.alive


class DummyQueue:
    def __init__(self):
        self._watch_thread = None
        self.started = []

    def start_watch(self, a, b, c):
        self.started.append((a, b, c))
        self._watch_thread = DummyThread(True)


@pytest.fixture
def comfy_caller(monkeypatch):
    # Provide fake comfy_script.runtime module
    queue = DummyQueue()
    runtime_mod = types.SimpleNamespace(queue=queue)
    monkeypatch.setitem(sys.modules, "comfy_script.runtime", runtime_mod)
    cc = get_comfy_caller()(url="http://example")
    return cc, queue


def test_parse_lora_argument():
    cc = get_comfy_caller()()
    assert cc._parse_lora_argument("model") == ("model", 1.0, 1.0)
    assert cc._parse_lora_argument("model:0.5") == ("model", 0.5, 1.0)
    assert cc._parse_lora_argument("model:0.2:0.3") == ("model", 0.2, 0.3)


def test_apply_loras(monkeypatch):
    cc = get_comfy_caller()()
    calls = []

    def loader(model, clip, name, weight, clip_weight):
        calls.append((model, clip, name, weight, clip_weight))
        return f"{model}+{name}", f"{clip}+{name}"

    caller_mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(caller_mod, "LoraLoader", loader, raising=False)

    model, clip = cc._apply_loras("m", "c", ["a:0.1:0.2", "b"])
    assert calls[0] == ("m", "c", "a", 0.1, 0.2)
    assert calls[1] == ("m+a", "c+a", "b", 1.0, 1.0)
    assert model == "m+a+b"
    assert clip == "c+a+b"


def test_ensure_seed(monkeypatch):
    cc = get_comfy_caller()()
    caller_mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(caller_mod.secrets, "randbelow", lambda a: 42)
    assert cc._ensure_seed(None) == 42
    assert cc._ensure_seed(9) == 9


def test_image_to_base64(tmp_path):
    file = tmp_path / "img.txt"
    content = b"data"
    file.write_bytes(content)
    cc = get_comfy_caller()()
    encoded = cc._image_to_base64(str(file))
    assert encoded == base64.b64encode(content).decode()
    with pytest.raises(ValueError):
        cc._image_to_base64(b"bytes")


def test_watch_thread_management(comfy_caller, monkeypatch):
    cc, queue = comfy_caller
    cc._ensure_watch_thread()
    assert queue.started == [(False, False, False)]

    # Calling again with alive thread should not restart
    cc._ensure_watch_thread()
    assert queue.started == [(False, False, False)]

    # If thread dies, a new one should start
    queue._watch_thread.alive = False
    cc._ensure_watch_thread()
    assert len(queue.started) == 2

    # Test cleanup
    killed = []
    monkeypatch.setattr(cc, "_kill_thread", lambda t: killed.append(t))
    current = queue._watch_thread
    cc._cleanup_watch_thread()
    assert killed == [current]
    assert queue._watch_thread is None


def test_run_workflow(monkeypatch):
    cc = get_comfy_caller()()

    async def handler(val=0):
        return val + 1

    cc.workflows["dummy"] = handler
    cc.defaults["dummy"] = {"val": 1}

    called = []
    monkeypatch.setattr(cc, "_ensure_watch_thread", lambda: called.append("start"))
    monkeypatch.setattr(cc, "_cleanup_watch_thread", lambda: called.append("stop"))
    monkeypatch.setattr(lair.util, "is_debug_enabled", lambda: True)

    result = cc.run_workflow("dummy", val=4)
    assert result == 5
    assert called == ["start", "stop"]


def test_run_workflow_no_debug(monkeypatch, capsys):
    cc = get_comfy_caller()()

    async def handler():
        return "ok"

    cc.workflows["dummy"] = handler
    cc.defaults["dummy"] = {}

    called = []
    monkeypatch.setattr(cc, "_ensure_watch_thread", lambda: called.append("start"))
    monkeypatch.setattr(cc, "_cleanup_watch_thread", lambda: called.append("stop"))
    monkeypatch.setattr(lair.util, "is_debug_enabled", lambda: False)

    result = cc.run_workflow("dummy")
    assert result == "ok"
    assert called == ["start", "stop"]
