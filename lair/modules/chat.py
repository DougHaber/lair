"""Chat module for the command line interface."""

from __future__ import annotations

import argparse
from typing import Any

import lair
import lair.cli


def _module_info() -> dict[str, Any]:
    """Return metadata about this module."""
    return {
        "description": "Run the interactive Chat interface",
        "class": Chat,
        "tags": ["cli"],
        "aliases": [],
    }


class Chat:
    """Interface for starting and managing chat sessions."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        """
        Initialize the chat subcommand.

        Args:
            parser: Parser to which chat arguments are added.

        """
        parser.add_argument("-s", "--session", type=str, help="Session id or alias to use.")
        parser.add_argument(
            "-S",
            "--allow-create-session",
            action="store_true",
            help="If an alias provided via --session is not found, create it",
        )

    def run(self, arguments: argparse.Namespace) -> None:
        """
        Start the chat interface with the provided arguments.

        Args:
            arguments: Parsed command line arguments.

        """
        chat = lair.cli.ChatInterface(
            starting_session_id_or_alias=arguments.session,
            create_session_if_missing=arguments.allow_create_session,
        )
        chat.start()
