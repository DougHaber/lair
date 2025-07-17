import base64
import importlib
import types
import sys

import pytest

import lair


def get_ComfyCaller():
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
    cc = get_ComfyCaller()(url="http://example")
    return cc, queue


def test_parse_lora_argument():
    cc = get_ComfyCaller()()
    assert cc._parse_lora_argument("model") == ("model", 1.0, 1.0)
    assert cc._parse_lora_argument("model:0.5") == ("model", 0.5, 1.0)
    assert cc._parse_lora_argument("model:0.2:0.3") == ("model", 0.2, 0.3)


def test_apply_loras(monkeypatch):
    cc = get_ComfyCaller()()
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
    cc = get_ComfyCaller()()
    caller_mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(caller_mod.secrets, "randbelow", lambda a: 42)
    assert cc._ensure_seed(None) == 42
    assert cc._ensure_seed(9) == 9


def test_image_to_base64(tmp_path):
    file = tmp_path / "img.txt"
    content = b"data"
    file.write_bytes(content)
    cc = get_ComfyCaller()()
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
    cc = get_ComfyCaller()()

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
    cc = get_ComfyCaller()()

    async def handler():
        print("noisy")
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


import importlib
import types
import ssl
import sys
import asyncio

import pytest

import lair


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


def test_import_comfy_script_already(monkeypatch):
    cc = get_ComfyCaller()()
    cc.is_comfy_script_imported = True
    called = []
    monkeypatch.setattr(importlib, "import_module", lambda *a, **k: called.append(True))
    cc._import_comfy_script()
    assert called == []


def test_get_defaults_hunyuan_video_t2v(monkeypatch):
    cc = get_ComfyCaller()()
    vals = {
        "comfy.hunyuan_video.loras": "x\ny",
        "comfy.hunyuan_video.batch_size": 1,
        "comfy.hunyuan_video.clip_name_1": "c1",
        "comfy.hunyuan_video.clip_name_2": "c2",
        "comfy.hunyuan_video.denoise": 0.1,
        "comfy.hunyuan_video.height": 2,
        "comfy.hunyuan_video.frame_rate": 3,
        "comfy.hunyuan_video.guidance_scale": 0.2,
        "comfy.hunyuan_video.model_name": "m",
        "comfy.hunyuan_video.model_weight_dtype": "fp16",
        "comfy.hunyuan_video.num_frames": 4,
        "comfy.hunyuan_video.prompt": "p",
        "comfy.hunyuan_video.sampler": "sam",
        "comfy.hunyuan_video.sampling_shift": 0,
        "comfy.hunyuan_video.scheduler": "sch",
        "comfy.hunyuan_video.seed": None,
        "comfy.hunyuan_video.steps": 5,
        "comfy.hunyuan_video.tiled_decode.enabled": False,
        "comfy.hunyuan_video.tiled_decode.overlap": 1,
        "comfy.hunyuan_video.tiled_decode.tile_size": 2,
        "comfy.hunyuan_video.tiled_decode.temporal_overlap": 3,
        "comfy.hunyuan_video.tiled_decode.temporal_size": 4,
        "comfy.hunyuan_video.vae_model_name": "vae",
        "comfy.hunyuan_video.width": 6,
    }
    monkeypatch.setattr(importlib.import_module("lair").config, "get", lambda k, *a, **kw: vals.get(k))
    defaults = cc._get_defaults_hunyuan_video_t2v()
    assert defaults["loras"] == ["x", "y"]
    assert defaults["batch_size"] == 1


class DummySyncWF:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


def _setup_ltxv_i2v(monkeypatch, cc, prompt_provided):
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "Workflow", DummySyncWF, raising=False)
    monkeypatch.setattr(cc.__class__, "_image_to_base64", lambda self, img: "b64", raising=False)
    monkeypatch.setattr(mod, "CheckpointLoaderSimple", lambda m: ("model", "clip", "vae"), raising=False)
    monkeypatch.setattr(mod, "ETNLoadImageBase64", lambda b64: ("img", None), raising=False)
    monkeypatch.setattr(mod, "LTXVPreprocess", lambda img, n: img, raising=False)
    monkeypatch.setattr(mod, "ImageResizeKJ", lambda *a, **k: ("img2", 1, 1), raising=False)
    monkeypatch.setattr(mod, "CLIPLoader", lambda *a, **k: "clip", raising=False)
    if not prompt_provided:
        monkeypatch.setattr(mod, "DownloadAndLoadFlorence2Model", lambda *a, **k: "model2", raising=False)
        monkeypatch.setattr(
            mod, "Florence2Run", lambda *a, **k: (None, None, DummyNode({"text": ["auto"]}), None), raising=False
        )
        monkeypatch.setattr(mod, "StringReplaceMtb", lambda *a, **k: DummyNode({"text": ["auto"]}), raising=False)
        monkeypatch.setattr(mod, "StringFunctionPysssss", lambda *a, **k: DummyNode({"text": ["auto"]}), raising=False)
    monkeypatch.setattr(mod, "CLIPTextEncode", lambda t, c: f"enc:{t}", raising=False)
    monkeypatch.setattr(mod, "LTXVImgToVideo", lambda *a, **k: ("p", "n", "latent"), raising=False)
    monkeypatch.setattr(mod, "LTXVConditioning", lambda p, n, fr: (p, n), raising=False)
    monkeypatch.setattr(mod, "KSamplerSelect", lambda s: "sampler", raising=False)
    monkeypatch.setattr(mod, "LTXVScheduler", lambda *a: "sigmas", raising=False)
    monkeypatch.setattr(mod, "SamplerCustom", lambda *a: ("out", None), raising=False)
    monkeypatch.setattr(mod, "VAEDecode", lambda *a: "frames", raising=False)
    monkeypatch.setattr(mod, "VHSVideoCombine", lambda **k: DummyNode({"gifs": [{"filename": "f"}]}), raising=False)
    monkeypatch.setattr(mod.secrets, "randbelow", lambda a: 7)
    monkeypatch.setattr(cc, "view", lambda f: f"view:{f}")


