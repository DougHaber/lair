"""
Run ComfyUI workflows.

This module provides utilities for invoking ComfyUI workflows from Python.  It
delegates the heavy lifting to a running ComfyUI server and handles the minor
quirks of the ``comfy_script`` library.  Workflows are defined as async
functions regardless of whether they internally await.

The original implementation bundled diffusion libraries directly which made the
tool considerably slower to install and run.  Offloading to ComfyUI allows us to
reuse its optimised implementations and avoids reloading models for every run.
"""

import asyncio
import base64
import contextlib
import ctypes
import importlib
import io
import secrets
import threading
from typing import Any, Callable, cast

import requests

import lair
from lair.logging import logger  # noqa

Workflow: Any = None
LoraLoader: Any = None
CheckpointLoaderSimple: Any = None
CLIPTextEncode: Any = None
EmptyLatentImage: Any = None
KSampler: Any = None
VAEDecode: Any = None
SaveImage: Any = None
ETNLoadImageBase64: Any = None
LTXVPreprocess: Any = None
ImageResizeKJ: Any = None
CLIPLoader: Any = None
DownloadAndLoadFlorence2Model: Any = None
Florence2Run: Any = None
StringReplaceMtb: Any = None
StringFunctionPysssss: Any = None
LTXVImgToVideo: Any = None
LTXVConditioning: Any = None
KSamplerSelect: Any = None
LTXVScheduler: Any = None
SamplerCustom: Any = None
VHSVideoCombine: Any = None
RandomNoise: Any = None
UNETLoader: Any = None
DualCLIPLoader: Any = None
FluxGuidance: Any = None
ModelSamplingSD3: Any = None
BasicGuider: Any = None
BasicScheduler: Any = None
EmptyHunyuanLatentVideo: Any = None
SamplerCustomAdvanced: Any = None
VAELoader: Any = None
VAEDecodeTiled: Any = None
SaveAnimatedWEBP: Any = None
ImagePadForOutpaint: Any = None
VAEEncodeForInpaint: Any = None
ImageUpscaleWithModel: Any = None
UpscaleModelLoader: Any = None


