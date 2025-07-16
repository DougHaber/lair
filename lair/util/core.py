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
from typing import Optional

import pdfplumber
import yaml

import lair
from lair.logging import logger

subprocess_run = subprocess.run


def safe_dump_json(document):
    def fix_date(x):
        return str(x) if isinstance(x, datetime.datetime) else x

    return json.dumps(document, default=fix_date)


def safe_int(number):
    try:
        return int(number)
    except Exception:
        return number


def slurp_file(filename):
    with open(os.path.expanduser(filename), "r") as fd:
        document = fd.read()

    return document


def save_file(filename, contents):
    with open(os.path.expanduser(filename), "w") as fd:
        fd.write(contents)


def parse_yaml_text(text):
    return yaml.safe_load(text)


def parse_yaml_file(filename):
    with open(filename, "r") as fd:
        return yaml.safe_load(fd)


def load_json_file(filename):
    return json.loads(slurp_file(filename))


def save_json_file(filename, document):
    json_document = safe_dump_json(document)

    with open(filename, "w") as fd:
        fd.write(json_document)


def get_lib_path(end=""):
    """Return the path to the recon library."""
    return os.path.dirname(__file__) + "/../" + end


def read_package_file(path, name):
    """Read a file within the packages libdir.
    path - Package path (dot delimited, such as lair.files)
    name - Filename within the path"""
    with importlib.resources.open_text(path, name) as fd:
        return fd.read()


def get_log_level():
    return logging.getLevelName(logger.level)


def is_debug_enabled():
    return logger.getEffectiveLevel() <= logging.DEBUG


def strip_escape_codes(content):
    return re.sub(r"\033\[[0-9;?]*[a-zA-Z]", "", content)


def get_message(role, message):
    return {
        "role": role,
        "content": message,
    }


def expand_filename_list(filenames, *, fail_on_not_found=True, sort_results=True):
    """Expand user and globs in filenames and return the expanded list"""
    new_filenames = []

    for filename in filenames:
        matches = glob.glob(os.path.expanduser(filename))

        if not matches and fail_on_not_found:
            raise Exception("File not found: %s" % filename)

        new_filenames.extend(matches)

    return sorted(new_filenames) if sort_results else new_filenames


def _get_attachments_content__image_file(filename):
    mime_type = mimetypes.guess_type(filename)[0]  # Extract the MIME type
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"File has image extension, but non-image mime type: {filename}  (mime={mime_type})")

    parts = []
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


def read_pdf(filename, *, enforce_limits=False):
    limit = lair.config.get("misc.text_attachment_max_size")

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


def _get_attachments_content__pdf_file(filename):
    contents = read_pdf(filename)

    if lair.config.get("misc.provide_attachment_filenames"):
        header = f"User provided file: filename={filename}\n---\n"
    else:
        header = "User provided file:\n---\n"

    return lair.util.get_message("user", header + contents)


def _get_attachments_content__text_file(filename):
    limit = lair.config.get("misc.text_attachment_max_size")
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
        with open(filename, "r") as fd:
            contents = fd.read(limit if do_truncate else None)
    except UnicodeDecodeError as error:
        raise Exception(f"File attachment is not text: file={filename}, error={error}")

    if lair.config.get("misc.provide_attachment_filenames"):
        header = f"User provided file: filename={filename}\n---\n"
    else:
        header = "User provided file:\n---\n"

    return lair.util.get_message("user", header + contents)


def get_attachments_content(filenames):
    """
    Take a list of filenames and return the content
    Parameters:
        filenames: A list of filenames to generate attachments for. Globs and homedir
            expansion are supported.

    Returns:
        content_parts = list of OpenAI API style `content` messages
        messages = list of strings of chat messages for each text section.
    """
    content_parts = []
    messages = []
    for filename in expand_filename_list(filenames):
        extension = pathlib.Path(filename).suffix[1:]

        if extension.lower() in {"gif", "jpg", "jpeg", "png", "webp"}:
            content_parts.extend(_get_attachments_content__image_file(filename))
        elif extension == "pdf":
            messages.append(_get_attachments_content__pdf_file(filename))
        else:
            messages.append(_get_attachments_content__text_file(filename))

    return content_parts, messages


def edit_content_in_editor(content: str, suffix: Optional[str] = None) -> str | None:
    """
    Edit the content in an external editor
    Return the new content or None if unchanged
    """
    editor_cmd = lair.config.get("misc.editor_command") or os.getenv("VISUAL") or os.getenv("EDITOR") or "vi"
    editor_args = shlex.split(editor_cmd)

    temp_file = tempfile.NamedTemporaryFile(mode="w+t", delete=False, suffix=suffix)
    temp_path = pathlib.Path(temp_file.name)

    try:
        temp_file.write(content)
        temp_file.close()

        run = subprocess.run
        run(editor_args + [str(temp_path)], check=True)
        modified_content = temp_path.read_text()

        return modified_content if modified_content != content else None
    finally:
        temp_path.unlink()


def decode_jsonl(jsonl_str):
    """
    Decode JSONL content and return a list of each decoded line
    """
    records = []
    for line in jsonl_str.split("\n"):
        if line:  # Process only non-blank lines
            records.append(json.loads(line))

    return records


def slice_from_str(original_list, slice_str: str):
    """Apply a slice string (e.g., ':2', '-2:', '1:4:2') to a list and return the new list."""
    parts = slice_str.split(":")

    def safe_int(value):
        """Convert to integer if value is not empty, otherwise return None."""
        return int(value) if value else None

    # Convert parts to integers or None
    start = safe_int(parts[0]) if len(parts) > 0 and parts[0] else None
    stop = safe_int(parts[1]) if len(parts) > 1 and parts[1] else None
    step = safe_int(parts[2]) if len(parts) > 2 and parts[2] else None

    return original_list[slice(start, stop, step)]
