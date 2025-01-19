import base64
import datetime
import glob
import importlib.resources
import json
import logging
import mimetypes
import pathlib
import os
import re

import lair
from lair.logging import logger

import yaml


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
    with open(os.path.expanduser(filename), 'r') as fd:
        document = fd.read()

    return document


def save_file(filename, contents):
    with open(os.path.expanduser(filename), 'w') as fd:
        fd.write(contents)


def parse_yaml_text(text):
    return yaml.safe_load(text)


def parse_yaml_file(filename):
    with open(filename, 'r') as fd:
        return yaml.safe_load(fd)


def load_json_file(filename):
    return json.loads(slurp_file(filename))


def save_json_file(filename, document):
    json_document = safe_dump_json(document)

    with open(filename, 'w') as fd:
        fd.write(json_document)


def get_lib_path(end=''):
    """Return the path to the recon library."""
    return os.path.dirname(__file__) + '/../' + end


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
    return re.sub(r'\033\[\d+(;\d+)*m', '', content)


def get_message(role, message):
    return {
        "role": role,
        "content": message,
    }


def expand_filename_list(filenames, *, fail_on_not_found=True, sort_results=True):
    '''Expand user and globs in filenames and return the expanded list'''
    new_filenames = []

    for filename in filenames:
        matches = glob.glob(os.path.expanduser(filename))

        if not matches and fail_on_not_found:
            raise Exception('File not found: %s' % filename)

        new_filenames.extend(matches)

    return sorted(new_filenames) if sort_results else new_filenames


def _get_attachments_content__image_file(filename):
    mime_type = mimetypes.guess_type(filename)[0]  # Extract the MIME type
    if not mime_type or not mime_type.startswith('image/'):
        raise ValueError(f"File has image extension, but non-image mime type: {filename}  (mime={mime_type})")

    parts = []
    with open(filename, 'rb') as fd:
        if lair.config.get('model.provide_attachment_filenames'):
            parts.append({"type": "text", "text": f"Attached File: {filename} ({mime_type})"})

        base64_str = base64.b64encode(fd.read()).decode('utf-8')
        parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{base64_str}",
            }
        })

    return parts

def _get_attachments_content__text_file(filename):
    messages = []

    limit = lair.config.get('misc.text_attachment_max_size')
    do_truncate = False
    if os.path.getsize(filename) > limit:
        if not lair.config.get('misc.text_attachment_truncate'):
            raise Exception("Attachment is greater than limit set by misc.text_attachment_max_size: file={filename}, size={os.path.getsize(filename)}, limit={limit}")
        else:
            do_truncate = True

    try:
        with open(filename, 'r') as fd:
            contents = fd.read(limit if do_truncate else None)
    except UnicodeDecodeError as error:
        raise Exception(f"File attachment is not text: file={filename}, error={error}")

    if lair.config.get('model.provide_attachment_filenames'):
        header = f'User provided file: filename={filename}\n---\n'
    else:
        header = 'User provided file:\n---\n'

    messages.append(lair.util.get_message('user', header + contents))

    return messages

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

        if extension in {'gif', 'jpg', 'jpeg', 'png', 'webp'}:
            content_parts.extend(_get_attachments_content__image_file(filename))
        elif extension == 'pdf':
            raise Exception("PDF attachment not supported")
        else:
            messages.extend(_get_attachments_content__text_file(filename))

    return content_parts, messages
