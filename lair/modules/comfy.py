import inspect
import os

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

        command_parser = sub_parser.add_parser('image', help='Basic image creation workflow')
        command_parser.add_argument('-b', '--batch-size', default=1, type=int,
                                    help='Batch size  (default is 1)')
        command_parser.add_argument('-c', '--cfg', default=8.0, type=float,
                                    help='Classifier-free guidance scale')
        command_parser.add_argument('-H', '--output-height', default=512, type=int,
                                    help='Output file height  (default is 512)')
        command_parser.add_argument('-m', '--model-name', required=True, type=str,
                                    help='Name of the image diffusion model  (required)')
        command_parser.add_argument('-n', '--negative-prompt', default='', type=str,
                                    help='Negative prompt to use for image diffusion')
        command_parser.add_argument('-N', '--steps', default=20, type=int,
                                    help='Number of sampling steps  (default is 20)')
        command_parser.add_argument('-o', '--output-file', default='output.png', type=str,
                                    help='File to write output to. When batch size is greater than 1, the basename becomes a prefix.  (default is output.png)')
        command_parser.add_argument('-p', '--prompt', required=True, type=str,
                                    help='Prompt to use for image diffusion  (required)')
        command_parser.add_argument('-r', '--seed', default=None, type=int,
                                    help='The seed to use when sampling  (default is random)')
        command_parser.add_argument('-s', '--sampler', default='euler', type=str,
                                    help='Sampler to use for image diffusion  (default is euler)')
        command_parser.add_argument('-S', '--scheduler', default='normal', type=str,
                                    help='Scheduler to use for image diffusion  (default is normal)')
        command_parser.add_argument('-u', '--comfy-url', default='http://127.0.0.1:8188',
                                    help='URL for the Comfy UI API  (default is http://127.0.0.1:8188)')
        command_parser.add_argument('-w', '--output-width', default=512, type=int,
                                    help='Output file width  (default is 512)')

    def _save_output(self, results, filename):
        """
        Saves a list of outputs to disk.

        Args:
            results (list): List of outputs to be saved.
            filename (str): Base filename to save the outputs. If multiple outputs, filenames
                            will increment as {basename}{x}.{extension}.
        """
        if len(results) == 1:  # Save single output with provided filename
            results[0].save(filename)
        else:
            if not os.path.splitext(filename)[1]:
                raise ValueError("Filename must have an extension (e.g., 'output.png').")

            basename, extension = os.path.splitext(filename)

            # Save multiple outputs with incrementing filenames
            for i, output in enumerate(results, start=1):
                padded_index = f"{i:06d}"  # Zero-padded to 6 digits
                output_filename = f"{basename}{padded_index}{extension}"
                output.save(output_filename)

    def run(self, arguments):
        comfy = lair.comfy_caller.ComfyCaller(arguments.comfy_url)

        commands = {
            'image': comfy.workflow_generate_image,
        }

        handler = commands[arguments.comfy_command]

        # Call the handler, passing in only the existing parameters
        arguments_dict = vars(arguments)
        parameters = inspect.signature(handler).parameters
        function_arguments = {key: value for key,
                              value in arguments_dict.items() if key in parameters}
        output = handler(**function_arguments)

        self._save_output(output, arguments.output_file)
