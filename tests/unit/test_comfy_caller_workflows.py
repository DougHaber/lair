import asyncio
import importlib
import ssl
import sys
import types

import pytest

import lair
from tests.helpers.comfy_caller import get_comfy_caller


class DummyNode:
    def __init__(self, output):
        self._output = output

    def wait(self):
        return self


def test_monkey_patch_comfy_script(monkeypatch):
    importlib.import_module("lair.comfy_caller")
    cc = get_comfy_caller()()

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
    cc = get_comfy_caller()(url="http://unit.test")

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
    cc = get_comfy_caller()(url="http://same")
    called = []
    monkeypatch.setattr(cc, "_import_comfy_script", lambda: called.append(True))
    cc.set_url("http://same")
    assert called == []

    cc2 = get_comfy_caller()()
    called2 = []
    monkeypatch.setattr(cc2, "_import_comfy_script", lambda: called2.append(True))
    cc2.set_url("http://new")
    assert cc2.url == "http://new"
    assert called2 == [True]

    error = None
    try:
        cc.set_url("http://other")
    except Exception as exc:
        error = exc
    assert error is not None


def test_view(monkeypatch):
    cc = get_comfy_caller()(url="http://server")
    responses = []

    class Resp:
        def __init__(self, code, content=b""):
            self.status_code = code
            self.content = content

    def fake_get(url, params, verify, timeout=None):
        responses.append((url, params, verify, timeout))
        return Resp(200, b"data")

    monkeypatch.setattr(importlib.import_module("lair.comfy_caller").requests, "get", fake_get, raising=False)
    result = cc.view("file")
    assert result == b"data"
    assert responses[0][0] == "http://server/api/view"
    assert responses[0][3] == lair.config.get("comfy.timeout")

    monkeypatch.setattr(
        importlib.import_module("lair.comfy_caller").requests, "get", lambda *a, **k: Resp(404), raising=False
    )
    error = None
    try:
        cc.view("bad")
    except Exception as exc:
        error = exc
    assert error is not None


def test_kill_thread(monkeypatch):
    cc = get_comfy_caller()()
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
    cc = get_comfy_caller()()
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
    monkeypatch.setattr(caller_mod.secrets, "randbelow", lambda a: 42)

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
    cc = get_comfy_caller()()
    assert cc._kill_thread(None) is None


def test_get_defaults_image(monkeypatch):
    cc = get_comfy_caller()()
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
    cc = get_comfy_caller()()
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "Workflow", DummyAsyncWF, raising=False)
    monkeypatch.setattr(mod, "CheckpointLoaderSimple", lambda n: ("m", "c", "v"), raising=False)
    monkeypatch.setattr(cc, "_apply_loras", lambda m, c, loras: (m + "+l", c + "+l"))
    monkeypatch.setattr(mod, "CLIPTextEncode", lambda t, c: f"{t}:{c}", raising=False)
    monkeypatch.setattr(mod, "EmptyLatentImage", lambda *a: "latent", raising=False)
    monkeypatch.setattr(mod, "KSampler", lambda *a, **k: "latent2", raising=False)
    monkeypatch.setattr(mod, "VAEDecode", lambda latent, v: "img", raising=False)
    monkeypatch.setattr(mod, "SaveImage", lambda img, prefix: DummyAsyncNode(["ok"]), raising=False)
    monkeypatch.setattr(mod.secrets, "randbelow", lambda a: 5)
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
    cc = get_comfy_caller()()
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "UpscaleModelLoader", lambda n: f"m:{n}", raising=False)
    monkeypatch.setattr(cc.__class__, "_image_to_base64", lambda self, img: "b64", raising=False)
    monkeypatch.setattr(mod, "ETNLoadImageBase64", lambda b: ("img", None), raising=False)
    monkeypatch.setattr(mod, "ImageUpscaleWithModel", lambda model, img: "up", raising=False)
    monkeypatch.setattr(mod, "SaveImage", lambda img, prefix: DummyAsyncNode(["out"]), raising=False)
    res = asyncio.run(cc._workflow_upscale(source_image="src", model_name="m"))
    assert res == ["out"]


