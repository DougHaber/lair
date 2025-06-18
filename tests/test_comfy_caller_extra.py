import importlib
import types
import ssl
import sys
import asyncio

import pytest

from tests.test_comfy_caller import get_ComfyCaller


class DummyNode:
    def __init__(self, output):
        self._output = output

    def wait(self):
        return self


def test_monkey_patch_comfy_script(monkeypatch):
    importlib.import_module("lair.comfy_caller")
    cc = get_ComfyCaller()()

    class DummyConnector:
        last_ssl = None

        def __init__(self, *args, **kwargs):
            DummyConnector.last_ssl = kwargs.get("ssl")

    aiohttp_mod = types.SimpleNamespace(TCPConnector=DummyConnector)
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_mod)

    cc._monkey_patch_comfy_script()

    DummyConnector()
    ctx = DummyConnector.last_ssl
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False


def test_import_comfy_script(monkeypatch):
    caller_mod = importlib.import_module("lair.comfy_caller")
    cc = get_ComfyCaller()(url="http://unit.test")

    runtime_mod = types.ModuleType("comfy_script.runtime")

    def load(url):
        runtime_mod.loaded = url

    class Workflow:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    runtime_mod.load = load
    runtime_mod.Workflow = Workflow
    monkeypatch.setitem(sys.modules, "comfy_script.runtime", runtime_mod)

    nodes_mod = types.ModuleType("comfy_script.runtime.nodes")
    nodes_mod.DummyNode = object()
    monkeypatch.setitem(sys.modules, "comfy_script.runtime.nodes", nodes_mod)

    called = []
    monkeypatch.setattr(cc, "_monkey_patch_comfy_script", lambda: called.append("patch"))
    monkeypatch.setattr(
        importlib.import_module("lair").config, "get", lambda k, *a, **kw: False if k == "comfy.verify_ssl" else None
    )

    cc._import_comfy_script()

    assert runtime_mod.loaded == "http://unit.test"
    assert called == ["patch"]
    assert caller_mod.load is load
    assert caller_mod.Workflow is Workflow
    assert caller_mod.DummyNode is nodes_mod.DummyNode
    assert cc.is_comfy_script_imported is True


def test_set_url(monkeypatch):
    cc = get_ComfyCaller()(url="http://same")
    called = []
    monkeypatch.setattr(cc, "_import_comfy_script", lambda: called.append(True))
    cc.set_url("http://same")
    assert called == []

    cc2 = get_ComfyCaller()()
    called2 = []
    monkeypatch.setattr(cc2, "_import_comfy_script", lambda: called2.append(True))
    cc2.set_url("http://new")
    assert cc2.url == "http://new"
    assert called2 == [True]

    with pytest.raises(Exception):
        cc.set_url("http://other")


def test_view(monkeypatch):
    cc = get_ComfyCaller()(url="http://server")
    responses = []

    class Resp:
        def __init__(self, code, content=b""):
            self.status_code = code
            self.content = content

    def fake_get(url, params, verify):
        responses.append((url, params, verify))
        return Resp(200, b"data")

    monkeypatch.setattr(importlib.import_module("lair.comfy_caller").requests, "get", fake_get, raising=False)
    result = cc.view("file")
    assert result == b"data"
    assert responses[0][0] == "http://server/api/view"

    monkeypatch.setattr(
        importlib.import_module("lair.comfy_caller").requests, "get", lambda *a, **k: Resp(404), raising=False
    )
    with pytest.raises(Exception):
        cc.view("bad")


