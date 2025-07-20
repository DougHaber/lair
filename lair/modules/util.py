"""Utility module providing a thin wrapper around LLM chat sessions."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from typing import Any

import lair
import lair.cli
import lair.reporting
import lair.sessions
import lair.util
from lair.logging import logger  # noqa
from lair.sessions.base_chat_session import BaseChatSession


def _module_info() -> dict[str, Any]:
    """Return metadata describing this module.

    Returns:
        dict[str, Any]: Information used by the module loader.

    """
    return {
        "description": "Make simple calls to LLMs",
        "class": Util,
        "tags": [],
        "aliases": [],
    }


class Util:
    """Expose utility commands for interacting with chat models."""

    def __init__(self, parser: argparse.ArgumentParser) -> None:
        """Initialize argument parser options for the ``util`` command.

        Args:
            parser: The argument parser to register options with.

        """
        parser.add_argument(
            "-a",
            "--attach-file",
            type=str,
            dest="attachments",
            action="append",
            help=(
                "Specify one or more image files to attach to the request. Multiple files "
                "may be provided by repeating the argument. Ensure the model you are interacting "
                "with supports file attachments. Globs are supported."
            ),
        )
        (parser.add_argument("-c", "--content", type=str, help="Content to use"),)
        parser.add_argument("-C", "--content-file", type=str, help="Filename containing content use")
        parser.add_argument(
            "-F",
            "--include-filenames",
            action="store_true",
            default=None,
            help=(
                "Provide filenames of attached files (via misc.provide_attachment_filenames, "
                f"default={lair.config.get('misc.provide_attachment_filenames')})"
            ),
        )
        parser.add_argument("-i", "--instructions", type=str, help="Instructions for the request")
        parser.add_argument(
            "-I", "--instructions-file", type=str, help="Filename containing instructions for the request"
        )
        parser.add_argument("-m", "--markdown", action="store_true", help="Enable markdown output")
        parser.add_argument("-p", "--pipe", action="store_true", help="Read content from stdin")
        parser.add_argument("-r", "--read-only-session", action="store_true", help="Do not modify the session used")
        parser.add_argument("-s", "--session", type=str, help="Session id or alias to use.")
        parser.add_argument(
            "-S",
            "--allow-create-session",
            action="store_true",
            help="If an alias provided via --session is not found, create it",
        )
        parser.add_argument("-t", "--enable-tools", action="store_true", help="Allow the model to call tools")

    def call_llm(
        self,
        chat_session: BaseChatSession,
        *,
        instructions: str,
        user_messages: Iterable[dict[str, Any]],
        enable_tools: bool = True,
    ) -> str:
        """Send the composed messages to the LLM.

        Args:
            chat_session: The chat session to send messages through.
            instructions: System level instructions for the model.
            user_messages: Additional user messages to include.
            enable_tools: Whether tool calls are permitted.

        Returns:
            str: The model's response.

        """
        messages = [
            lair.util.get_message("user", instructions),
            *user_messages,
        ]

        lair.config.set("tools.enabled", enable_tools)
        response = chat_session.chat(messages)

        return response

    def clean_response(self, response: str) -> str:
        """Strip formatting markup from the LLM response.

        Args:
            response: The raw response returned by the model.

        Returns:
            str: The cleaned response.

        """
        response = re.sub(r"^```.*\n?", "", response, flags=re.MULTILINE)

        return response

    def _read_file(self, filename: str) -> str:
        """Return the contents of ``filename``.

        Args:
            filename: Path to the file to read.

        Returns:
            str: The file contents.

        """
        with open(filename) as fd:
            return fd.read()

    def _get_instructions(self, arguments: argparse.Namespace) -> str:
        """Return instructions text from command line arguments.

        Args:
            arguments: Parsed command-line arguments.

        Returns:
            str: The instruction text.

        """
        if arguments.instructions_file:
            return self._read_file(arguments.instructions_file)
        if arguments.instructions:
            return arguments.instructions

        logger.error("Either --instructions or --instructions-file must be proved")
        sys.exit(1)

    def _get_user_messages(self, arguments: argparse.Namespace) -> list[dict[str, Any]]:
        """Build the list of user messages based on the provided arguments.

        Args:
            arguments: Parsed command-line arguments.

        Returns:
            list[dict[str, Any]]: Messages prepared for sending to the model.

        """
        # Read the user "content" message
        message = None
        if arguments.pipe:
            message = sys.stdin.read()
        elif arguments.content_file:
            message = self._read_file(arguments.content_file)
        elif arguments.content:
            message = arguments.content

        if message:  # These extra instructions helps a lot in some models
            message = "CONTENT is found below. Everything above is instructions and rules:\n" + message

        messages = []
        if arguments.attachments:
            attachment_content_parts, attachment_messages = lair.util.get_attachments_content(arguments.attachments)
            messages.extend(attachment_messages)
        else:
            attachment_content_parts = []

        # Add the regular message as a standard message, or image sections if there are images

        if message:
            messages.append(lair.util.get_message("user", message))

        messages.append(
            {
                "role": "user",
                "content": attachment_content_parts,
            }
        )

        return messages

    def _init_session_manager(
        self, chat_session: BaseChatSession, arguments: argparse.Namespace
    ) -> lair.sessions.SessionManager | None:
        """Prepare a session manager based on user options.

        Args:
            chat_session: The chat session in use.
            arguments: Parsed command-line arguments.

        Returns:
            Optional[lair.sessions.SessionManager]: The session manager instance or ``None``.

        """
        if not arguments.session:
            chat_session.session_title = "N/A"  # Prevent wasteful auto-title generation
            return None

        session_manager = lair.sessions.SessionManager()
        try:
            session_manager.switch_to_session(arguments.session, chat_session)
        except lair.sessions.UnknownSessionException:
            if not arguments.allow_create_session:
                logger.error(f"Unknown session: {arguments.session}")
                sys.exit(1)

            if arguments.read_only_session:
                logger.error("Unable to create a new session with the --read-only-session flag.")
                sys.exit(1)

            if not session_manager.is_alias_available(arguments.session):
                if isinstance(lair.util.safe_int(arguments.session), int):
                    logger.error("Failed to create new session. Session aliases may not be integers.")
                else:
                    logger.error("Failed to create new session. Alias is already used.")
                sys.exit(1)

            chat_session.session_alias = arguments.session
            session_manager.add_from_chat_session(chat_session)

        return session_manager

    def run(self, arguments: argparse.Namespace) -> None:
        """Execute the util command with the provided arguments.

        Args:
            arguments: Parsed command-line arguments.

        """
        chat_session = lair.sessions.get_chat_session(
            session_type=lair.config.get("session.type"),
        )
        session_manager = self._init_session_manager(chat_session, arguments)
        config_backup = lair.config.active.copy()
        util_prompt_template = lair.config.get("util.system_prompt_template")

        if arguments.model:
            lair.config.set("model.name", arguments.model)
        lair.config.set("session.system_prompt_template", util_prompt_template)
        lair.config.set("style.render_markdown", arguments.markdown)

        if arguments.include_filenames is not None:
            lair.config.set("misc.provide_attachment_filenames", arguments.include_filenames)

        instructions = self._get_instructions(arguments)
        user_messages = self._get_user_messages(arguments)

        response = self.call_llm(
            chat_session, instructions=instructions, enable_tools=arguments.enable_tools, user_messages=user_messages
        )
        response = self.clean_response(response)

        if session_manager is not None and not arguments.read_only_session:
            # The original configuration is restored so that there are no configuration changes.
            lair.config.update(config_backup)
            session_manager.refresh_from_chat_session(chat_session)

        if arguments.markdown:
            reporting = lair.reporting.Reporting()
            reporting.llm_output(response)
        else:
            sys.stdout.write(response + "\n")
