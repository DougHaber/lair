# This module provides support for running parameterized workflows via ComfyUI and collecting the output. An earlier
# version used modules like diffusers, torch, and scipy to do similar things on its own. This made the code much more
# complicated and slower to install and run. By allowing an external ComfyUI Server to do the work, we gain access to
# all of their hard work on implementing and optimizing the diffusion process and support for all the variants of
# models. As the server persists between runs, this also removes the need to reload models onto the GPU each new run,
# and so greatly improves cycle time.
#
# The ComfyScript library used here works really well, but it doesn't always behave nicely. It creates threads to do
# actual work, but it isn't clear how to shut them down properly when complete, so calling this will result in extra
# threads that keep running. It also uses print() instead of a proper logger for debugging, and so it can be very
# noisy. Some non-ideal protections are taken to block output, but even those don't work perfectly since the threads may
# occasionally print things even after workflows are no longer running.
#
# Some ComfyScript features require async. To keep things simple, all workflow functions are written with async whether
# they use it or not.

import asyncio
import base64
import contextlib
import importlib
import io
import random

import requests

import lair
from lair.logging import logger  # noqa


# This never executes, but it helps trick code editors into accepting the symbols.
# Without this, all the symbols would be highlighted as being unknown.
if False:
    from comfy_script.runtime.nodes import *


