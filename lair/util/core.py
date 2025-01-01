import base64
import datetime
import glob
import importlib.resources
import json
import logging
import mimetypes
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
    with open(filename, 'r') as fd:
        document = fd.read()

    return document


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


def filenames_to_data_url_messages(filenames):
    messages = []
    for filename in expand_filename_list(filenames):
        mime_type = mimetypes.guess_type(filename)[0]  # Extract the MIME type
        if not mime_type:
            raise ValueError(f"Could not determine MIME type for file: {filename}")

        with open(filename, 'rb') as fd:
            if lair.config.active.get('model.provide_attachment_filenames'):
                messages.append({"type": "text", "text": f"Attached File: {filename} ({mime_type})"})

            base64_str = base64.b64encode(fd.read()).decode('utf-8')
            messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_str}",
                }
            })

    return messages
