import os

import PIL

import lair
import lair.cli
import lair.comfy_caller
from lair.logging import logger  # noqa


def _module_info():
    return {
        'description': 'Run ComfyUI workflows',
        'class': Comfy,
        'tags': [],
        'aliases': []
    }


class Comfy():

    def __init__(self, parser):
        sub_parser = parser.add_subparsers(dest='comfy_command', required=True)

        self.comfy = lair.comfy_caller.ComfyCaller()

        self._add_argparse_image(sub_parser)
        self._add_argparse_ltxv_i2v(sub_parser)

    def _add_argparse_image(self, sub_parser):
        command_parser = sub_parser.add_parser('image', help='Basic image creation workflow')
        defaults = self.comfy.defaults['image']
        output_file = lair.config.get('comfy.image.output_file')
        comfy_url = lair.config.get('comfy.url')

        command_parser.add_argument('-b', '--batch-size', type=int,
                                    help='Batch size (default: 1)')
        command_parser.add_argument('-c', '--cfg', type=float,
                                    help=f'Classifier-free guidance scale (default: {defaults["cfg"]})')
        command_parser.add_argument('-H', '--output-height', type=int,
                                    help=f'Output file height (default: {defaults["output_height"]})')
        command_parser.add_argument('-l', '--lora', nargs='*', type=str, dest='loras',
                                    help='Loras to use. Can be specified multiple times. Processed in order. (format either: {name}, {name}:{weight}, or {name}:{weight}:{clip_weight})')
        command_parser.add_argument('-m', '--model-name', type=str,
                                    help=f'Name of the image diffusion model (default: {defaults["model_name"]})')
        command_parser.add_argument('-n', '--negative-prompt', type=str,
                                    help=f'Negative prompt to use for image diffusion (default: {defaults["negative_prompt"]})')
        command_parser.add_argument('-N', '--steps', type=int,
                                    help=f'Number of sampling steps (default: {defaults["steps"]})')
        command_parser.add_argument('-o', '--output-file', default=output_file, type=str,
                                    help=f'File to write output to. When batch size is greater than 1, the basename becomes a prefix. (default: {output_file})')
        command_parser.add_argument('-p', '--prompt', type=str,
                                    help=f'Prompt to use for image diffusion (default: {defaults["prompt"]})')
        command_parser.add_argument('-r', '--repeat', default=1, type=int,
                                    help='Number of times to repeat. Total images generated is number of repeats times batch size. (default: 1)')
        command_parser.add_argument('-s', '--sampler', type=str,
                                    help=f'Sampler to use for image diffusion (default: {defaults["sampler"]})')
        command_parser.add_argument('-S', '--scheduler', type=str,
                                    help=f'Scheduler to use for image diffusion (default: {defaults["scheduler"]})')
        command_parser.add_argument('-u', '--comfy-url', default=comfy_url,
                                    help=f'URL for the Comfy UI API (default: {comfy_url})')
        command_parser.add_argument('-w', '--output-width', type=int,
                                    help=f'Output file width (default: {defaults["output_width"]})')
        command_parser.add_argument('-x', '--seed', type=int,
                                    help=f'The seed to use when sampling (default: {defaults["seed"] if defaults["seed"] is not None else "random"})')

    def _add_argparse_ltxv_i2v(self, sub_parser):
        command_parser = sub_parser.add_parser('ltxv-i2v', help='LTX Video - Image to Video')
        defaults = self.comfy.defaults['ltxv-i2v']
        output_file = lair.config.get('comfy.ltxv_i2v.output_file')
        comfy_url = lair.config.get('comfy.url')

        command_parser.add_argument('-b', '--batch-size', type=int,
                                    help='Batch size (default: 1)')
        command_parser.add_argument('-c', '--cfg', type=float,
                                    help=f'Classifier-free guidance scale (default: {defaults["cfg"]})')
        command_parser.add_argument('-C', '--clip-name', type=str,
                                    help=f'Name of the clip model (default: {defaults["clip_name"]})')
        command_parser.add_argument('-f', '--frame-rate', type=int,
                                    help=f'Batch size (default: {defaults["frame_rate"]})')
        command_parser.add_argument('-F', '--num-frames', type=int,
                                    help=f'Number of frames to generate (default: {defaults["num_frames"]}, must be N * 8 + 1)')
        command_parser.add_argument('-g', '--stg', type=float,
                                    help=f'Spatio-Temporal Guidance scale (default: {defaults["stg"]})')
        command_parser.add_argument('-i', '--image', type=str, required=True,
                                    help='Input image file to use (required)')
        command_parser.add_argument('-m', '--model-name', type=str,
                                    help=f'Name of the image diffusion model (default: {defaults["model_name"]})')
        command_parser.add_argument('-n', '--negative-prompt', type=str,
                                    help=f'Negative prompt to use for image diffusion (default: {defaults["negative_prompt"]})')
        command_parser.add_argument('-N', '--steps', type=int,
                                    help=f'Number of sampling steps (default: {defaults["steps"]})')
        command_parser.add_argument('-o', '--output-file', default=output_file, type=str,
                                    help=f'File to write output to. When batch size is greater than 1, the basename becomes a prefix. (default: {output_file})')
        command_parser.add_argument('-O', '--output-format', type=str,
                                    help=f'Output format to use (default: {defaults["output_format"]}')
        command_parser.add_argument('-r', '--repeat', default=1, type=int,
                                    help='Number of times to repeat. Total images generated is number of repeats times batch size. (default: 1)')
        command_parser.add_argument('-s', '--sampler', type=str,
                                    help=f'Sampler to use for image diffusion (default: {defaults["sampler"]})')
        command_parser.add_argument('-S', '--scheduler', type=str,
                                    help=f'Scheduler to use for image diffusion (default: {defaults["scheduler"]})')
        command_parser.add_argument('-u', '--comfy-url', default=comfy_url,
                                    help=f'URL for the Comfy UI API (default: {comfy_url})')
        command_parser.add_argument('-x', '--seed', type=int,
                                    help=f'The seed to use when sampling (default: {defaults["seed"] if defaults["seed"] is not None else "random"})')

    def _save_output__save_to_disk(self, item, filename):
        """
        Save the given item to disk. Supports PIL.Image and HTTP response.raw objects.

        :param item: The item to save (PIL.Image.Image or HTTP response.raw).
        :param filename: The file path to save the item to.
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

    def _save_output(self, results, filename, start_index, single_output=False):
        """
        Saves a list of outputs to disk.

        Args:
            results (list): List of outputs to be saved.
            filename (str): Base filename to save the outputs. If multiple outputs, filenames
                            will increment as {basename}{x}.{extension}.
        """
        output_files = []

        if single_output:  # Save single output with provided filename
            self._save_output__save_to_disk(results[0], filename)
            output_files.append(filename)
        else:
            if not os.path.splitext(filename)[1]:
                raise ValueError("Filename must have an extension (e.g., 'output.png').")

            basename, extension = os.path.splitext(filename)

            # Save multiple outputs with incrementing filenames
            for i, output in enumerate(results, start=start_index):
                padded_index = f"{i:06d}"  # Zero-padded to 6 digits
                output_filename = f"{basename}{padded_index}{extension}"
                self._save_output__save_to_disk(output, output_filename)
                output_files.append(output_filename)

        logger.debug(f"saved: {', '.join(output_files)}")

    def run(self, arguments):
        self.comfy.set_url(arguments.comfy_url)

        # Create a dictionary containing only the supported and defined arguments for the handler
        arguments_dict = vars(arguments)
        defaults = self.comfy.defaults[arguments.comfy_command]
        function_arguments = {key: value for key, value in arguments_dict.items() if key in defaults and arguments_dict[key] is not None}

        # True when there is only a single file output
        batch_size = function_arguments.get('batch_size', defaults['batch_size'])
        single_output = (arguments.repeat == 1 and batch_size == 1)

        for i in range(0, arguments.repeat):
            output = self.comfy.run_workflow(arguments.comfy_command, **function_arguments)
            self._save_output(output, arguments.output_file, i * len(output),
                              single_output=single_output)
