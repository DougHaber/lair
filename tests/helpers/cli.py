from __future__ import annotations

import contextlib
import importlib
import io
import sys
from dataclasses import dataclass
from shlex import split


@dataclass(frozen=True, slots=True)
class CliResult:
    """Result from running the lair CLI in a subprocess."""

    stdout: str
    returncode: int


def run_cli(command: str, *, expected_exit_code: int | None = None) -> CliResult:
    """
    Run the lair CLI and capture output.

    Args:
        command: CLI arguments as a single string, e.g. ``"chat --help"``.
        expected_exit_code: If provided, assert the process exits with this
            code.

    Returns:
        A ``CliResult`` containing combined stdout and stderr.

    Raises:
        AssertionError: If ``expected_exit_code`` is provided and does not
            match.
    """
    args = split(command)

    argv_backup = sys.argv
    sys.argv = ["lair", *args]
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                import lair
                import lair.cli.run as run_module

                # Some tests temporarily delete attributes on the `lair` package
                # or stub out submodules (e.g. `lair.comfy_caller`). Ensure
                # expected submodules are re-attached before running the CLI
                # entrypoint.
                sys.modules.pop("lair.comfy_caller", None)
                lair.comfy_caller = importlib.import_module("lair.comfy_caller")

                run_module.start()
                returncode = 0
            except SystemExit as exc:
                returncode = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.argv = argv_backup

    result = CliResult(stdout=stdout.getvalue() + stderr.getvalue(), returncode=returncode)

    if expected_exit_code is not None:
        assert result.returncode == expected_exit_code, result.stdout

    return result
