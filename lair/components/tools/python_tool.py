import os
import shlex
import shutil
import subprocess
import tempfile
import traceback

import lair
from lair.logging import logger


class PythonTool:
    name = "python"

    def __init__(self):
        self._docker = shutil.which("docker") or "docker"

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
                    "This is not a REPL. Repeat calls are independent. "
                    "Output must be printed to be retrieved. "
                    f"STDOUT, STDERR are returned.) (extra_modules={settings['extra_modules']}, "
                    f"timeout={settings['timeout']})"
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
        run = subprocess.run
        run(
            [
                shlex.quote(self._docker),
                "rm",
                "-f",
                shlex.quote(container_id),
            ],
            capture_output=True,
            text=True,
        )

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
            container_script_path = os.path.join(tempfile.gettempdir(), os.path.basename(temp_file_path))

            run = subprocess.run
            run_proc = run(
                [
                    shlex.quote(self._docker),
                    "run",
                    "-d",
                    "-v",
                    f"{shlex.quote(temp_file_path)}:{shlex.quote(container_script_path)}:ro",
                    shlex.quote(lair.config.get("tools.python.docker_image")),
                    "python",
                    shlex.quote(container_script_path),
                ],
                capture_output=True,
                text=True,
            )
            if run_proc.returncode != 0:
                return self._format_output(error="ERROR: Failed to start_container", exit_status=run_proc.returncode)

            container_id = run_proc.stdout.strip()

            try:  # Wait for the container to finish execution, with a timeout.
                wait_proc = run(
                    [shlex.quote(self._docker), "wait", shlex.quote(container_id)],
                    capture_output=True,
                    text=True,
                    timeout=lair.config.get("tools.python.timeout"),
                )
            except subprocess.TimeoutExpired:
                self._cleanup_container(container_id)
                return self._format_output(
                    error=f"ERROR: Timeout after {lair.config.get('tools.python.timeout')} seconds"
                )
            try:
                exit_status = int(wait_proc.stdout.strip())
            except ValueError:
                exit_status = None

            logs_proc = run(
                [shlex.quote(self._docker), "logs", shlex.quote(container_id)],
                capture_output=True,
                text=True,
            )

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