class ComfyCaller:
    """Interface to a running ComfyUI server."""

    def __init__(self, url: str | None = None, output_prefix: str = "ComfyUI") -> None:
        """
        Create a new caller.

        Args:
            url: Base URL of the ComfyUI server.
            output_prefix: Filename prefix for any saved outputs.

        """
        self.url = url
        self.output_prefix = output_prefix

        self.workflows: dict[str, Callable[..., Any]] = {}
        self.is_comfy_script_imported = False

        self._init_defaults()
        self._init_workflows()

        # If the config changes, update all defaults
        lair.events.subscribe("config.update", lambda d: self._init_defaults(), instance=self)

    def _monkey_patch_comfy_script(self) -> None:
        """
        Disable SSL verification in ``comfy_script``.

        ``comfy_script`` does not expose a way to disable SSL verification.  This
        method patches ``aiohttp.TCPConnector`` to use a custom SSL context with
        hostname checks disabled.
        """
        import ssl

        import aiohttp

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        original_init = cast(Callable[..., Any], aiohttp.TCPConnector.__init__)

        def patched_init(self: aiohttp.TCPConnector, *args: object, **kwargs: object) -> None:
            """Override connector initialisation to disable SSL verification."""
            kwargs["ssl"] = ssl_context
            return original_init(self, *args, **kwargs)

        aiohttp.TCPConnector.__init__ = cast(Any, patched_init)

    def _import_comfy_script(self) -> None:
        """Import ``comfy_script`` and load node definitions."""
        # The imports actually connect to the server. If the defaults are being requested, that is problematic
        # since that happens before the server URL is provided. To work around that, importing is deferred
        if self.is_comfy_script_imported is True:
            return

        # ComfyScript behaves poorly with output and writes debugging with
        # print() statements that can not be properly disabled. To deal with
        # this, STDOUT is ignored on import.
        with contextlib.redirect_stdout(io.StringIO()):
            runtime_module = importlib.import_module("comfy_script.runtime")
            load = runtime_module.load
            workflow_local = runtime_module.Workflow

            globals()["load"] = load
            globals()["Workflow"] = workflow_local

            if lair.config.get("comfy.verify_ssl") is False:
                self._monkey_patch_comfy_script()

            load(self.url)

            nodes_module = importlib.import_module("comfy_script.runtime.nodes")
            nodes = {name: getattr(nodes_module, name) for name in dir(nodes_module) if not name.startswith("_")}
            globals().update(nodes)

        self.is_comfy_script_imported = True

    def _init_workflows(self) -> None:
        """Register workflow handlers."""
        self.workflows = {
            "hunyuan-video-t2v": self._workflow_hunyuan_video_t2v,
            "image": self._workflow_image,
            "ltxv-i2v": self._workflow_ltxv_i2v,
            "ltxv-prompt": self._workflow_ltxv_prompt,
            "outpaint": self._workflow_outpaint,
            "upscale": self._workflow_upscale,
        }

    def _init_defaults(self) -> None:
        """Load default configuration values for each workflow."""
        self.defaults = {
            "hunyuan-video-t2v": self._get_defaults_hunyuan_video_t2v(),
            "image": self._get_defaults_image(),
            "ltxv-i2v": self._get_defaults_ltxv_i2v(),
            "ltxv-prompt": self._get_defaults_ltxv_prompt(),
            "outpaint": self._get_defaults_outpaint(),
            "upscale": self._get_defaults_upscale(),
        }

    def _parse_lora_argument(self, lora: str) -> tuple[str, float, float]:
        """Split a lora argument into its components."""
        parts = lora.split(":", maxsplit=3)

        lora_model = parts.pop(0)
        weight = 1.0
        clip_weight = 1.0

        # If there are more values, override the defaults for their components
        if parts:
            weight = float(parts.pop(0))
        if parts:
            clip_weight = float(parts.pop(0))

        return lora_model, weight, clip_weight

    def _apply_loras(self, model: object, clip: object, loras: list[str] | None) -> tuple[object, object]:
        """Apply a list of loras to the model and clip."""
        for lora in loras or []:
            lora_model, weight, clip_weight = self._parse_lora_argument(lora)
            model, clip = LoraLoader(model, clip, lora_model, weight, clip_weight)

        return model, clip

    def _ensure_seed(self, seed: int | None) -> int:
        """Return a random seed when one is not provided."""
        return secrets.randbelow(2**31) if seed is None else seed

    def _image_to_base64(self, image: str) -> str:
        """Return the base64 representation of an image file."""
        if not isinstance(image, str):
            raise ValueError("image must be a string path")

        with open(image, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _ensure_watch_thread(self) -> None:
        """Start the ComfyScript watch thread if it is not running."""
        runtime = importlib.import_module("comfy_script.runtime")

        queue = runtime.queue
        watch = getattr(queue, "_watch_thread", None)
        if watch is None or not watch.is_alive():
            queue.start_watch(False, False, False)

    def _kill_thread(self, thread: threading.Thread | None) -> None:
        """Terminate a running thread."""
        if thread is None:
            return
        try:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident or 0), ctypes.py_object(SystemExit))
        except Exception:
            logger.debug("Failed to terminate ComfyScript thread")

    def _cleanup_watch_thread(self) -> None:
        """Stop the watch thread created by ``comfy_script``."""
        runtime = importlib.import_module("comfy_script.runtime")

        queue = runtime.queue
        watch = getattr(queue, "_watch_thread", None)
        if watch and watch.is_alive():
            self._kill_thread(watch)
        queue._watch_thread = None

    def run_workflow(self, workflow: str, *args: object, **kwargs: object) -> object:
        """
        Execute a registered workflow.

        Args:
            workflow: Name of the workflow to run.
            *args: Positional arguments passed to the workflow.
            **kwargs: Keyword arguments passed to the workflow.

        Returns:
            The value returned by the workflow function.

        """
        logger.debug(f"run_workflow({workflow}, {kwargs})")
        handler = self.workflows[workflow]
        kwargs = {**self.defaults[workflow], **kwargs}

        self._ensure_watch_thread()

        if lair.util.is_debug_enabled():
            result = asyncio.run(handler(*args, **kwargs))
        else:
            # With debug disabled, try to quiet things down.
            # Unfortunately, its threads print output even after the workflow completes, so some output will still leak.
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = asyncio.run(handler(*args, **kwargs))

        self._cleanup_watch_thread()

        return result

    def set_url(self, url: str) -> None:
        """Configure the ComfyUI server URL."""
        if url == self.url:  # If setting the same value, no change is needed
            return
        elif self.url is not None:
            # This should be supported, but we'll need to look into the ComfyScript repo
            # to figure out how
            raise Exception("ComfyCaller(): Modifying a Comfy URL is not supported.")
        else:
            self.url = url
            self._import_comfy_script()

    def _get_defaults_image(self) -> dict[str, Any]:
        """Return default parameters for the ``image`` workflow."""
        loras_val = lair.config.get("comfy.image.loras")
        loras = [lora for lora in str(loras_val).split("\n") if lora] if loras_val is not None else None

        return {
            "batch_size": lair.config.get("comfy.image.batch_size"),
            "cfg": lair.config.get("comfy.image.cfg"),
            "denoise": lair.config.get("comfy.image.denoise"),
            "loras": loras,
            "model_name": lair.config.get("comfy.image.model_name"),
            "negative_prompt": lair.config.get("comfy.image.negative_prompt"),
            "output_height": lair.config.get("comfy.image.output_height"),
            "output_width": lair.config.get("comfy.image.output_width"),
            "prompt": lair.config.get("comfy.image.prompt"),
            "sampler": lair.config.get("comfy.image.sampler"),
            "scheduler": lair.config.get("comfy.image.scheduler"),
            "seed": lair.config.get("comfy.image.seed"),
            "steps": lair.config.get("comfy.image.steps"),
        }

    def view(self, filename: str, type: str = "temp") -> bytes:
        """Retrieve an image or video from the ComfyUI server."""
        response = requests.get(
            f"{self.url}/api/view",
            params={"filename": filename, "type": type},
            verify=bool(lair.config.get("comfy.verify_ssl", True)),
            timeout=cast(float | tuple[float, float] | tuple[float, None] | None, lair.config.get("comfy.timeout")),
        )
        if response.status_code != 200:
            raise Exception(f"/api/view returned unexpected status code: {response.status_code}")
        else:
            return response.content

    async def _workflow_image(
        self,
        *,
        model_name: str,
        prompt: str,
        loras: list[str] | None,
        negative_prompt: str,
        output_width: int,
        output_height: int,
        batch_size: int,
        seed: int | None,
        steps: int,
        cfg: float,
        sampler: str,
        scheduler: str,
        denoise: float,
    ) -> list[str]:
        """Generate images using a text prompt."""
        seed = self._ensure_seed(seed)

        async with Workflow():
            model, clip, vae = CheckpointLoaderSimple(model_name)

            model, clip = self._apply_loras(model, clip, loras)

            positive_conditioning = CLIPTextEncode(prompt, clip)
            negative_conditioning = CLIPTextEncode(negative_prompt, clip)
            latent = EmptyLatentImage(output_width, output_height, batch_size)

            latent = KSampler(
                model,
                seed,
                steps,
                cfg,
                sampler,
                scheduler,
                positive_conditioning,
                negative_conditioning,
                latent,
                denoise,
            )
            image = VAEDecode(latent, vae)
            save_image_node = SaveImage(image, self.output_prefix)

            images = await save_image_node.wait()

        return images

    def _get_defaults_ltxv_i2v(self) -> dict[str, Any]:
        """Return default parameters for the ``ltxv-i2v`` workflow."""
        return {
            "auto_prompt_extra": lair.config.get("comfy.ltxv_i2v.auto_prompt_extra"),
            "auto_prompt_suffix": lair.config.get("comfy.ltxv_i2v.auto_prompt_suffix"),
            "base_shift": lair.config.get("comfy.ltxv_i2v.scheduler_base_shift"),
            "batch_size": lair.config.get("comfy.ltxv_i2v.batch_size"),
            "cfg": lair.config.get("comfy.ltxv_i2v.cfg"),
            "clip_name": lair.config.get("comfy.ltxv_i2v.clip_name"),
            "denoise": lair.config.get("comfy.ltxv_i2v.denoise"),
            "florence_model_name": lair.config.get("comfy.ltxv_i2v.florence_model_name"),
            "florence_seed": lair.config.get("comfy.ltxv_i2v.florence_seed"),
            "frame_rate_conditioning": lair.config.get("comfy.ltxv_i2v.frame_rate_conditioning"),
            "frame_rate_save": lair.config.get("comfy.ltxv_i2v.frame_rate_save"),
            "image": None,
            "image_resize_height": lair.config.get("comfy.ltxv_i2v.image_resize_height"),
            "image_resize_width": lair.config.get("comfy.ltxv_i2v.image_resize_width"),
            "max_shift": lair.config.get("comfy.ltxv_i2v.scheduler_max_shift"),
            "model_name": lair.config.get("comfy.ltxv_i2v.model_name"),
            "negative_prompt": lair.config.get("comfy.ltxv_i2v.negative_prompt"),
            "num_frames": lair.config.get("comfy.ltxv_i2v.num_frames"),
            "output_format": lair.config.get("comfy.ltxv_i2v.output_format"),
            "pingpong": lair.config.get("comfy.ltxv_i2v.pingpong"),
            "prompt": lair.config.get("comfy.ltxv_i2v.prompt"),
            "sampler": lair.config.get("comfy.ltxv_i2v.sampler"),
            "scheduler": lair.config.get("comfy.ltxv_i2v.scheduler"),
            "seed": lair.config.get("comfy.ltxv_i2v.seed"),
            "steps": lair.config.get("comfy.ltxv_i2v.steps"),
            "stretch": lair.config.get("comfy.ltxv_i2v.scheduler_stretch"),
            "terminal": lair.config.get("comfy.ltxv_i2v.scheduler_terminal"),
        }

    async def _workflow_ltxv_i2v(
        self,
        image: str,
        *,
        model_name: str,
        clip_name: str,
        image_resize_height: int,
        image_resize_width: int,
        num_frames: int,
        frame_rate_conditioning: int,
        frame_rate_save: int,
        batch_size: int,
        florence_model_name: str,
        max_shift: float,
        base_shift: float,
        stretch: float,
        terminal: int,
        negative_prompt: str,
        auto_prompt_suffix: str,
        auto_prompt_extra: str,
        prompt: str | None,
        cfg: float,
        sampler: str,
        scheduler: str,
        steps: int,
        pingpong: bool,
        output_format: str,
        denoise: float,
        seed: int | None,
        florence_seed: int | None,
    ) -> list[bytes]:
        """Convert an input image to video using the LTXV workflow."""
        if image is None:
            raise ValueError("ltxv-i2v: Image must not be None")
        seed = self._ensure_seed(seed)
        florence_seed = self._ensure_seed(florence_seed)

        with Workflow():
            model, _, vae = CheckpointLoaderSimple(model_name)
            image, _ = ETNLoadImageBase64(self._image_to_base64(image))
            image = LTXVPreprocess(image, 40)
            image2, width, height = ImageResizeKJ(
                image, image_resize_height, image_resize_width, "bilinear", True, 32, 0, 0, None, "disabled"
            )
            clip = CLIPLoader(clip_name, "ltxv", "default")

            if prompt is None:  # If a prompt is not provided, automatically generate one
                florence2_model = DownloadAndLoadFlorence2Model(florence_model_name, "fp16", "sdpa", None)
                _, _, prompt, _ = Florence2Run(
                    image, florence2_model, "", "more_detailed_caption", True, False, 256, 3, True, "", florence_seed
                )
                prompt = StringReplaceMtb(prompt, "image", "video")
                prompt = StringReplaceMtb(prompt, "photo", "video")
                prompt = StringReplaceMtb(prompt, "painting", "video")
                prompt = StringReplaceMtb(prompt, "illustration", "video")
                prompt = StringFunctionPysssss("append", "no", prompt, auto_prompt_extra, auto_prompt_suffix)

            positive = CLIPTextEncode(prompt, clip)
            negative = CLIPTextEncode(negative_prompt, clip)
            positive, negative, latent = LTXVImgToVideo(positive, negative, vae, image, width, height, num_frames, 1)
            positive, negative = LTXVConditioning(positive, negative, frame_rate_conditioning)

            sampler = KSamplerSelect(sampler)
            sigmas = LTXVScheduler(steps, max_shift, base_shift, stretch, terminal, latent)

            output, _ = SamplerCustom(model, True, seed, cfg, positive, negative, sampler, sigmas, latent)
            frames = VAEDecode(output, vae)

            video_node = VHSVideoCombine(
                images=frames,
                frame_rate=frame_rate_save,
                loop_count=0,
                filename_prefix="LTXVideo",
                format=output_format,
                pingpong=pingpong,
                save_output=False,
                audio=None,
                meta_batch=None,
                vae=None,
            )

        videos = []
        for video in video_node.wait()._output["gifs"]:
            videos.append(self.view(video["filename"]))

        return videos

    def _get_defaults_ltxv_prompt(self) -> dict[str, Any]:
        """Return default parameters for the ``ltxv-prompt`` workflow."""
        return {
            "auto_prompt_extra": lair.config.get("comfy.ltxv_prompt.auto_prompt_extra"),
            "auto_prompt_suffix": lair.config.get("comfy.ltxv_prompt.auto_prompt_suffix"),
            "florence_model_name": lair.config.get("comfy.ltxv_prompt.florence_model_name"),
            "florence_seed": lair.config.get("comfy.ltxv_prompt.florence_seed"),
            "image": None,
            "image_resize_height": lair.config.get("comfy.ltxv_prompt.image_resize_height"),
            "image_resize_width": lair.config.get("comfy.ltxv_prompt.image_resize_width"),
        }

    async def _workflow_ltxv_prompt(
        self,
        image: str,
        *,
        florence_model_name: str,
        auto_prompt_extra: str,
        auto_prompt_suffix: str,
        florence_seed: int | None,
        image_resize_height: int,
        image_resize_width: int,
    ) -> list[bytes]:
        """Generate a prompt for a given image."""
        if image is None:
            raise ValueError("ltxv-prompt: Image must not be None")
        if florence_seed is None:
            florence_seed = secrets.randbelow(2**31)

        with Workflow():
            image, _ = ETNLoadImageBase64(self._image_to_base64(image))
            image2, width, height = ImageResizeKJ(
                image, image_resize_height, image_resize_width, "bilinear", True, 32, 0, 0, None, "disabled"
            )
            florence2_model = DownloadAndLoadFlorence2Model(florence_model_name, "fp16", "sdpa", None)
            _, _, prompt, _ = Florence2Run(
                image, florence2_model, "", "more_detailed_caption", True, False, 256, 3, True, "", florence_seed
            )
            prompt = StringReplaceMtb(prompt, "image", "video")
            prompt = StringReplaceMtb(prompt, "photo", "video")
            prompt = StringReplaceMtb(prompt, "painting", "video")
            prompt = StringReplaceMtb(prompt, "illustration", "video")
            prompt = StringFunctionPysssss("append", "no", prompt, auto_prompt_extra, auto_prompt_suffix)

        prompts = []
        for line in prompt.wait()._output["text"]:
            # Encoding is used so that the save file bytes() support can write the output
            prompts.append(line.encode())

        return prompts

    def _get_defaults_hunyuan_video_t2v(self) -> dict[str, Any]:
        """Return default parameters for the hunyuan-video-t2v workflow."""
        loras_val = lair.config.get("comfy.hunyuan_video.loras")
        loras = [lora for lora in str(loras_val).split("\n") if lora] if loras_val is not None else None

        return {
            "batch_size": lair.config.get("comfy.hunyuan_video.batch_size"),
            "clip_name_1": lair.config.get("comfy.hunyuan_video.clip_name_1"),
            "clip_name_2": lair.config.get("comfy.hunyuan_video.clip_name_2"),
            "denoise": lair.config.get("comfy.hunyuan_video.denoise"),
            "height": lair.config.get("comfy.hunyuan_video.height"),
            "frame_rate": lair.config.get("comfy.hunyuan_video.frame_rate"),
            "guidance_scale": lair.config.get("comfy.hunyuan_video.guidance_scale"),
            "loras": loras,
            "model_name": lair.config.get("comfy.hunyuan_video.model_name"),
            "model_weight_dtype": lair.config.get("comfy.hunyuan_video.model_weight_dtype"),
            "num_frames": lair.config.get("comfy.hunyuan_video.num_frames"),
            "prompt": lair.config.get("comfy.hunyuan_video.prompt"),
            "sampler": lair.config.get("comfy.hunyuan_video.sampler"),
            "sampling_shift": lair.config.get("comfy.hunyuan_video.sampling_shift"),
            "scheduler": lair.config.get("comfy.hunyuan_video.scheduler"),
            "seed": lair.config.get("comfy.hunyuan_video.seed"),
            "steps": lair.config.get("comfy.hunyuan_video.steps"),
            "tiled_decode_enabled": lair.config.get("comfy.hunyuan_video.tiled_decode.enabled"),
            "tile_overlap": lair.config.get("comfy.hunyuan_video.tiled_decode.overlap"),
            "tile_size": lair.config.get("comfy.hunyuan_video.tiled_decode.tile_size"),
            "tile_temporal_overlap": lair.config.get("comfy.hunyuan_video.tiled_decode.temporal_overlap"),
            "tile_temporal_size": lair.config.get("comfy.hunyuan_video.tiled_decode.temporal_size"),
            "vae_model_name": lair.config.get("comfy.hunyuan_video.vae_model_name"),
            "width": lair.config.get("comfy.hunyuan_video.width"),
        }

    async def _workflow_hunyuan_video_t2v(
        self,
        *,
        batch_size: int,
        clip_name_1: str,
        clip_name_2: str,
        denoise: float,
        frame_rate: int,
        guidance_scale: float,
        height: int,
        loras: list[str] | None,
        model_name: str,
        num_frames: int,
        model_weight_dtype: str,
        prompt: str,
        sampler: str,
        sampling_shift: float,
        scheduler: str,
        seed: int | None,
        steps: int,
        tile_overlap: int,
        tile_size: int,
        tile_temporal_size: int,
        tile_temporal_overlap: int,
        tiled_decode_enabled: bool,
        width: int,
        vae_model_name: str,
    ) -> list[bytes]:
        """Generate a hunyuan video from text."""
        seed = self._ensure_seed(seed)

        noise = RandomNoise(seed)
        model = UNETLoader(model_name, model_weight_dtype)
        clip = DualCLIPLoader(clip_name_1, clip_name_2, "hunyuan_video", None)

        model, clip = self._apply_loras(model, clip, loras)

        conditioning = CLIPTextEncode(prompt, clip)
        conditioning = FluxGuidance(conditioning, guidance_scale)

        model_shifted = ModelSamplingSD3(model, sampling_shift)
        guider = BasicGuider(model_shifted, conditioning)
        sampler = KSamplerSelect("euler_ancestral")
        sigmas = BasicScheduler(model, "simple", steps, denoise)
        latent = EmptyHunyuanLatentVideo(width, height, num_frames, batch_size)
        latent, _ = SamplerCustomAdvanced(noise, guider, sampler, sigmas, latent)

        vae = VAELoader(vae_model_name)

        if tiled_decode_enabled:
            image = VAEDecodeTiled(latent, vae, tile_size, tile_overlap, tile_temporal_overlap, tile_temporal_size)
        else:
            image = VAEDecode(latent, vae)

        save_node = SaveAnimatedWEBP(image, "ComfyUI", frame_rate, False, 80, "default")

        videos = []
        for video in save_node.wait()._output["images"]:
            videos.append(self.view(video["filename"], type="output"))

        return videos

    def _get_defaults_outpaint(self) -> dict[str, Any]:
        """Return default parameters for the ``outpaint`` workflow."""
        loras_val = lair.config.get("comfy.outpaint.loras")
        loras = [lora for lora in str(loras_val).split("\n") if lora] if loras_val is not None else None

        return {
            "cfg": lair.config.get("comfy.outpaint.cfg"),
            "denoise": lair.config.get("comfy.outpaint.denoise"),
            "feathering": lair.config.get("comfy.outpaint.feathering"),
            "grow_mask_by": lair.config.get("comfy.outpaint.grow_mask_by"),
            "loras": loras,
            "model_name": lair.config.get("comfy.outpaint.model_name"),
            "negative_prompt": lair.config.get("comfy.outpaint.negative_prompt"),
            "padding_bottom": lair.config.get("comfy.outpaint.padding_bottom"),
            "padding_left": lair.config.get("comfy.outpaint.padding_left"),
            "padding_right": lair.config.get("comfy.outpaint.padding_right"),
            "padding_top": lair.config.get("comfy.outpaint.padding_top"),
            "prompt": lair.config.get("comfy.outpaint.prompt"),
            "sampler": lair.config.get("comfy.outpaint.sampler"),
            "scheduler": lair.config.get("comfy.outpaint.scheduler"),
            "seed": lair.config.get("comfy.outpaint.seed"),
            "source_image": None,
            "steps": lair.config.get("comfy.outpaint.steps"),
        }

    async def _workflow_outpaint(
        self,
        *,
        model_name: str,
        prompt: str,
        loras: list[str] | None,
        negative_prompt: str,
        grow_mask_by: int,
        seed: int | None,
        source_image: str,
        steps: int,
        cfg: float,
        sampler: str,
        scheduler: str,
        denoise: float,
        padding_left: int,
        padding_top: int,
        padding_right: int,
        padding_bottom: int,
        feathering: int,
    ) -> list[str]:
        """Outpaint an image using the given prompt."""
        seed = self._ensure_seed(seed)

        async with Workflow():
            model, clip, vae = CheckpointLoaderSimple(model_name)

            model, clip = self._apply_loras(model, clip, loras)

            positive_conditioning = CLIPTextEncode(prompt, clip)
            negative_conditioning = CLIPTextEncode(negative_prompt, clip)

            source_image, _ = ETNLoadImageBase64(self._image_to_base64(source_image))
            source_image, mask = ImagePadForOutpaint(
                source_image, padding_left, padding_top, padding_right, padding_bottom, feathering
            )
            save_image_node = SaveImage(source_image, self.output_prefix)

            latent = VAEEncodeForInpaint(source_image, vae, mask, grow_mask_by)
            latent = KSampler(
                model,
                seed,
                steps,
                cfg,
                sampler,
                scheduler,
                positive_conditioning,
                negative_conditioning,
                latent,
                denoise,
            )

            image = VAEDecode(latent, vae)
            save_image_node = SaveImage(image, self.output_prefix)

            images = await save_image_node.wait()

        return images

    def _get_defaults_upscale(self) -> dict[str, Any]:
        """Return default parameters for the ``upscale`` workflow."""
        return {
            "source_image": None,
            "model_name": lair.config.get("comfy.upscale.model_name"),
        }

    async def _workflow_upscale(self, *, source_image: str, model_name: str) -> list[str]:
        """Upscale a provided image."""
        upscale_model = UpscaleModelLoader(model_name)
        image, _ = ETNLoadImageBase64(self._image_to_base64(source_image))
        image = ImageUpscaleWithModel(upscale_model, image)
        save_image_node = SaveImage(image, self.output_prefix)
        images = await save_image_node.wait()

        return images