def test_kill_thread(monkeypatch):
    cc = get_ComfyCaller()()
    dummy = types.SimpleNamespace(ident=5)
    called = []
    monkeypatch.setattr(
        importlib.import_module("lair.comfy_caller").ctypes.pythonapi,
        "PyThreadState_SetAsyncExc",
        lambda ident, exc: called.append((ident, exc)),
    )
    cc._kill_thread(dummy)
    mod = importlib.import_module("lair.comfy_caller").ctypes
    assert called and called[0][0].value == 5
    assert isinstance(called[0][1], mod.py_object)

    monkeypatch.setattr(
        importlib.import_module("lair.comfy_caller").ctypes.pythonapi,
        "PyThreadState_SetAsyncExc",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError),
    )
    logged = []
    monkeypatch.setattr(importlib.import_module("lair.comfy_caller").logger, "debug", lambda msg: logged.append(msg))
    cc._kill_thread(dummy)
    assert "Failed to terminate ComfyScript thread" in logged[0]


def test_workflow_ltxv_prompt(monkeypatch):
    cc = get_ComfyCaller()()
    with pytest.raises(ValueError):
        asyncio.run(
            cc._workflow_ltxv_prompt(
                None,
                florence_model_name="m",
                auto_prompt_extra="",
                auto_prompt_suffix="",
                florence_seed=1,
                image_resize_height=1,
                image_resize_width=1,
            )
        )

    caller_mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(
        caller_mod,
        "Workflow",
        type("WF", (), {"__enter__": lambda self: None, "__exit__": lambda self, exc_type, exc, tb: None}),
    )
    monkeypatch.setattr(cc.__class__, "_image_to_base64", lambda self, img: "b64", raising=False)
    monkeypatch.setattr(caller_mod, "ETNLoadImageBase64", lambda img: ("img", None), raising=False)
    monkeypatch.setattr(caller_mod, "ImageResizeKJ", lambda *a, **k: ("img2", 1, 1), raising=False)
    monkeypatch.setattr(caller_mod, "DownloadAndLoadFlorence2Model", lambda *a, **k: "model", raising=False)
    monkeypatch.setattr(
        caller_mod, "Florence2Run", lambda *a, **k: (None, None, DummyNode({"text": ["p"]}), None), raising=False
    )
    monkeypatch.setattr(caller_mod, "StringReplaceMtb", lambda *a, **k: DummyNode({"text": ["p"]}), raising=False)
    monkeypatch.setattr(
        caller_mod, "StringFunctionPysssss", lambda *a, **k: DummyNode({"text": ["final"]}), raising=False
    )
    monkeypatch.setattr(caller_mod.random, "randint", lambda a, b: 42)

    result = asyncio.run(
        cc._workflow_ltxv_prompt(
            "file",
            florence_model_name="m",
            auto_prompt_extra="",
            auto_prompt_suffix="",
            florence_seed=None,
            image_resize_height=1,
            image_resize_width=1,
        )
    )
    assert result == [b"final"]


def test_kill_thread_none():
    cc = get_ComfyCaller()()
    assert cc._kill_thread(None) is None


def test_get_defaults_image(monkeypatch):
    cc = get_ComfyCaller()()
    vals = {
        "comfy.image.loras": "a\nb",
        "comfy.image.batch_size": 1,
        "comfy.image.cfg": 0.1,
        "comfy.image.denoise": 0.2,
        "comfy.image.model_name": "m",
        "comfy.image.negative_prompt": "n",
        "comfy.image.output_height": 2,
        "comfy.image.output_width": 3,
        "comfy.image.prompt": "p",
        "comfy.image.sampler": "sam",
        "comfy.image.scheduler": "sch",
        "comfy.image.seed": None,
        "comfy.image.steps": 4,
    }
    monkeypatch.setattr(importlib.import_module("lair").config, "get", lambda k, *a, **kw: vals.get(k))
    defaults = cc._get_defaults_image()
    assert defaults["loras"] == ["a", "b"]
    assert defaults["batch_size"] == 1


class DummyAsyncWF:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class DummyAsyncNode:
    def __init__(self, result):
        self._result = result

    async def wait(self):
        return self._result


