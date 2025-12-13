"""
Utility helpers used across the Lair project.

This module exports various utility functions for interacting with files,
parsing content, and handling attachments. Importing from this package makes
these helpers available for reuse in other parts of the code base.
"""

from lair.util.core import (
    _get_attachments_content__image_file,
    _get_attachments_content__pdf_file,
    _get_attachments_content__text_file,
    decode_jsonl,
    edit_content_in_editor,
    expand_filename_list,
    get_attachments_content,
    get_lib_path,
    get_log_level,
    get_message,
    is_debug_enabled,
    load_json_file,
    parse_yaml_file,
    parse_yaml_text,
    read_package_file,
    read_pdf,
    safe_dump_json,
    safe_int,
    save_file,
    save_json_file,
    slice_from_str,
    slurp_file,
    strip_escape_codes,
)

__all__ = [
    "_get_attachments_content__image_file",
    "_get_attachments_content__pdf_file",
    "_get_attachments_content__text_file",
    "decode_jsonl",
    "edit_content_in_editor",
    "expand_filename_list",
    "get_attachments_content",
    "get_lib_path",
    "get_log_level",
    "get_message",
    "is_debug_enabled",
    "load_json_file",
    "parse_yaml_file",
    "parse_yaml_text",
    "read_package_file",
    "read_pdf",
    "safe_dump_json",
    "safe_int",
    "save_file",
    "save_json_file",
    "slurp_file",
    "strip_escape_codes",
    "slice_from_str",
]