def test_workflow_outpaint(monkeypatch):
    cc = get_comfy_caller()()
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
    monkeypatch.setattr(mod.secrets, "randbelow", lambda a: 42)
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


def test_import_comfy_script_noop(monkeypatch):
    cc = get_comfy_caller()(url="http://unit")
    cc.is_comfy_script_imported = True
    called = []
    monkeypatch.setattr(importlib, "import_module", lambda *a, **k: called.append(a))
    monkeypatch.setattr(cc, "_monkey_patch_comfy_script", lambda: called.append("patch"))
    cc._import_comfy_script()
    assert called == []


def test_get_defaults_hunyuan_and_outpaint(monkeypatch):
    cc = get_comfy_caller()()
    hv = {
        "comfy.hunyuan_video.loras": "x\ny",
        "comfy.hunyuan_video.batch_size": 2,
    }
    op = {
        "comfy.outpaint.loras": "a\nb",
        "comfy.outpaint.cfg": 1,
    }

    def fake_get(key, *a, **k):
        return hv.get(key) if key in hv else op.get(key)

    monkeypatch.setattr(importlib.import_module("lair").config, "get", fake_get)
    hv_defaults = cc._get_defaults_hunyuan_video_t2v()
    op_defaults = cc._get_defaults_outpaint()
    assert hv_defaults["loras"] == ["x", "y"]
    assert hv_defaults["batch_size"] == 2
    assert op_defaults["loras"] == ["a", "b"]
    assert op_defaults["cfg"] == 1


class DummyWF:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


def test_workflow_ltxv_i2v(monkeypatch):
    cc = get_comfy_caller()()
    with pytest.raises(ValueError):
        asyncio.run(
            cc._workflow_ltxv_i2v(
                None,
                model_name="m",
                clip_name="c",
                image_resize_height=1,
                image_resize_width=1,
                num_frames=1,
                frame_rate_conditioning=1,
                frame_rate_save=1,
                batch_size=1,
                florence_model_name="f",
                max_shift=1,
                base_shift=1,
                stretch=1,
                terminal=1,
                negative_prompt="n",
                auto_prompt_suffix="s",
                auto_prompt_extra="e",
                prompt="p",
                cfg=1,
                sampler="sam",
                scheduler="sch",
                steps=1,
                pingpong=False,
                output_format="gif",
                denoise=0.1,
                seed=1,
                florence_seed=1,
            )
        )

    caller_mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(caller_mod, "CheckpointLoaderSimple", lambda n: ("m", "c", "v"), raising=False)
    monkeypatch.setattr(caller_mod, "Workflow", DummyWF, raising=False)
    monkeypatch.setattr(cc.__class__, "_image_to_base64", lambda self, img: "b64")
    monkeypatch.setattr(caller_mod, "ETNLoadImageBase64", lambda b: ("img", None))
    monkeypatch.setattr(caller_mod, "LTXVPreprocess", lambda img, s: "prep")
    monkeypatch.setattr(caller_mod, "ImageResizeKJ", lambda *a, **k: ("img2", 2, 3))
    monkeypatch.setattr(caller_mod, "CLIPLoader", lambda *a, **k: "clip")
    monkeypatch.setattr(caller_mod, "DownloadAndLoadFlorence2Model", lambda *a, **k: "model")
    monkeypatch.setattr(caller_mod, "Florence2Run", lambda *a, **k: (None, None, DummyNode({"text": ["p"]}), None))
    monkeypatch.setattr(caller_mod, "StringReplaceMtb", lambda *a, **k: DummyNode({"text": ["p"]}))
    monkeypatch.setattr(caller_mod, "StringFunctionPysssss", lambda *a, **k: DummyNode({"text": ["final"]}))
    monkeypatch.setattr(caller_mod, "CLIPTextEncode", lambda t, c: f"{t}/{c}")
    monkeypatch.setattr(caller_mod, "LTXVImgToVideo", lambda *a, **k: ("pos", "neg", "latent"))
    monkeypatch.setattr(caller_mod, "LTXVConditioning", lambda p, n, f: (p, n))
    monkeypatch.setattr(caller_mod, "KSamplerSelect", lambda s: "sampler")
    monkeypatch.setattr(caller_mod, "LTXVScheduler", lambda *a, **k: "sigmas")
    monkeypatch.setattr(caller_mod, "SamplerCustom", lambda *a, **k: ("out", None))
    monkeypatch.setattr(caller_mod, "VAEDecode", lambda output, v: "frames")
    monkeypatch.setattr(caller_mod, "VHSVideoCombine", lambda **k: DummyNode({"gifs": [{"filename": "vid"}]}))
    monkeypatch.setattr(cc, "view", lambda f: f"view:{f}")
    monkeypatch.setattr(cc, "_ensure_seed", lambda s: 5)

    result = asyncio.run(
        cc._workflow_ltxv_i2v(
            "file",
            model_name="m",
            clip_name="c",
            image_resize_height=1,
            image_resize_width=1,
            num_frames=1,
            frame_rate_conditioning=1,
            frame_rate_save=1,
            batch_size=1,
            florence_model_name="f",
            max_shift=1,
            base_shift=1,
            stretch=1,
            terminal=1,
            negative_prompt="n",
            auto_prompt_suffix="s",
            auto_prompt_extra="e",
            prompt=None,
            cfg=1,
            sampler="sam",
            scheduler="sch",
            steps=1,
            pingpong=False,
            output_format="gif",
            denoise=0.1,
            seed=None,
            florence_seed=None,
        )
    )
    assert result == ["view:vid"]