def test_workflow_image(monkeypatch):
    cc = get_ComfyCaller()()
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "Workflow", DummyAsyncWF, raising=False)
    monkeypatch.setattr(mod, "CheckpointLoaderSimple", lambda n: ("m", "c", "v"), raising=False)
    monkeypatch.setattr(cc, "_apply_loras", lambda m, c, loras: (m + "+l", c + "+l"))
    monkeypatch.setattr(mod, "CLIPTextEncode", lambda t, c: f"{t}:{c}", raising=False)
    monkeypatch.setattr(mod, "EmptyLatentImage", lambda *a: "latent", raising=False)
    monkeypatch.setattr(mod, "KSampler", lambda *a, **k: "latent2", raising=False)
    monkeypatch.setattr(mod, "VAEDecode", lambda latent, v: "img", raising=False)
    monkeypatch.setattr(mod, "SaveImage", lambda img, prefix: DummyAsyncNode(["ok"]), raising=False)
    monkeypatch.setattr(mod.random, "randint", lambda a, b: 5)
    images = asyncio.run(
        cc._workflow_image(
            model_name="m",
            prompt="p",
            loras=["l"],
            negative_prompt="n",
            output_width=1,
            output_height=1,
            batch_size=1,
            seed=None,
            steps=1,
            cfg=1,
            sampler="sam",
            scheduler="sch",
            denoise=0.5,
        )
    )
    assert images == ["ok"]


def test_workflow_upscale(monkeypatch):
    cc = get_ComfyCaller()()
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "UpscaleModelLoader", lambda n: f"m:{n}", raising=False)
    monkeypatch.setattr(cc.__class__, "_image_to_base64", lambda self, img: "b64", raising=False)
    monkeypatch.setattr(mod, "ETNLoadImageBase64", lambda b: ("img", None), raising=False)
    monkeypatch.setattr(mod, "ImageUpscaleWithModel", lambda model, img: "up", raising=False)
    monkeypatch.setattr(mod, "SaveImage", lambda img, prefix: DummyAsyncNode(["out"]), raising=False)
    res = asyncio.run(cc._workflow_upscale(source_image="src", model_name="m"))
    assert res == ["out"]


def test_workflow_outpaint(monkeypatch):
    cc = get_ComfyCaller()()
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "Workflow", DummyAsyncWF, raising=False)
    monkeypatch.setattr(mod, "CheckpointLoaderSimple", lambda n: ("m", "c", "v"), raising=False)
    monkeypatch.setattr(cc, "_apply_loras", lambda m, c, loras: (m, c))
    monkeypatch.setattr(mod, "CLIPTextEncode", lambda p, c: f"cond:{p}", raising=False)
    monkeypatch.setattr(cc.__class__, "_image_to_base64", lambda self, img: "b64", raising=False)
    monkeypatch.setattr(mod, "ETNLoadImageBase64", lambda b: ("img", None), raising=False)
    monkeypatch.setattr(mod, "ImagePadForOutpaint", lambda *a, **k: ("pad", "mask"), raising=False)
    monkeypatch.setattr(mod, "VAEEncodeForInpaint", lambda *a, **k: "latent", raising=False)
    monkeypatch.setattr(mod, "KSampler", lambda *a, **k: "latent2", raising=False)
    monkeypatch.setattr(mod, "VAEDecode", lambda latent, v: "img2", raising=False)
    monkeypatch.setattr(mod, "SaveImage", lambda *a, **k: DummyAsyncNode(["img"]), raising=False)
    monkeypatch.setattr(mod.random, "randint", lambda a, b: 42)
    images = asyncio.run(
        cc._workflow_outpaint(
            model_name="m",
            prompt="p",
            loras=None,
            negative_prompt="n",
            grow_mask_by=1,
            seed=None,
            source_image="src",
            steps=1,
            cfg=1,
            sampler="sam",
            scheduler="sch",
            denoise=0.5,
            padding_left=1,
            padding_top=1,
            padding_right=1,
            padding_bottom=1,
            feathering=1,
        )
    )
    assert images == ["img"]