class ComfyCaller():
    def __init__(self, url=None, output_prefix='ComfyUI'):
        self.url = url
        self.output_prefix = output_prefix

        self.workflows = {}
        self.is_comfy_script_imported = False

        self._init_defaults()
        self._init_workflows()

        # If the mode changes, update all defaults
        lair.events.subscribe('config.change_mode', lambda d: self._init_defaults())

    def set_url(self, url):
        if self.url is not None:
            raise Exception("ComfyCaller(): Modifying a Comfy URL is not supported.")
        else:
            self.url = url
            self._import_comfy_script()

    def _import_comfy_script(self):
        # The imports actually connect to the server. If the defaults are being requested, that is problematic
        # since that happens before the server URL is provided. To work around that, importing is deferred
        if self.is_comfy_script_imported is True:
            return

        # ComfyScript behaves poorly with output and writes debugging with print() statements that can not be properly disabled.
        # To deal with this, STDOUT is ignored on import.
        with contextlib.redirect_stdout(io.StringIO()):
            from comfy_script.runtime import load, Workflow
            globals()['load'] = load
            globals()['Workflow'] = Workflow
            load(self.url)

            nodes_module = importlib.import_module("comfy_script.runtime.nodes")
            nodes = {name: getattr(nodes_module, name) for name in dir(nodes_module) if not name.startswith("_")}
            globals().update(nodes)

        self.is_comfy_script_imported = True

    def _init_workflows(self):
        self.workflows = {
            'image': self._workflow_image,
            'ltxv-i2v': self._workflow_ltxv_i2v,
        }

    def _init_defaults(self):
        self.defaults = {
            'image': self._get_defaults_image(),
            'ltxv-i2v': self._get_defaults_ltxv_i2v(),
        }

    def _get_defaults_image(self):
        loras = lair.config.get('comfy.image.loras')
        if loras is not None:
            loras = loras.split('\n')

        return {
            'batch_size': lair.config.get('comfy.image.batch_size', 1),
            'cfg': lair.config.get('comfy.image.cfg', 8.0),
            'denoise': lair.config.get('comfy.image.denoise', 1.0),
            'loras': loras,
            'model_name': lair.config.get('comfy.image.model_name', 'v1-5-pruned-emaonly.safetensors'),
            'negative_prompt': lair.config.get('comfy.image.negative_prompt', ''),
            'output_height': lair.config.get('comfy.image.output_height', 512),
            'output_width': lair.config.get('comfy.image.output_width', 512),
            'prompt': lair.config.get('comfy.image.prompt', ''),
            'sampler': lair.config.get('comfy.image.sampler', 'euler'),
            'scheduler': lair.config.get('comfy.image.scheduler', 'normal'),
            'seed': lair.config.get('comfy.image.seed', None),
            'steps': lair.config.get('comfy.image.steps', 20),
        }

    def view(self, filename, type='temp'):
        response = requests.get(
            f'{self.url}/api/view',
            params={
                'filename': filename,
                'type': type,
            },
            verify=lair.config.get('comfy.verify_ssl', True)
        )

        if response.status_code != 200:
            raise Exception(f'/api/view returned unexpected status code: {response.status_code}')
        else:
            return response.content

    def _parse_lora_argument(self, lora):
        parts = lora.split(':', maxsplit=3)

        lora_model = parts.pop(0)
        weight = 1.0
        clip_weight = 1.0

        # If there are more values, override the defaults for their components
        if parts:
            weight = float(parts.pop(0))
        if parts:
            clip_weight = float(parts.pop(0))

        return lora_model, weight, clip_weight

    def run_workflow(self, workflow, *args, **kwargs):
        handler = self.workflows[workflow]
        kwargs = {**self.defaults[workflow], **kwargs}

        # Use contextlib to try to prevent the noise output of comfy_script.
        # Unfortunately, its threads print output even after the workflow completes, so some output will still leak.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return asyncio.run(handler(*args, **kwargs))

    async def _workflow_image(self, *, model_name, prompt,
                              loras=None, negative_prompt='',
                              output_width=512, output_height=512, batch_size=1,
                              seed=None, steps=20, cfg=8,
                              sampler='euler', scheduler='normal', denoise=1.0):
        if seed is None:
            seed = random.randint(0, 2**31 - 1)

        async with Workflow():
            model, clip, vae = CheckpointLoaderSimple(model_name)

            for lora in loras or []:
                lora_model, weight, clip_weight = self._parse_lora_argument(lora)
                model, clip = LoraLoader(model, clip, lora_model, weight, clip_weight)

            positive_conditioning = CLIPTextEncode(prompt, clip)
            negative_conditioning = CLIPTextEncode(negative_prompt, clip)
            latent = EmptyLatentImage(output_width, output_height, batch_size)

            latent = KSampler(model, seed, steps, cfg, sampler, scheduler,
                              positive_conditioning, negative_conditioning, latent, denoise)
            image = VAEDecode(latent, vae)
            save_image_node = SaveImage(image, self.output_prefix)

            images = await save_image_node.wait()

        return images

    def _get_defaults_ltxv_i2v(self):
        loras = lair.config.get('comfy.ltxv_i2v.loras')
        if loras is not None:
            loras = loras.split('\n')

        return {
            'auto_prompt_extra': lair.config.get('comfy.ltxv_i2v.auto_prompt_extra', ''),
            'auto_prompt_suffix': lair.config.get('comfy.ltxv_i2v.auto_prompt_suffix', ' The scene is captured in real-life footage.'),
            'batch_size': lair.config.get('comfy.ltxv_i2v.batch_size', 1),
            'cfg': lair.config.get('comfy.ltxv_i2v.cfg', 3.0),
            'clip_name': lair.config.get('comfy.ltxv_i2v.clip_name', 't5xxl_fp16.safetensors'),
            'denoise': lair.config.get('comfy.ltxv_i2v.denoise', 1.0),
            'florence_model_name': lair.config.get('comfy.ltxv_i2v.florence_model_name', 'microsoft/Florence-2-base'),
            'frame_rate': lair.config.get('comfy.ltxv_i2v.frame_rate', 25),
            'image': None,
            'image_resize_height': lair.config.get('comfy.ltxv_i2v.image_resize_height', 800),
            'image_resize_width': lair.config.get('comfy.ltxv_i2v.image_resize_width', 800),
            'model_name': lair.config.get('comfy.ltxv_i2v.model_name', 'ltx-video-2b-v0.9.1.safetensors'),
            'negative_prompt': lair.config.get('comfy.ltxv_i2v.negative_prompt',
                                               'worst quality, inconsistent motion, blurry, jittery, distorted, watermarks'),
            'num_frames': lair.config.get('comfy.ltxv_i2v.num_frames', 105),
            'output_format': lair.config.get('comfy.ltxv_i2v.output_format', 'video/h264-mp4'),
            'pingpong': lair.config.get('comfy.ltxv_i2v.pingpong', False),
            'prompt': lair.config.get('comfy.ltxv_i2v.prompt', None),
            'sampler': lair.config.get('comfy.ltxv_i2v.sampler', 'euler_ancestral'),
            'scheduler': lair.config.get('comfy.ltxv_i2v.scheduler', 'normal'),
            'seed': lair.config.get('comfy.ltxv_i2v.seed', None),
            'steps': lair.config.get('comfy.ltxv_i2v.steps', 25),
            'stg': lair.config.get('comfy.ltxv_i2v.stg', 1.0),
            'stg_block_indices': lair.config.get('comfy.ltxv_i2v.stg_block_indices', '14'),
            'stg_rescale': lair.config.get('comfy.ltxv_i2v.stg_rescale', 0.75),
        }

    def image_to_base64(self, image):
        # Convert an image to base64 based on the type
        if isinstance(image, str):  # If the image is a str, then it is a filename
            with open(image, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        else:
            raise ValueError("Conversion of image to base64 not supported for type: %s" % type(image))

    async def _workflow_ltxv_i2v(self, image, *, model_name='ltx-video-2b-v0.9.1.safetensors',
                                 clip_name='t5xxl_fp16.safetensors', stg_block_indices='14', image_resize_height=800,
                                 image_resize_width=800, num_frames=105, frame_rate=25, batch_size=1,
                                 florence_model_name='microsoft/Florence-2-base', negative_prompt='',
                                 auto_prompt_suffix='', auto_prompt_extra='', prompt=None, cfg=3.0, stg=1.0,
                                 stg_rescale=0.75, sampler='euler ancestral', scheduler='normal', steps=25,
                                 pingpong=False, output_format='video/h264-mp4', denoise=1.0, seed=None):
        if image is None:
            raise ValueError("ltxv-i2v: Image must not be None")
        if seed is None:
            seed = random.randint(0, 2**31 - 1)

        with Workflow():
            noise = RandomNoise(seed)
            model, vae = LTXVLoader(model_name, 'bfloat16')
            model = LTXVApplySTG(model, 'attention', stg_block_indices)
            image, _ = ETNLoadImageBase64(self.image_to_base64(image))
            image2, width, height = ImageResizeKJ(image, image_resize_height, image_resize_width, 'bilinear',
                                                  True, 32, 0, 0, None, 'disabled')
            model, latent, sigma_shift = LTXVModelConfigurator(model, vae, 'Custom', width, height, num_frames,
                                                               frame_rate, batch_size, True, 29, image2, None)
            clip = CLIPLoader(clip_name, 'ltxv')
            if prompt is None:  # If a prompt is not provided, automatically generate one
                florence2_model = DownloadAndLoadFlorence2Model(florence_model_name, 'fp16', 'sdpa', None)
                _, _, prompt, _ = Florence2Run(image, florence2_model, '', 'more_detailed_caption', True, False, 256,
                                               3, True, '', 42)  # TODO: Configitize seed
                prompt = StringReplaceMtb(prompt, 'image', 'video')
                prompt = StringReplaceMtb(prompt, 'photo', 'video')
                prompt = StringReplaceMtb(prompt, 'painting', 'video')
                prompt = StringReplaceMtb(prompt, 'illustration', 'video')
                prompt = StringFunctionPysssss('append', 'no', prompt, auto_prompt_extra, auto_prompt_suffix)

            positive_conditioning = CLIPTextEncode(prompt, clip)
            negative_conditioning = CLIPTextEncode(negative_prompt, clip)

            guider = STGGuider(model, positive_conditioning, negative_conditioning, cfg, stg, stg_rescale)
            sampler = KSamplerSelect(sampler)
            sigmas = BasicScheduler(model, scheduler, steps, denoise)
            sigmas = LTXVShiftSigmas(sigmas, sigma_shift, True, 0.1)
            _, latent = SamplerCustomAdvanced(noise, guider, sampler, sigmas, latent)
            image3 = VAEDecode(latent, vae)
            video_node = VHSVideoCombine(images=image3,
                                         # The official workflow set frame_rate to 24 instead of 25.
                                         # For simplicity, I made them the same, but I'm not sure what the reason for that is.
                                         frame_rate=frame_rate,
                                         loop_count=0,
                                         filename_prefix='LTXVideo',
                                         format=output_format,
                                         pingpong=pingpong,
                                         save_output=False,
                                         audio=None,
                                         meta_batch=None,
                                         vae=None,
                                         )

        videos = []
        for video in video_node.wait()._output['gifs']:
            videos.append(self.view(video['filename']))

        return videos
