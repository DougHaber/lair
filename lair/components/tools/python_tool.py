"""Tool for executing Python scripts inside Docker containers."""

import os
import shlex
import shutil
import subprocess
import tempfile
import traceback
from typing import Any, Optional, cast

import lair
from lair.components.tools.tool_set import ToolSet
from lair.logging import logger


class PythonTool:
    """Tool that exposes Python execution as a single callable function."""

    name = "python"

    def __init__(self) -> None:
        """Initialize the tool by resolving the docker binary path."""
        self._docker = shutil.which("docker") or "docker"

    def add_to_tool_set(self, tool_set: ToolSet) -> None:
        """
        Register this tool with a :class:`ToolSet` instance.

        Args:
            tool_set: The :class:`ToolSet` to register the tool with.

        """
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="run_python",
            flags=["tools.python.enabled"],
            definition_handler=lambda: self._generate_definition(),
            handler=lambda *args, **kwargs: self.run_python(*args, **kwargs),
        )

    def _generate_definition(self) -> dict[str, Any]:
        """Return the OpenAI function definition for ``run_python``."""
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
                    f"(extra_modules={settings['extra_modules']}, timeout={settings['timeout']})"
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

    def _cleanup_container(self, container_id: str) -> None:
        """
        Force remove a container by ID.

        Args:
            container_id: The ID of the Docker container to remove.

        """
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

    def _format_output(
        self,
        *,
        error: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        exit_status: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Normalize subprocess output for return to the caller.

        Args:
            error: Error message to include.
            stdout: Standard output from the command.
            stderr: Standard error from the command.
            exit_status: Exit status of the command if known.

        Returns:
            A dictionary containing any provided values with empty items removed.

        """
        output: dict[str, Any] = {}

        if error:
            output["error"] = f"{error}"
        if stdout and stdout.strip():
            output["stdout"] = f"{stdout.strip()}"
        if stderr and stderr.strip():
            output["stderr"] = f"{stderr.strip()}"
        if exit_status is not None:
            output["exit_status"] = exit_status

        return output

    def run_python(self, script: str) -> dict[str, Any]:
        """
        Execute the provided Python script inside a temporary Docker container.

        Args:
            script: The Python source code to run.

        Returns:
            A dictionary containing ``stdout``, ``stderr`` and ``exit_status`` or
            an ``error`` message if execution failed.

        """
        try:
            return self._run_python_inner(script)
        except Exception as error:
            if isinstance(error, subprocess.TimeoutExpired):
                return self._format_output(
                    error=f"ERROR: Timeout after {lair.config.get('tools.python.timeout')} seconds"
                )
            return self._handle_exception(error)

    def _run_python_inner(self, script: str) -> dict[str, Any]:
        container_id: Optional[str] = None
        temp_file_path, container_path = self._create_temp_script(script)
        try:
            container_id, start_status = self._start_container(temp_file_path, container_path)
            if container_id is None:
                return self._format_output(error="ERROR: Failed to start_container", exit_status=start_status)
            try:
                return self._collect_output(container_id)
            except Exception:
                if container_id:
                    self._cleanup_container(container_id)
                raise
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def _handle_exception(self, error: Exception) -> dict[str, Any]:
        logger.warning(f"run_python(): Error encountered: {error}")
        return self._format_output(error=f"{error}\n{traceback.format_exc()}")

    def _collect_output(self, container_id: str) -> dict[str, Any]:
        """Retrieve logs from ``container_id`` and format the result."""
        exit_status, stdout, stderr = self._get_container_output(container_id)
        return self._format_output(stdout=stdout, stderr=stderr, exit_status=exit_status)

    def _create_temp_script(self, script: str) -> tuple[str, str]:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as temp_file:
            temp_file.write(script)
            temp_file_path = os.path.abspath(temp_file.name)
        container_script_path = os.path.join(tempfile.gettempdir(), os.path.basename(temp_file_path))
        return temp_file_path, container_script_path

    def _start_container(self, host_path: str, container_path: str) -> tuple[str | None, int | None]:
        run = subprocess.run
        proc = run(
            [
                shlex.quote(self._docker),
                "run",
                "-d",
                "-v",
                f"{shlex.quote(host_path)}:{shlex.quote(container_path)}:ro",
                shlex.quote(cast(str, lair.config.get("tools.python.docker_image"))),
                "python",
                shlex.quote(container_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None, proc.returncode
        return proc.stdout.strip(), None

    def _get_container_output(self, container_id: str) -> tuple[Optional[int], str, str]:
        run = subprocess.run
        try:
            wait_proc = run(
                [shlex.quote(self._docker), "wait", shlex.quote(container_id)],
                capture_output=True,
                text=True,
                timeout=cast(float, lair.config.get("tools.python.timeout")),
            )
        except subprocess.TimeoutExpired:
            self._cleanup_container(container_id)
            raise

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
        return exit_status, logs_proc.stdout, logs_proc.stderr