def test_workflow_ltxv_i2v(monkeypatch):
    cc = get_ComfyCaller()()
    _setup_ltxv_i2v(monkeypatch, cc, prompt_provided=True)
    videos = asyncio.run(
        cc._workflow_ltxv_i2v(
            "img",
            model_name="m",
            clip_name="c",
            image_resize_height=1,
            image_resize_width=1,
            num_frames=1,
            frame_rate_conditioning=1,
            frame_rate_save=1,
            batch_size=1,
            florence_model_name="fm",
            max_shift=0,
            base_shift=0,
            stretch=0,
            terminal=False,
            negative_prompt="n",
            auto_prompt_suffix="s",
            auto_prompt_extra="e",
            prompt="given",
            cfg=1,
            sampler="sam",
            scheduler="sch",
            steps=1,
            pingpong=False,
            output_format="webp",
            denoise=0.5,
            seed=None,
            florence_seed=1,
        )
    )
    assert videos == ["view:f"]


def test_workflow_ltxv_i2v_prompt_auto(monkeypatch):
    cc = get_ComfyCaller()()
    _setup_ltxv_i2v(monkeypatch, cc, prompt_provided=False)
    videos = asyncio.run(
        cc._workflow_ltxv_i2v(
            "img",
            model_name="m",
            clip_name="c",
            image_resize_height=1,
            image_resize_width=1,
            num_frames=1,
            frame_rate_conditioning=1,
            frame_rate_save=1,
            batch_size=1,
            florence_model_name="fm",
            max_shift=0,
            base_shift=0,
            stretch=0,
            terminal=False,
            negative_prompt="n",
            auto_prompt_suffix="s",
            auto_prompt_extra="e",
            prompt=None,
            cfg=1,
            sampler="sam",
            scheduler="sch",
            steps=1,
            pingpong=False,
            output_format="webp",
            denoise=0.5,
            seed=None,
            florence_seed=None,
        )
    )
    assert videos == ["view:f"]


def _setup_hunyuan(monkeypatch, cc, tiled):
    mod = importlib.import_module("lair.comfy_caller")
    monkeypatch.setattr(mod, "RandomNoise", lambda s: f"noise:{s}")
    monkeypatch.setattr(mod, "UNETLoader", lambda n, d: "model", raising=False)
    monkeypatch.setattr(mod, "DualCLIPLoader", lambda a, b, c, d: "clip", raising=False)
    monkeypatch.setattr(mod, "CLIPTextEncode", lambda t, c: f"enc:{t}", raising=False)
    monkeypatch.setattr(mod, "FluxGuidance", lambda c, g: f"flux:{g}", raising=False)
    monkeypatch.setattr(mod, "ModelSamplingSD3", lambda m, s: "shifted", raising=False)
    monkeypatch.setattr(mod, "BasicGuider", lambda m, c: "guider", raising=False)
    monkeypatch.setattr(mod, "KSamplerSelect", lambda s: "ksel", raising=False)
    monkeypatch.setattr(mod, "BasicScheduler", lambda m, m2, steps, denoise: "sig", raising=False)
    monkeypatch.setattr(mod, "EmptyHunyuanLatentVideo", lambda *a: "latent", raising=False)
    monkeypatch.setattr(mod, "SamplerCustomAdvanced", lambda *a: ("latent2", None), raising=False)
    monkeypatch.setattr(mod, "VAELoader", lambda n: "vae", raising=False)
    monkeypatch.setattr(mod, "VAEDecodeTiled", lambda *a: "img_t", raising=False)
    monkeypatch.setattr(mod, "VAEDecode", lambda *a: "img", raising=False)
    monkeypatch.setattr(
        mod, "SaveAnimatedWEBP", lambda *a, **k: DummyNode({"images": [{"filename": "f"}]}), raising=False
    )
    monkeypatch.setattr(mod.secrets, "randbelow", lambda a: 5)
    monkeypatch.setattr(cc, "view", lambda f, type="output": f"view:{f}:{type}")


@pytest.mark.parametrize("tiled", [False, True])
def test_workflow_hunyuan_video_t2v(monkeypatch, tiled):
    cc = get_ComfyCaller()()
    _setup_hunyuan(monkeypatch, cc, tiled)
    videos = asyncio.run(
        cc._workflow_hunyuan_video_t2v(
            batch_size=1,
            clip_name_1="c1",
            clip_name_2="c2",
            denoise=0.1,
            frame_rate=1,
            guidance_scale=0.2,
            height=1,
            loras=None,
            model_name="m",
            num_frames=1,
            model_weight_dtype="fp16",
            prompt="p",
            sampler="sam",
            sampling_shift=0,
            scheduler="sch",
            seed=None,
            steps=1,
            tile_overlap=0,
            tile_size=1,
            tile_temporal_size=1,
            tile_temporal_overlap=0,
            tiled_decode_enabled=tiled,
            width=1,
            vae_model_name="vae",
        )
    )
    assert videos == ["view:f:output"]
