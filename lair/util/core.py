"""Utility helpers used across the Lair project."""

from __future__ import annotations

import base64
import datetime
import glob
import importlib.resources
import json
import logging
import mimetypes
import os
import pathlib
import re
import shlex
import subprocess
import tempfile
from typing import TypeVar, cast

import pdfplumber
import yaml

import lair
from lair.logging import logger

T = TypeVar("T")

subprocess_run = subprocess.run


def safe_dump_json(document: object) -> str:
    """
    Serialize a document to JSON while handling ``datetime`` objects.

    Args:
        document: Any JSON serializable structure.

    Returns:
        A JSON string representation of ``document``.

    """

    def fix_date(x: object) -> object:
        return str(x) if isinstance(x, datetime.datetime) else x

    return json.dumps(document, default=fix_date)


def safe_int(number: str | float) -> int | str | float:
    """
    Convert a value to ``int`` if possible.

    Args:
        number: Value to convert.

    Returns:
        ``int`` when conversion succeeds, otherwise the original ``number``.

    """
    try:
        return int(number)
    except Exception:
        return number


def slurp_file(filename: str) -> str:
    """
    Read a file and return its contents.

    Args:
        filename: Path to the file. ``~`` expansion is supported.

    Returns:
        The content of the file.

    """
    with open(os.path.expanduser(filename)) as fd:
        document = fd.read()

    return document


def save_file(filename: str, contents: str) -> None:
    """
    Write ``contents`` to ``filename``.

    Args:
        filename: Destination path. ``~`` expansion is supported.
        contents: Text to write to the file.

    """
    with open(os.path.expanduser(filename), "w") as fd:
        fd.write(contents)


def parse_yaml_text(text: str) -> dict:
    """Parse YAML content using PyYAML."""
    data = yaml.safe_load(text)
    return data or {}


def parse_yaml_file(filename: str) -> dict:
    """
    Read a YAML file from disk.

    Args:
        filename: Path to the YAML file.

    Returns:
        Parsed YAML data as a dictionary.

    """
    with open(filename) as fd:
        contents = fd.read()
    return parse_yaml_text(contents)


def load_json_file(filename: str) -> object:
    """Load JSON data from a file."""
    return json.loads(slurp_file(filename))


def save_json_file(filename: str, document: object) -> None:
    """Serialize ``document`` to JSON and save it to ``filename``."""
    json_document = safe_dump_json(document)

    with open(filename, "w") as fd:
        fd.write(json_document)


def get_lib_path(end: str = "") -> str:
    """
    Return the path to the library directory.

    Args:
        end: Optional suffix to append to the base path.

    Returns:
        The absolute path to the requested location.

    """
    return os.path.dirname(__file__) + "/../" + end


def read_package_file(path: str, name: str) -> str:
    """
    Read a file bundled with the package.

    Args:
        path: Dot-delimited package path, e.g. ``"lair.files"``.
        name: Filename within the package.

    Returns:
        The file contents as a string.

    """
    with importlib.resources.open_text(path, name) as fd:
        return fd.read()


def get_log_level() -> str:
    """Return the current log level name."""
    return logging.getLevelName(logger.level)


def is_debug_enabled() -> bool:
    """Check whether debug logging is enabled."""
    return logger.getEffectiveLevel() <= logging.DEBUG


def strip_escape_codes(content: str) -> str:
    """Remove ANSI escape codes from ``content``."""
    return re.sub(r"\033\[[0-9;?]*[a-zA-Z]", "", content)


def get_message(role: str, message: str) -> dict[str, str]:
    """Create a structured chat message."""
    return {
        "role": role,
        "content": message,
    }


def expand_filename_list(
    filenames: list[str], *, fail_on_not_found: bool = True, sort_results: bool = True
) -> list[str]:
    """
    Expand user paths and globs.

    Args:
        filenames: A list of filename patterns.
        fail_on_not_found: Raise ``Exception`` when no matches are found.
        sort_results: Whether to sort the resulting list.

    Returns:
        List of expanded filenames.

    """
    new_filenames: list[str] = []

    for filename in filenames:
        matches = glob.glob(os.path.expanduser(filename))

        if not matches and fail_on_not_found:
            raise Exception(f"File not found: {filename}")

        new_filenames.extend(matches)

    return sorted(new_filenames) if sort_results else new_filenames


def _get_attachments_content__image_file(filename: str) -> list[dict[str, object]]:
    """
    Return image parts for an attachment.

    Args:
        filename: Path to the image file.

    Returns:
        A list of content parts suitable for OpenAI image attachments.

    """
    mime_type = mimetypes.guess_type(filename)[0]  # Extract the MIME type
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"File has image extension, but non-image mime type: {filename}  (mime={mime_type})")

    parts: list[dict[str, object]] = []
    with open(filename, "rb") as fd:
        if lair.config.get("misc.provide_attachment_filenames"):
            parts.append({"type": "text", "text": f"Attached File: {filename} ({mime_type})"})

        base64_str = base64.b64encode(fd.read()).decode("utf-8")
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_str}",
                },
            }
        )

    return parts