def test_workflow_hunyuan_video_t2v(monkeypatch):
    cc = get_comfy_caller()()
    caller_mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(caller_mod, "RandomNoise", lambda s: f"noise{s}")
    monkeypatch.setattr(caller_mod, "UNETLoader", lambda n, d: f"unet:{n}:{d}")
    monkeypatch.setattr(caller_mod, "DualCLIPLoader", lambda *a: "clip")
    monkeypatch.setattr(cc, "_apply_loras", lambda model, cfg, loras: (model, cfg))
    monkeypatch.setattr(caller_mod, "CLIPTextEncode", lambda p, c: f"{p}/{c}")
    monkeypatch.setattr(caller_mod, "FluxGuidance", lambda c, g: f"flux:{c}:{g}")
    monkeypatch.setattr(caller_mod, "ModelSamplingSD3", lambda m, s: f"shift:{m}:{s}")
    monkeypatch.setattr(caller_mod, "BasicGuider", lambda m, c: f"guide:{m}:{c}")
    monkeypatch.setattr(caller_mod, "KSamplerSelect", lambda *a: "sampler")
    monkeypatch.setattr(caller_mod, "BasicScheduler", lambda *a, **k: "sigmas")
    monkeypatch.setattr(caller_mod, "EmptyHunyuanLatentVideo", lambda *a: "latent")
    monkeypatch.setattr(caller_mod, "SamplerCustomAdvanced", lambda *a, **k: ("latent", None))
    monkeypatch.setattr(caller_mod, "VAELoader", lambda n: "vae")
    monkeypatch.setattr(caller_mod, "VAEDecodeTiled", lambda *a, **k: "img")
    monkeypatch.setattr(caller_mod, "SaveAnimatedWEBP", lambda *a, **k: DummyNode({"images": [{"filename": "vid"}]}))
    monkeypatch.setattr(cc, "view", lambda f, type="output": f"view:{f}")
    monkeypatch.setattr(cc, "_ensure_seed", lambda s: 1)

    result = asyncio.run(
        cc._workflow_hunyuan_video_t2v(
            batch_size=1,
            clip_name_1="c1",
            clip_name_2="c2",
            denoise=0.1,
            frame_rate=24,
            guidance_scale=1.0,
            height=64,
            loras=None,
            model_name="m",
            num_frames=2,
            model_weight_dtype="fp16",
            prompt="p",
            sampler="sampler",
            sampling_shift=1.0,
            scheduler="sch",
            seed=None,
            steps=2,
            tile_overlap=1,
            tile_size=64,
            tile_temporal_size=2,
            tile_temporal_overlap=1,
            tiled_decode_enabled=True,
            width=64,
            vae_model_name="vae",
        )
    )
    assert result == ["view:vid"]
