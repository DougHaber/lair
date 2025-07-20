"""Command line interface for running ComfyUI workflows."""

import argparse
import os
import pathlib
import shlex
import sys
from collections.abc import Iterable, Sequence
from typing import Any, cast

import PIL

import lair
import lair.cli
import lair.comfy_caller
from lair.cli.chat_interface import ChatInterface
from lair.logging import logger  # noqa
from lair.util.argparse import (
    ArgumentParserExitException,
    ArgumentParserHelpException,
    ErrorRaisingArgumentParser,
)


def _module_info() -> dict[str, Any]:
    """Return metadata describing this module."""
    return {
        "description": "Run ComfyUI workflows",
        "class": Comfy,
        "tags": [],
        "aliases": [],
    }


class Comfy:
    """Entry point for the ``comfy`` command."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        """Initialize the argument parser for all ComfyUI workflows."""
        sub_parser = parser.add_subparsers(dest="comfy_command", required=True)

        self.comfy = lair.comfy_caller.ComfyCaller()
        self._image_file_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

        self._add_argparse_hunyuan_video_t2v(sub_parser)
        self._add_argparse_image(sub_parser)
        self._add_argparse_ltxv_i2v(sub_parser)
        self._add_argparse_ltxv_prompt(sub_parser)
        self._add_argparse_outpaint(sub_parser)
        self._add_argparse_upscale(sub_parser)

        lair.events.subscribe("chat.init", lambda d: self._on_chat_init(cast(ChatInterface, d)), instance=self)

    def _add_argparse_image(self, sub_parser: argparse._SubParsersAction) -> None:
        command_parser = sub_parser.add_parser("image", help="Basic image creation workflow")
        defaults = self.comfy.defaults["image"]
        output_file = lair.config.get("comfy.image.output_file")
        comfy_url = lair.config.get("comfy.url")

        command_parser.add_argument("-b", "--batch-size", type=int, help="Batch size (default: 1)")
        command_parser.add_argument(
            "-c", "--cfg", type=float, help=f"Classifier-free guidance scale (default: {defaults['cfg']})"
        )
        command_parser.add_argument(
            "-H", "--output-height", type=int, help=f"Output file height (default: {defaults['output_height']})"
        )
        command_parser.add_argument(
            "-l",
            "--lora",
            nargs="*",
            type=str,
            dest="loras",
            help=(
                "Loras to use. Can be specified multiple times. These are processed in order. "
                "Command line usage overrides LoRAs in the settings. "
                "(format either: {name}, {name}:{weight}, or {name}:{weight}:{clip_weight})"
            ),
        )
        command_parser.add_argument(
            "-m",
            "--model-name",
            type=str,
            help=f"Name of the image diffusion model (default: {defaults['model_name']})",
        )
        command_parser.add_argument(
            "-n", "--negative-prompt", type=str, help="Negative prompt to use for image diffusion"
        )
        command_parser.add_argument(
            "-N", "--steps", type=int, help=f"Number of sampling steps (default: {defaults['steps']})"
        )
        command_parser.add_argument(
            "-o",
            "--output-file",
            default=output_file,
            type=str,
            help=(
                f"File to write output to. When generating multiple images, "
                f"the basename becomes a prefix. (default: {output_file})"
            ),
        )
        command_parser.add_argument("-p", "--prompt", type=str, help="Prompt to use for image diffusion.")
        command_parser.add_argument("-P", "--prompt-file", type=str, help="File name to read a prompt from.")
        command_parser.add_argument(
            "-r",
            "--repeat",
            default=1,
            type=int,
            help=(
                "Number of times to repeat. Total images generated is number of repeats times batch size. (default: 1)"
            ),
        )
        command_parser.add_argument(
            "-s", "--sampler", type=str, help=f"Sampler to use for image diffusion (default: {defaults['sampler']})"
        )
        command_parser.add_argument(
            "-S",
            "--scheduler",
            type=str,
            help=f"Scheduler to use for image diffusion (default: {defaults['scheduler']})",
        )
        command_parser.add_argument(
            "-u", "--comfy-url", default=comfy_url, help=f"URL for the Comfy UI API (default: {comfy_url})"
        )
        command_parser.add_argument(
            "-w", "--output-width", type=int, help=f"Output file width (default: {defaults['output_width']})"
        )
        command_parser.add_argument(
            "-x",
            "--seed",
            type=int,
            help=(
                "The seed to use when sampling (default: "
                f"{defaults['seed'] if defaults['seed'] is not None else 'random'})"
            ),
        )

    def _add_argparse_hunyuan_video_t2v(self, sub_parser: argparse._SubParsersAction) -> None:
        command_parser = sub_parser.add_parser("hunyuan-video-t2v", help="Hunyuan Video - Text to Video")
        defaults = self.comfy.defaults["hunyuan-video-t2v"]
        output_file = lair.config.get("comfy.hunyuan_video.output_file")
        comfy_url = lair.config.get("comfy.url")

        command_parser.add_argument("-b", "--batch-size", type=int, help="Batch size (default: 1)")
        command_parser.add_argument(
            "-c", "--clip-name-1", type=str, help=f"Name of the first clip model (default: {defaults['clip_name_1']})"
        )
        command_parser.add_argument(
            "-C", "--clip-name-2", type=str, help=f"Name of the second clip model (default: {defaults['clip_name_2']})"
        )
        command_parser.add_argument(
            "-f", "--frame-rate", type=int, help=f"Batch size (default: {defaults['frame_rate']})"
        )
        command_parser.add_argument(
            "-F",
            "--num-frames",
            type=int,
            help=f"Number of frames to generate (default: {defaults['num_frames']}, must be N * 4 + 1)",
        )
        command_parser.add_argument(
            "-g", "--guidance_scale", type=float, help=f"Guidance scale (default: {defaults['guidance_scale']})"
        )
        command_parser.add_argument(
            "-H", "--output-height", type=int, dest="height", help=f"Output file height (default: {defaults['height']})"
        )
        command_parser.add_argument(
            "-l",
            "--lora",
            nargs="*",
            type=str,
            dest="loras",
            help=(
                "Loras to use. Can be specified multiple times. These are processed in order. "
                "Command line usage overrides LoRAs in the settings. "
                "(format either: {name}, {name}:{weight}, or {name}:{weight}:{clip_weight})"
            ),
        )
        command_parser.add_argument(
            "-m",
            "--model-name",
            type=str,
            help=f"Name of the image diffusion model (default: {defaults['model_name']})",
        )
        command_parser.add_argument(
            "-M",
            "--model-weight-dtype",
            type=str,
            help=f"Dtype to use for the model (default: {defaults['model_weight_dtype']})",
        )
        command_parser.add_argument(
            "-o",
            "--output-file",
            default=output_file,
            type=str,
            help=(
                f"File to write output to. When generating multiple images, "
                f"the basename becomes a prefix. (default: {output_file})"
            ),
        )
        command_parser.add_argument(
            "-p", "--prompt", type=str, help="Prompt to use. (auto-prompt is disabled when this is provided)"
        )
        command_parser.add_argument(
            "-P",
            "--prompt-file",
            type=str,
            help="File name to read a prompt from.  (auto-prompt is disabled when this is provided)",
        )
        command_parser.add_argument(
            "-r",
            "--repeat",
            default=1,
            type=int,
            help=(
                "Number of times to repeat. Total images generated is number of repeats times batch size. (default: 1)"
            ),
        )
        command_parser.add_argument(
            "-s", "--sampler", type=str, help=f"Sampler to use for image diffusion (default: {defaults['sampler']})"
        )
        command_parser.add_argument(
            "-S",
            "--scheduler",
            type=str,
            help=f"Scheduler to use for image diffusion (default: {defaults['scheduler']})",
        )
        command_parser.add_argument(
            "-u", "--comfy-url", default=comfy_url, help=f"URL for the Comfy UI API (default: {comfy_url})"
        )
        command_parser.add_argument(
            "-w", "--output-width", type=int, dest="width", help=f"Output file width (default: {defaults['width']})"
        )
        command_parser.add_argument(
            "-x",
            "--seed",
            type=int,
            help=(
                "The seed to use when sampling (default: "
                f"{defaults['seed'] if defaults['seed'] is not None else 'random'})"
            ),
        )

    def _add_argparse_ltxv_i2v(self, sub_parser: argparse._SubParsersAction) -> None:
        command_parser = sub_parser.add_parser("ltxv-i2v", help="LTX Video - Image to Video")
        defaults = self.comfy.defaults["ltxv-i2v"]
        output_file = lair.config.get("comfy.ltxv_i2v.output_file")
        comfy_url = lair.config.get("comfy.url")

        command_parser.add_argument(
            "-a",
            "--auto-prompt-extra",
            type=str,
            help=(
                "Content to add after the generated prompt (When --prompt or "
                "--prompt-file is provided, this is ignored)"
            ),
        )
        command_parser.add_argument(
            "-A",
            "--auto-prompt-suffix",
            type=str,
            help=(
                "Content to add to the end of the generated prompt (When --prompt "
                "or --prompt-file is provided, this is ignored)"
            ),
        )
        command_parser.add_argument("-b", "--batch-size", type=int, help="Batch size (default: 1)")
        command_parser.add_argument(
            "-c", "--cfg", type=float, help=f"Classifier-free guidance scale (default: {defaults['cfg']})"
        )
        command_parser.add_argument(
            "-C", "--clip-name", type=str, help=f"Name of the clip model (default: {defaults['clip_name']})"
        )
        command_parser.add_argument(
            "-f",
            "--frame-rate-saving",
            type=int,
            help=f"Frame rate for saving -- different than conditioning (default: {defaults['frame_rate_save']})",
        )
        command_parser.add_argument(
            "-F",
            "--num-frames",
            type=int,
            help=f"Number of frames to generate (default: {defaults['num_frames']}, must be N * 8 + 1)",
        )
        command_parser.add_argument("-i", "--image", type=str, required=True, help="Input image file to use (required)")
        command_parser.add_argument(
            "-m",
            "--model-name",
            type=str,
            help=f"Name of the image diffusion model (default: {defaults['model_name']})",
        )
        command_parser.add_argument(
            "-n", "--negative-prompt", type=str, help="Negative prompt to use for image diffusion"
        )
        command_parser.add_argument(
            "-N", "--steps", type=int, help=f"Number of sampling steps (default: {defaults['steps']})"
        )
        command_parser.add_argument(
            "-o",
            "--output-file",
            default=output_file,
            type=str,
            help=(
                f"File to write output to. When generating multiple images, "
                f"the basename becomes a prefix. (default: {output_file})"
            ),
        )
        command_parser.add_argument(
            "-O", "--output-format", type=str, help=f"Output format to use (default: {defaults['output_format']}"
        )
        command_parser.add_argument(
            "-p", "--prompt", type=str, help="Prompt to use. (auto-prompt is disabled when this is provided)"
        )
        command_parser.add_argument(
            "-P",
            "--prompt-file",
            type=str,
            help="File name to read a prompt from.  (auto-prompt is disabled when this is provided)",
        )
        command_parser.add_argument(
            "-r",
            "--repeat",
            default=1,
            type=int,
            help=(
                "Number of times to repeat. Total images generated is number of repeats times batch size. (default: 1)"
            ),
        )
        command_parser.add_argument(
            "-R",
            "--frame-rate-conditioning",
            type=int,
            help=(
                f"Frame rate for conditioning -- different than saving (default: {defaults['frame_rate_conditioning']})"
            ),
        )
        command_parser.add_argument(
            "-s", "--sampler", type=str, help=f"Sampler to use for image diffusion (default: {defaults['sampler']})"
        )
        command_parser.add_argument(
            "-S",
            "--scheduler",
            type=str,
            help=f"Scheduler to use for image diffusion (default: {defaults['scheduler']})",
        )
        command_parser.add_argument(
            "-u", "--comfy-url", default=comfy_url, help=f"URL for the Comfy UI API (default: {comfy_url})"
        )
        command_parser.add_argument(
            "-x",
            "--seed",
            type=int,
            help=(
                "The seed to use when sampling (default: "
                f"{defaults['seed'] if defaults['seed'] is not None else 'random'})"
            ),
        )

    def _add_argparse_ltxv_prompt(self, sub_parser: argparse._SubParsersAction) -> None:
        command_parser = sub_parser.add_parser("ltxv-prompt", help="LTX Video - Generate prompts from an image")
        defaults = self.comfy.defaults["ltxv-prompt"]
        output_file = lair.config.get("comfy.ltxv_prompt.output_file")
        comfy_url = lair.config.get("comfy.url")

        command_parser.add_argument(
            "-a", "--auto-prompt-extra", type=str, help="Content to add after the generated prompt"
        )
        command_parser.add_argument(
            "-A", "--auto-prompt-suffix", type=str, help="Content to add to the end of the generated prompt"
        )
        command_parser.add_argument("-i", "--image", type=str, required=True, help="Input image file to use (required)")
        command_parser.add_argument(
            "-o",
            "--output-file",
            default=output_file,
            type=str,
            help=(
                f"File to write output to. When generating multiple images, "
                f"the basename becomes a prefix. (default: {output_file})"
            ),
        )
        command_parser.add_argument(
            "-r", "--repeat", default=1, type=int, help="Number of times to repeat. (default: 1)"
        )
        command_parser.add_argument(
            "-u", "--comfy-url", default=comfy_url, help=f"URL for the Comfy UI API (default: {comfy_url})"
        )
        command_parser.add_argument(
            "-x",
            "--seed",
            type=int,
            dest="florence_seed",
            help=(
                "The seed to use with the Florence model (default: "
                f"{defaults['florence_seed'] if defaults['florence_seed'] is not None else 'random'})"
            ),
        )

    def _add_argparse_outpaint(self, sub_parser: argparse._SubParsersAction) -> None:
        command_parser = sub_parser.add_parser("outpaint", help="Outpaint images")
        defaults = self.comfy.defaults["outpaint"]
        comfy_url = lair.config.get("comfy.url")
        padding_default = (
            f"{defaults['padding_top']}x{defaults['padding_right']}x"
            f"{defaults['padding_bottom']}x{defaults['padding_left']}"
        )

        command_parser.add_argument(
            "-c", "--cfg", type=float, help=f"Classifier-free guidance scale (default: {defaults['cfg']})"
        )
        command_parser.add_argument(
            "-d", "--denoise", type=float, help=f"Denoise level (default: {defaults['denoise']})"
        )
        command_parser.add_argument(
            "-f", "--feathering", type=float, help=f"Feathering pixels (default: {defaults['feathering']})"
        )
        command_parser.add_argument(
            "-g",
            "--grow-mask_by",
            type=float,
            help=f"How many pixels to use for the grow_mask_by setting (default: {defaults['grow_mask_by']})",
        )
        command_parser.add_argument(
            "-l",
            "--lora",
            nargs="*",
            type=str,
            dest="loras",
            help=(
                "Loras to use. Can be specified multiple times. These are processed in order. "
                "Command line usage overrides LoRAs in the settings. "
                "(format either: {name}, {name}:{weight}, or {name}:{weight}:{clip_weight})"
            ),
        )
        command_parser.add_argument(
            "-m",
            "--model-name",
            type=str,
            help=f"Name of the image diffusion model (default: {defaults['model_name']})",
        )
        command_parser.add_argument(
            "-n", "--negative-prompt", type=str, help="Negative prompt to use for image diffusion"
        )
        command_parser.add_argument(
            "-N", "--steps", type=int, help=f"Number of sampling steps (default: {defaults['steps']})"
        )
        command_parser.add_argument("-p", "--prompt", type=str, help="Prompt to use for image diffusion.")
        command_parser.add_argument("-P", "--prompt-file", type=str, help="File name to read a prompt from.")
        command_parser.add_argument(
            "-r", "--recursive", action="store_true", help="Recursively process all files in provided paths"
        )
        command_parser.add_argument(
            "-R",
            "--padding",
            type=str,
            help=f"Provide top/right/bottom/left padding (format: TxRxBxL, default: {padding_default})",
        )
        command_parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Do not perform upscaling for files that already have an output file",
        )
        command_parser.add_argument(
            "-s", "--sampler", type=str, help=f"Sampler to use for image diffusion (default: {defaults['sampler']})"
        )
        command_parser.add_argument(
            "-S",
            "--scheduler",
            type=str,
            help=f"Scheduler to use for image diffusion (default: {defaults['scheduler']})",
        )
        command_parser.add_argument(
            "-u", "--comfy-url", default=comfy_url, help=f"URL for the Comfy UI API (default: {comfy_url})"
        )
        command_parser.add_argument(
            "-x",
            "--seed",
            type=int,
            help=(
                "The seed to use when sampling (default: "
                f"{defaults['seed'] if defaults['seed'] is not None else 'random'})"
            ),
        )
        command_parser.add_argument("outpaint_files", type=str, nargs="+", help="File(s) to outpaint")

    def _add_argparse_upscale(self, sub_parser: argparse._SubParsersAction) -> None:
        command_parser = sub_parser.add_parser("upscale", help="Upscale images")
        defaults = self.comfy.defaults["upscale"]
        comfy_url = lair.config.get("comfy.url")

        command_parser.add_argument(
            "-m", "--model-name", type=str, help=f"Upscale model  (default: {defaults['model_name']})"
        )
        command_parser.add_argument(
            "-r", "--recursive", action="store_true", help="Recursively process all files in provided paths"
        )
        command_parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Do not perform upscaling for files that already have an output file",
        )
        command_parser.add_argument(
            "-u", "--comfy-url", default=comfy_url, help=f"URL for the Comfy UI API (default: {comfy_url})"
        )
        command_parser.add_argument("scale_files", type=str, nargs="+", help="File(s) to scale")

    def _get_chat_command_parser(self) -> argparse.ArgumentParser:
        """Return an ``ArgumentParser`` for the ``/comfy`` chat command."""
        new_parser = ErrorRaisingArgumentParser(prog="/comfy")
        sub_parser = new_parser.add_subparsers(dest="comfy_command", required=True)

        self._add_argparse_hunyuan_video_t2v(sub_parser)
        self._add_argparse_image(sub_parser)
        self._add_argparse_ltxv_i2v(sub_parser)
        self._add_argparse_ltxv_prompt(sub_parser)
        self._add_argparse_upscale(sub_parser)

        return new_parser

    def _on_chat_init(self, chat_interface: "ChatInterface") -> None:
        """Register the ``/comfy`` command with the chat interface."""

        def comfy_command(command: str, arguments: Iterable[str], arguments_str: str) -> None:
            """Execute a ComfyUI workflow from the chat interface."""
            try:
                chat_command_parser = self._get_chat_command_parser()
                new_arguments = shlex.split(" ".join(arguments))
                try:
                    params = chat_command_parser.parse_args(new_arguments)
                    params.comfy_url = lair.config.get("comfy.url")
                except ArgumentParserHelpException as error:  # Display help with styles
                    chat_interface.reporting.error(str(error), show_exception=False)
                    return
                except ArgumentParserExitException:  # Ignore exits
                    return
            except argparse.ArgumentError as error:
                message = str(error)
                if message == "the following arguments are required: comfy_command":
                    # If /comfy --help is run, display the full help with styles
                    chat_interface.reporting.error(chat_command_parser.format_help(), show_exception=False)
                    return
                logger.error(message)
                return

            self.run(params)

        chat_interface.register_command("/comfy", comfy_command, "Call ComfyUI workflows")

    def _save_output__save_to_disk(self, item: object, filename: str) -> None:
        """Save a workflow output to disk.

        Args:
            item: The object to save. ``PIL.Image.Image`` and file-like objects are supported.
            filename: Path on disk where the item should be saved.

        Raises:
            TypeError: If ``item`` is not a supported type.

        """
        if isinstance(item, PIL.Image.Image):
            item.save(filename)
        elif isinstance(item, bytes):
            with open(filename, "wb") as file:
                file.write(item)
        elif hasattr(item, "read"):  # File like objects
            with open(filename, "wb") as file:
                while chunk := item.read(8192):  # Read and write in chunks
                    file.write(chunk)
        else:
            raise TypeError("Unsupported output type. Unable to save output file.")

    def _save_output(
        self,
        results: Sequence[object],
        filename: str,
        start_index: int = 0,
        single_output: bool = False,
    ) -> None:
        """Save workflow outputs to disk.

        Args:
            results: Items returned from the workflow.
            filename: Base filename for saving outputs.
            start_index: Index offset when naming multiple outputs.
            single_output: Whether ``results`` contains exactly one item.

        """
        output_files = []

        if single_output:  # Save single output with provided filename
            if filename == "-":
                sys.stdout.buffer.write(cast(bytes, results[0]) + b"\n")
                return

            self._save_output__save_to_disk(results[0], filename)
            output_files.append(filename)
        else:
            if filename == "-":
                raise Exception("Writing to STDOUT is only supported for single-file output")
            elif not os.path.splitext(filename)[1]:
                raise ValueError("Filename must have an extension (e.g., 'output.png').")

            basename, extension = os.path.splitext(filename)

            # Save multiple outputs with incrementing filenames
            for i, output in enumerate(results, start=start_index):
                padded_index = f"{i:06d}"  # Zero-padded to 6 digits
                output_filename = f"{basename}{padded_index}{extension}"
                self._save_output__save_to_disk(output, output_filename)
                output_files.append(output_filename)

        logger.debug(f"saved: {', '.join(output_files)}")

    def get_output_file_name(self, file_name: str) -> str:
        """Return the filename that should be used for an upscaled image."""
        return f"{os.path.splitext(file_name)[0]}-upscaled{os.path.splitext(file_name)[1]}"

    def _run_workflow_queue(
        self,
        arguments: argparse.Namespace,
        defaults: dict[str, Any],
        function_arguments: dict[str, Any],
        *,
        queue: list[str],
        output_filename_template: str,
    ) -> None:
        """Process each file in ``queue`` using the provided workflow."""
        while queue:
            source_filename = queue.pop(0)
            if os.path.isdir(source_filename):
                if arguments.recursive:
                    self._extend_queue_from_dir(source_filename, queue)
                else:
                    logger.warning(f"Path ignored: Use --recursive to process directories: {source_filename}")
            else:
                self._process_file(source_filename, arguments, function_arguments, output_filename_template)

    def _extend_queue_from_dir(self, directory: str, queue: list[str]) -> None:
        """Add image files from ``directory`` to ``queue``."""
        for filename in os.listdir(directory):
            path = pathlib.Path(directory) / filename
            if path.is_dir() or path.suffix.lower() in self._image_file_extensions:
                queue.append(str(path.absolute()))

    def _process_file(
        self,
        filename: str,
        arguments: argparse.Namespace,
        function_arguments: dict[str, Any],
        template: str,
    ) -> None:
        """Run a workflow for a single file and save the result."""
        function_arguments["source_image"] = filename
        output_filename = template.format(basename=os.path.splitext(filename)[0])

        if os.path.exists(output_filename) and arguments.skip_existing:
            logger.warning(f"Skipping existing file: {output_filename}")
            return

        output = cast(
            Sequence[object],
            self.comfy.run_workflow(arguments.comfy_command, **function_arguments),
        )
        if not output:
            raise ValueError("Workflow returned no output. This could indicate an invalid parameter was provided.")
        self._save_output(output, output_filename, single_output=True)

    def run_workflow_outpaint(
        self,
        arguments: argparse.Namespace,
        defaults: dict[str, Any],
        function_arguments: dict[str, Any],
    ) -> None:
        """Run the outpaint workflow for each file in ``arguments.outpaint_files``."""
        if arguments.padding:
            components = arguments.padding.split("x")
            if len(components) != 4:
                raise ValueError("Padding must have 4 components (top/right/bottom/left)")

            for value in components:
                int_value = lair.util.safe_int(value)
                if not isinstance(int_value, int):
                    raise ValueError("Padding components must be integers")

            function_arguments["padding_top"] = lair.util.safe_int(components[0])
            function_arguments["padding_right"] = lair.util.safe_int(components[1])
            function_arguments["padding_bottom"] = lair.util.safe_int(components[2])
            function_arguments["padding_left"] = lair.util.safe_int(components[3])

        self._run_workflow_queue(
            arguments,
            defaults,
            function_arguments,
            queue=[*arguments.outpaint_files],
            output_filename_template=cast(str, lair.config.get("comfy.outpaint.output_filename")),
        )

    def run_workflow_upscale(
        self,
        arguments: argparse.Namespace,
        defaults: dict[str, Any],
        function_arguments: dict[str, Any],
    ) -> None:
        """Run the upscale workflow for each file in ``arguments.scale_files``."""
        self._run_workflow_queue(
            arguments,
            defaults,
            function_arguments,
            queue=[*arguments.scale_files],
            output_filename_template=cast(str, lair.config.get("comfy.upscale.output_filename")),
        )

    def run_workflow_default(
        self,
        arguments: argparse.Namespace,
        defaults: dict[str, Any],
        function_arguments: dict[str, Any],
    ) -> None:
        """Run a workflow and save outputs, respecting ``arguments.repeat``."""
        # True when there is only a single file output
        batch_size = function_arguments.get("batch_size", defaults.get("batch_size", 1))
        single_output = arguments.repeat == 1 and batch_size == 1

        for i in range(0, arguments.repeat):
            output = cast(
                Sequence[object],
                self.comfy.run_workflow(arguments.comfy_command, **function_arguments),
            )

            if output is None or len(output) == 0:
                raise ValueError("Workflow returned no output. This could indicate an invalid parameter was provided.")
            self._save_output(output, arguments.output_file, i * len(output), single_output=single_output)

    def run(self, arguments: argparse.Namespace) -> None:
        """Execute a workflow based on parsed command-line ``arguments``."""
        self.comfy.set_url(arguments.comfy_url)

        arguments_dict = vars(arguments)
        # If a prompt-file is provided, set the prompt attribute from that
        if arguments_dict.get("prompt_file") is not None:
            arguments_dict["prompt"] = lair.util.slurp_file(cast(str, arguments_dict.get("prompt_file")))
            del arguments_dict["prompt_file"]
        defaults = self.comfy.defaults[arguments.comfy_command]
        function_arguments = {
            key: value for key, value in arguments_dict.items() if key in defaults and arguments_dict[key] is not None
        }

        if arguments.comfy_command == "upscale":
            self.run_workflow_upscale(arguments, defaults, function_arguments)
        elif arguments.comfy_command == "outpaint":
            self.run_workflow_outpaint(arguments, defaults, function_arguments)
        else:
            self.run_workflow_default(arguments, defaults, function_arguments)
