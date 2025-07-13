import os
import subprocess
import tempfile
import traceback

import lair
from lair.logging import logger


class PythonTool:
    name = "python"

    def __init__(self):
        pass

    def add_to_tool_set(self, tool_set):
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="run_python",
            flags=["tools.python.enabled"],
            definition_handler=lambda: self._generate_definition(),
            handler=lambda *args, **kwargs: self.run_python(*args, **kwargs),
        )

    def _generate_definition(self):
        settings = {
            "timeout": lair.config.get("tools.python.timeout"),
            "extra_modules": lair.config.get("tools.python.extra_modules"),
        }

        return {
            "type": "function",
            "function": {
                "name": "run_python",
                "description": (
                    "Run a python script and return the output. "
                    "This is not a REPL. Repeat calls are independent. Output must be printed to be retrieved. "
                    "STDOUT, STDERR are returned.) "
                    "(extra_modules=%(extra_modules)s, timeout=%(timeout)s)" % settings
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "The Python script to execute",
                        }
                    },
                    "required": ["script"],
                },
            },
        }

    def _cleanup_container(self, container_id):
        """Force remove a container by id."""
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, text=True)

    def _format_output(self, *, error=None, stdout=None, stderr=None, exit_status=None):
        output = {}

        if error:
            output["error"] = f"{error}"
        if stdout and stdout.strip():
            output["stdout"] = f"{stdout.strip()}"
        if stderr and stderr.strip():
            output["stderr"] = f"{stderr.strip()}"
        if exit_status is not None:
            output["exit_status"] = exit_status

        return output

    def run_python(self, script):
        container_id = None
        temp_file_path = None

        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as temp_file:
                temp_file.write(script)
                temp_file_path = os.path.abspath(temp_file.name)

            run_proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "-v",
                    f"{temp_file_path}:/tmp/script.py:ro",
                    lair.config.get("tools.python.docker_image"),
                    "python",
                    "/tmp/script.py",
                ],
                capture_output=True,
                text=True,
            )
            if run_proc.returncode != 0:
                return self._format_output(error="ERROR: Failed to start_container", exit_status=run_proc.returncode)

            container_id = run_proc.stdout.strip()

            try:  # Wait for the container to finish execution, with a timeout.
                wait_proc = subprocess.run(
                    ["docker", "wait", container_id],
                    capture_output=True,
                    text=True,
                    timeout=lair.config.get("tools.python.timeout"),
                )
            except subprocess.TimeoutExpired:
                self._cleanup_container(container_id)
                return self._format_output(
                    error=f'ERROR: Timeout after {lair.config.get("tools.python.timeout")} seconds'
                )
            try:
                exit_status = int(wait_proc.stdout.strip())
            except ValueError:
                exit_status = None

            logs_proc = subprocess.run(["docker", "logs", container_id], capture_output=True, text=True)

            self._cleanup_container(container_id)

            return self._format_output(stdout=logs_proc.stdout, stderr=logs_proc.stderr, exit_status=exit_status)
        except Exception as error:
            if container_id:
                self._cleanup_container(container_id)
            logger.warning(f"run_python(): Error encountered: {error}")
            return self._format_output(error=f"{error}\n{traceback.format_exc()}")
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