def read_pdf(filename: str, *, enforce_limits: bool = False) -> str:
    """
    Extract text from a PDF file.

    Args:
        filename: Path to the PDF file.
        enforce_limits: Whether to stop reading when the configured limit is exceeded.

    Returns:
        The extracted text.

    """
    limit = cast(int, lair.config.get("misc.text_attachment_max_size"))

    with pdfplumber.open(filename) as pdf_reader:
        contents = ""
        for page in pdf_reader.pages:
            contents += page.extract_text(x_tolerance=2, y_tolerance=2)
            if enforce_limits and len(contents) > limit:
                if not lair.config.get("misc.text_attachment_truncate"):
                    raise Exception(
                        "Attachment size exceeds limit: "
                        f"file={filename}, size={os.path.getsize(filename)}, limit={limit}"
                    )
                else:
                    logger.warning(
                        "Attachment size exceeds limit: "
                        f"file={filename}, size={os.path.getsize(filename)}, limit={limit}"
                    )
                    contents = contents[0:limit]
                    break

    return contents


def _get_attachments_content__pdf_file(filename: str) -> dict[str, str]:
    """
    Create a chat message from a PDF attachment.

    Args:
        filename: Path to the PDF file.

    Returns:
        A message dictionary suitable for sending to the chat API.

    """
    contents = read_pdf(filename)

    if lair.config.get("misc.provide_attachment_filenames"):
        header = f"User provided file: filename={filename}\n---\n"
    else:
        header = "User provided file:\n---\n"

    return lair.util.get_message("user", header + contents)


def _get_attachments_content__text_file(filename: str) -> dict[str, str]:
    """
    Create a chat message from a text attachment.

    Args:
        filename: Path to the text file.

    Returns:
        A message dictionary containing the file text.

    """
    limit = cast(int, lair.config.get("misc.text_attachment_max_size"))
    do_truncate = False
    if os.path.getsize(filename) > limit:
        if not lair.config.get("misc.text_attachment_truncate"):
            raise Exception(
                f"Attachment size exceeds limit: file={filename}, size={os.path.getsize(filename)}, limit={limit}"
            )
        else:
            logger.warning(
                f"Attachment size exceeds limit: file={filename}, size={os.path.getsize(filename)}, limit={limit}"
            )
            do_truncate = True

    try:
        with open(filename) as fd:
            contents = fd.read(limit if do_truncate else None)
    except UnicodeDecodeError as error:
        raise Exception(f"File attachment is not text: file={filename}, error={error}") from error

    if lair.config.get("misc.provide_attachment_filenames"):
        header = f"User provided file: filename={filename}\n---\n"
    else:
        header = "User provided file:\n---\n"

    return lair.util.get_message("user", header + contents)


def get_attachments_content(
    filenames: list[str],
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """
    Generate chat-ready content from a list of filenames.

    Args:
        filenames: Filenames or glob patterns. ``~`` expansion is supported.

    Returns:
        A tuple ``(content_parts, messages)`` where ``content_parts`` contains
        image parts and ``messages`` contains text messages.

    """
    content_parts: list[dict[str, object]] = []
    messages: list[dict[str, str]] = []
    for filename in expand_filename_list(filenames):
        extension = pathlib.Path(filename).suffix[1:]

        if extension.lower() in {"gif", "jpg", "jpeg", "png", "webp"}:
            content_parts.extend(_get_attachments_content__image_file(filename))
        elif extension == "pdf":
            messages.append(_get_attachments_content__pdf_file(filename))
        else:
            messages.append(_get_attachments_content__text_file(filename))

    return content_parts, messages


def edit_content_in_editor(content: str, suffix: str | None = None) -> str | None:
    """
    Edit text in an external editor.

    Args:
        content: The text to edit.
        suffix: Optional filename suffix for the temporary file.

    Returns:
        The modified content, or ``None`` if unchanged.

    """
    editor_cmd = str(lair.config.get("misc.editor_command") or os.getenv("VISUAL") or os.getenv("EDITOR") or "vi")
    editor_args = shlex.split(editor_cmd)

    with tempfile.NamedTemporaryFile(mode="w+t", delete=False, suffix=suffix) as temp_file:
        temp_path = pathlib.Path(temp_file.name)
        temp_file.write(content)
        temp_file.close()

        try:
            run = subprocess.run
            run(editor_args + [str(temp_path)], check=True)
            modified_content = temp_path.read_text()

            return modified_content if modified_content != content else None
        finally:
            temp_path.unlink()


def decode_jsonl(jsonl_str: str) -> list[dict[str, object]]:
    """
    Decode JSONL content into a list of records.

    Args:
        jsonl_str: The JSONL-formatted string.

    Returns:
        A list of dictionaries parsed from each line.

    """
    records: list[dict[str, object]] = []
    for line in jsonl_str.split("\n"):
        if line:  # Process only non-blank lines
            records.append(json.loads(line))

    return records


def slice_from_str(original_list: list[T], slice_str: str) -> list[T]:
    """
    Apply a ``slice`` string to a list.

    Args:
        original_list: The list to slice.
        slice_str: Slice notation such as ``":2"`` or ``"1:4:2"``.

    Returns:
        A new list containing the sliced elements.

    """
    parts = slice_str.split(":")

    def safe_int(value: str) -> int | None:
        """Convert to integer if ``value`` is not empty."""
        return int(value) if value else None

    # Convert parts to integers or None
    start = safe_int(parts[0]) if len(parts) > 0 and parts[0] else None
    stop = safe_int(parts[1]) if len(parts) > 1 and parts[1] else None
    step = safe_int(parts[2]) if len(parts) > 2 and parts[2] else None

    return original_list[slice(start, stop, step)]
