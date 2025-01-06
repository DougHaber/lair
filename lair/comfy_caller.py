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

import asyncio
import contextlib
import importlib
import io


# This never executes, but it helps trick code editors into accepting the symbols.
# Without this, all the symbols would be highlighted as being unknown.
if False:
    from comfy_script.runtime.nodes import *


class ComfyCaller():
    def __init__(self, url, output_prefix='ComfyUI'):
        self.url = url
        self.output_prefix = output_prefix

        self.workflows = {}

        self._import_comfy_script()
        self._init_workflows()

    def _import_comfy_script(self):
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

    def _init_workflows(self):
        self.workflows = {
            'generate_image': self.workflow_generate_image
        }

    def run_workflow(self, workflow, *args, **kwargs):
        '''Run a workflow, blocking into it completes and returning its output'''
        workflow_handler = self.workflows.get(workflow)

        if not workflow_handler:
            raise ValueError("Undefined workflow: %s" % workflow)

        # Use contextlib to try to prevent the noise output of comfy_script.
        # Unfortunately, its threads print output even after the workflow completes, so some output will still leak.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return asyncio.run(workflow_handler(*args, **kwargs))

    async def workflow_generate_image(self, *, model_name, prompt,
                                      negative_prompt='',
                                      output_width=512, output_height=512, batch_size=1,
                                      seed=None, steps=20, cfg=8, sampler='euler', scheduler='normal', denoise=1.0):
        async with Workflow():
            model, clip, vae = CheckpointLoaderSimple(model_name)
            positive_conditioning = CLIPTextEncode(prompt, clip)
            negative_conditioning = CLIPTextEncode(negative_prompt, clip)
            latent = EmptyLatentImage(output_width, output_height, batch_size)

            latent = KSampler(model, seed, steps, cfg, sampler, scheduler,
                              positive_conditioning, negative_conditioning, latent, denoise)
            image = VAEDecode(latent, vae)
            save_image_node = SaveImage(image, self.output_prefix)

            images = await save_image_node.wait()

        return images
