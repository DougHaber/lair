"""Prompt toolkit based interactive chat interface."""

import os
import re
import shutil
import sys
import time
from typing import Any, cast

import prompt_toolkit
import prompt_toolkit.filters
import prompt_toolkit.formatted_text
import prompt_toolkit.history
import prompt_toolkit.key_binding
import prompt_toolkit.keys
import prompt_toolkit.styles

import lair
import lair.sessions
from lair.cli.chat_interface_commands import ChatInterfaceCommands
from lair.cli.chat_interface_completer import ChatInterfaceCompleter
from lair.cli.chat_interface_reports import ChatInterfaceReports
from lair.logging import logger  # noqa


class ChatInterface(ChatInterfaceCommands, ChatInterfaceReports):
    """Interactive chat user interface."""

    def __init__(
        self,
        *,
        starting_session_id_or_alias: str | int | None = None,
        create_session_if_missing: bool = False,
    ) -> None:
        """Initialize the interface and attach to a chat session.

        Args:
            starting_session_id_or_alias: Session identifier or alias to start
                with.
            create_session_if_missing: Create the session if it does not exist.

        """
        session_type = cast(str, lair.config.get("session.type"))
        self.chat_session = lair.sessions.get_chat_session(session_type)
        self.session_manager = lair.sessions.SessionManager()
        self._init_starting_session(starting_session_id_or_alias, create_session_if_missing)

        self.last_used_session_id: int | None = None

        self.commands = self._get_commands()
        self.reporting = lair.reporting.Reporting()
        self._models: list[dict[str, Any]] | None = None  # Cached list of models

        self.flash_message: str | None = None
        self.flash_message_expiration: float = 0.0
        self.is_reading_prompt = False

        self.history: prompt_toolkit.history.History | None = None
        self.sub_prompt_history = {  # Prompt history for each sub-prompt type
            "session_set_alias": prompt_toolkit.history.InMemoryHistory(),
            "session_set_title": prompt_toolkit.history.InMemoryHistory(),
            "session_switch": prompt_toolkit.history.InMemoryHistory(),
        }

        self.prompt_session: prompt_toolkit.PromptSession | None = None
        self._on_config_update()  # Trigger the initial state updates

        lair.events.subscribe("config.update", lambda d: self._on_config_update(), instance=self)
        lair.events.fire("chat.init", self)

    def _on_config_update(self) -> None:
        """Update state when the configuration changes."""
        self._init_history()
        self._init_prompt_session()
        self._rebuild_chat_session()
        self._models = self.chat_session.list_models(ignore_errors=True)

    def _init_history(self) -> None:
        """Initialize the history backend."""
        history_file = lair.config.get("chat.history_file")
        if history_file:
            self.history = prompt_toolkit.history.FileHistory(os.path.expanduser(str(history_file)))
        else:
            self.history = None

    def _init_prompt_session(self) -> None:
        """Create the prompt session instance."""
        self.prompt_session = prompt_toolkit.PromptSession(
            bottom_toolbar=lambda: self._generate_toolbar(),
            completer=ChatInterfaceCompleter(self),
            enable_open_in_editor=True,
            enable_suspend=True,
            history=self.history,
            key_bindings=self._get_keybindings(),
            refresh_interval=0.2,
        )

    def _init_starting_session(
        self,
        id_or_alias: str | int | None,
        create_session_if_missing: bool,
    ) -> None:
        """Prepare the initial chat session."""
        if id_or_alias:
            try:
                self._switch_to_session(id_or_alias)
            except lair.sessions.UnknownSessionException:
                if create_session_if_missing:
                    if not self.session_manager.is_alias_available(id_or_alias):
                        if isinstance(lair.util.safe_int(id_or_alias), int):
                            logger.error("Failed to create new session. Session aliases may not be integers.")
                        else:
                            logger.error("Failed to create new session. Alias is already used.")
                        sys.exit(1)

                    self.chat_session.session_alias = id_or_alias
                    self.session_manager.add_from_chat_session(self.chat_session)
                else:
                    logger.error(f"Unknown session: {id_or_alias}")
                    sys.exit(1)
        else:
            self.session_manager.add_from_chat_session(self.chat_session)

    def _get_shortcut_details(self) -> dict[str, str]:
        """Return a mapping of shortcuts to descriptions."""

        def format_key(name: str) -> str:
            return str(lair.config.get(f"chat.keys.{name}")).replace("escape ", "ESC-").replace("c-", "C-")

        return {  # shortcut ->  description
            "F1 - F12": "Switch to session 1-12",
            format_key("show_history"): "Show the full chat history",
            format_key("show_recent_history"): "Show the last two messages from the chat history",
            format_key("list_models"): "Show all available models",
            format_key("list_tools"): "Show all available tools",
            format_key("session.clear"): "Clear the current session's history",
            format_key("session.new"): "Create a new session",
            format_key("session.next"): "Cycle to the next session",
            format_key("session.previous"): "Cycle to the previous session",
            format_key("session.set_alias"): "Set an alias for the current session",
            format_key("session.set_title"): "set a title for the current session",
            format_key("session.show"): "Display all sessions",
            format_key("session.switch"): "Fast switch to a different session",
            format_key("show_help"): "Show keys and shortcuts",
            format_key("toggle_debug"): "Toggle debugging output",
            format_key("toggle_markdown"): "Toggle markdown rendering",
            format_key("toggle_multiline_input"): "Toggle multi-line input",
            format_key("toggle_toolbar"): "Toggle bottom toolbar",
            format_key("toggle_tools"): "Toggle tools",
            format_key("toggle_verbose"): "Toggle verbose output",
            format_key("toggle_word_wrap"): "Toggle word wrapping",
        }

    def _get_keybindings(self) -> prompt_toolkit.key_binding.KeyBindings:
        """Build the key binding table."""
        key_bindings = prompt_toolkit.key_binding.KeyBindings()

        def get_key(name: str) -> list[str]:
            return str(lair.config.get(f"chat.keys.{name}")).split(" ")

        key_bindings.add(
            "enter",
            filter=prompt_toolkit.filters.completion_is_selected,
        )(self._enter_key_on_selected_completion)

        key_bindings.add(*get_key("toggle_debug"), eager=True)(self.toggle_debug)
        key_bindings.add(*get_key("toggle_toolbar"), eager=True)(self.toggle_toolbar)
        key_bindings.add(
            *get_key("toggle_multiline_input"),
            eager=True,
        )(self.toggle_multiline_input)
        key_bindings.add(*get_key("toggle_markdown"), eager=True)(self.toggle_markdown)
        key_bindings.add(*get_key("toggle_tools"), eager=True)(self.toggle_tools)
        key_bindings.add(*get_key("toggle_verbose"), eager=True)(self.toggle_verbose)
        key_bindings.add(*get_key("toggle_word_wrap"), eager=True)(self.toggle_word_wrap)
        key_bindings.add(*get_key("session.new"), eager=True)(self.session_new)
        key_bindings.add(*get_key("session.next"), eager=True)(self.session_next)
        key_bindings.add(*get_key("session.clear"), eager=True)(self.session_clear)
        key_bindings.add(*get_key("session.previous"), eager=True)(self.session_previous)
        key_bindings.add(*get_key("session.set_alias"), eager=True)(self.session_set_alias)
        key_bindings.add(*get_key("session.set_title"), eager=True)(self.session_set_title)
        key_bindings.add(*get_key("session.show"), eager=True)(self.session_status)
        key_bindings.add(*get_key("session.switch"), eager=True)(self.session_switch)
        key_bindings.add(*get_key("show_help"), eager=True)(self.show_help)
        key_bindings.add(*get_key("show_history"), eager=True)(self.show_history)
        key_bindings.add(*get_key("show_recent_history"), eager=True)(self.show_recent_history)
        key_bindings.add(*get_key("list_models"), eager=True)(self.list_models)
        key_bindings.add(*get_key("list_tools"), eager=True)(self.list_tools)

        for i in range(1, 13):
            key_bindings.add(f"f{i}", eager=True)(self._f_key)

        return key_bindings

    # Key binding handlers -------------------------------------------------

    def _enter_key_on_selected_completion(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Insert a space when accepting an autocompletion."""
        current_buffer = event.app.current_buffer
        current_buffer.insert_text(" ")
        current_buffer.cancel_completion()

    def toggle_debug(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle debug logging output."""
        if lair.util.is_debug_enabled():
            logger.setLevel("INFO")
            self._prompt_handler_system_message("Debugging disabled")
        else:
            logger.setLevel("DEBUG")
            self._prompt_handler_system_message("Debugging enabled")

    def toggle_toolbar(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle the visibility of the bottom toolbar."""
        if lair.config.active["chat.enable_toolbar"]:
            lair.config.set("chat.enable_toolbar", "false")
            self._prompt_handler_system_message("Bottom toolbar disabled")
        else:
            lair.config.set("chat.enable_toolbar", "true")
            self._prompt_handler_system_message("Bottom toolbar enabled")

    def toggle_multiline_input(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle multi-line input mode."""
        if lair.config.active["chat.multiline_input"]:
            lair.config.set("chat.multiline_input", "false")
            self._prompt_handler_system_message("Multi-line input disabled")
        else:
            lair.config.set("chat.multiline_input", "true")
            self._prompt_handler_system_message("Multi-line input enabled")

    def toggle_markdown(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle markdown rendering."""
        if lair.config.active["style.render_markdown"]:
            lair.config.set("style.render_markdown", "false")
            self._prompt_handler_system_message("Markdown rendering disabled")
        else:
            lair.config.set("style.render_markdown", "true")
            self._prompt_handler_system_message("Markdown rendering enabled")

    def toggle_tools(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle tool usage in the chat session."""
        if lair.config.active["tools.enabled"]:
            lair.config.set("tools.enabled", "false")
            self._prompt_handler_system_message("Tools disabled")
        else:
            lair.config.set("tools.enabled", "true")
            self._prompt_handler_system_message("Tools enabled")

    def toggle_verbose(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle verbose output from the model."""
        if lair.config.active["chat.verbose"]:
            lair.config.set("chat.verbose", "false")
            self._prompt_handler_system_message("Verbose output disabled")
        else:
            lair.config.set("chat.verbose", "true")
            self._prompt_handler_system_message("Verbose output enabled")

    def toggle_word_wrap(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Toggle word wrapping for responses."""
        if lair.config.active["style.word_wrap"]:
            lair.config.set("style.word_wrap", "false")
            self._prompt_handler_system_message("Word wrap disabled")
        else:
            lair.config.set("style.word_wrap", "true")
            self._prompt_handler_system_message("Word wrap enabled")

    def session_new(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Create a new chat session."""
        self._new_chat_session()
        self._prompt_handler_system_message("New session created")

    def session_next(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Switch to the next available session."""
        session_id = self.session_manager.get_next_session_id(self.chat_session.session_id)
        if session_id is not None:
            self._switch_to_session(session_id)

    def session_clear(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Clear the current session's history."""
        self.chat_session.new_session(preserve_alias=True, preserve_id=True)
        self.session_manager.refresh_from_chat_session(self.chat_session)
        self._prompt_handler_system_message("Conversation history cleared")

    def session_previous(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Switch to the previous session."""
        session_id = self.session_manager.get_previous_session_id(self.chat_session.session_id)
        if session_id is not None:
            self._switch_to_session(session_id)

    def session_set_alias(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Prompt for and set a session alias."""
        prompt_toolkit.application.run_in_terminal(self._handle_session_set_alias)

    def session_set_title(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Prompt for and set a session title."""
        prompt_toolkit.application.run_in_terminal(self._handle_session_set_title)

    def session_status(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Display all sessions in a report."""
        prompt_toolkit.application.run_in_terminal(self.print_sessions_report)

    def session_switch(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Prompt for a session id or alias to switch to."""
        prompt_toolkit.application.run_in_terminal(self._handle_session_switch)

    def show_help(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Display available shortcuts and commands."""
        prompt_toolkit.application.run_in_terminal(self.print_help)

    def show_history(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Print the full chat history."""
        prompt_toolkit.application.run_in_terminal(self.print_history)

    def show_recent_history(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Print the last two messages from the chat history."""
        prompt_toolkit.application.run_in_terminal(lambda: self.print_history(num_messages=2))

    def list_models(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """List available models."""
        prompt_toolkit.application.run_in_terminal(lambda: self.print_models_report(update_cache=True))

    def list_tools(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """List available tools."""
        prompt_toolkit.application.run_in_terminal(self.print_tools_report)

    def _f_key(self, event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
        """Switch to a numbered session using the F keys."""
        session_id = int(event.key_sequence[0].key[1:])
        prompt_toolkit.application.run_in_terminal(lambda: self._switch_to_session(session_id, raise_exceptions=False))

    def _new_chat_session(self) -> None:
        """Create and register a new chat session."""
        self.chat_session.new_session()
        # Reset the config to the default mode config
        lair.config.change_mode(lair.config.active_mode)
        self.session_manager.add_from_chat_session(self.chat_session)

    def _rebuild_chat_session(self) -> None:
        """Regenerate the current chat session."""
        # Changes to ``session.type`` may alter the chat session class used.
        old_chat_session = self.chat_session
        session_type = cast(str, lair.config.get("session.type"))
        self.chat_session = lair.sessions.get_chat_session(session_type)
        self.chat_session.import_state(old_chat_session)

    def _switch_to_session(self, id_or_alias: str | int, raise_exceptions: bool = True) -> None:
        """Switch to a different session.

        Args:
            id_or_alias: Session ID or alias to switch to.
            raise_exceptions: If ``True``, unknown sessions raise an exception.

        Raises:
            lair.sessions.UnknownSessionException: If the session is unknown and
                ``raise_exceptions`` is ``True``.

        """
        try:
            with lair.events.defer_events():
                old_session_id = self.chat_session.session_id
                self.session_manager.switch_to_session(id_or_alias, self.chat_session)
                self._rebuild_chat_session()
                if old_session_id != self.chat_session.session_id:
                    self.last_used_session_id = old_session_id
        except lair.sessions.UnknownSessionException:
            if raise_exceptions:
                raise
            else:
                logger.error(f"Unknown session: {id_or_alias}")

    def _get_default_switch_session_id(self) -> int | None:
        """Return the session ID used for quick switching.

        If the previously used session still exists it is returned; otherwise
        the next available session ID is used.
        """
        if self.last_used_session_id is not None and self.session_manager.get_session_id(
            self.last_used_session_id, raise_exception=False
        ):
            # If the last_used_session_id is still valid, return that
            return self.last_used_session_id
        else:
            return self.session_manager.get_next_session_id(self.chat_session.session_id)

    def _handle_session_switch(self) -> None:
        """Prompt the user for a session to switch to."""
        default_session_id = self._get_default_switch_session_id()

        key_bindings = prompt_toolkit.key_binding.KeyBindings()

        @key_bindings.add("tab")
        def show_sessions(event: prompt_toolkit.key_binding.KeyPressEvent) -> None:
            prompt_toolkit.application.run_in_terminal(lambda: self.print_sessions_report())

        try:
            id_or_alias_str = prompt_toolkit.prompt(
                f"Switch to session (default {default_session_id}): ",
                history=self.sub_prompt_history["session_switch"],
                in_thread=True,
                key_bindings=key_bindings,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        id_or_alias: str | int = cast(str | int, id_or_alias_str or default_session_id)

        try:
            self._switch_to_session(id_or_alias)
        except lair.sessions.UnknownSessionException:
            self.reporting.user_error(f"ERROR: Unknown session: {id_or_alias}")

    def _handle_session_set_alias(self) -> None:
        """Prompt the user to assign an alias to the current session."""
        session_id = self.chat_session.session_id

        try:
            new_alias = prompt_toolkit.prompt(
                f"Alias for session {session_id}: ",
                history=self.sub_prompt_history["session_set_alias"],
                in_thread=True,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        if self.session_manager.is_alias_available(new_alias):
            self.chat_session.session_alias = new_alias
            self.session_manager.set_alias(session_id, new_alias)
        elif isinstance(lair.util.safe_int(new_alias), int):
            self.reporting.user_error("ERROR: Aliases may not be integers")
        else:
            self.reporting.user_error("ERROR: That alias is unavailable")

    def _handle_session_set_title(self) -> None:
        """Prompt the user to set a title for the current session."""
        session_id = self.chat_session.session_id
        try:
            new_title = prompt_toolkit.prompt(
                f"Title for session {session_id}: ",
                history=self.sub_prompt_history["session_set_title"],
                in_thread=True,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        self.session_manager.set_title(session_id, new_title or None)

    def _handle_request_command(self, request: str) -> bool:
        """Handle slash commands."""
        command, *arguments = re.split(r"\s+", request)
        arguments_str = request[len(command) + 1 :].strip()
        if command in self.commands:
            try:
                self.commands[command]["callback"](command, arguments, arguments_str)
                return True
            except Exception as error:
                self.reporting.error(f"Command failed: {error}")
                return False
        else:
            self.reporting.user_error("Unknown command")
            return False

    def _handle_request_chat(self, request: str) -> bool:
        """Handle chat with the current chain."""
        user_request: str | list[dict[str, Any]] | None = request
        if lair.config.get("chat.attachments_enabled"):
            attachment_regex = cast(str, lair.config.get("chat.attachment_syntax_regex"))
            attachments = re.findall(attachment_regex, request)
            content_parts, messages = lair.util.get_attachments_content(attachments)

            # Remove the attachments from the user's message
            user_request = cast(str, re.sub(attachment_regex, "", request))
            if user_request.strip() == "":
                user_request = None

            if len(content_parts) > 0:
                user_request = [
                    *([{"type": "text", "text": user_request}] if user_request else []),
                    *content_parts,
                ]
            if user_request:
                self.chat_session.history.add_message("user", user_request)

            self.chat_session.history.add_messages(messages)

        response = self.chat_session.chat()
        self.reporting.llm_output(response)
        return True

    def _handle_request(self, request: str) -> bool:
        """Process a request by dispatching to commands or chat handling.

        Returns:
            bool: ``True`` if the request was handled successfully.

        """
        try:
            if request == "":
                return False
            elif request.startswith("/"):
                return self._handle_request_command(request)
            else:
                return self._handle_request_chat(request)
        except Exception as error:
            self.reporting.error(f"Chat failed: {error}")
            return False

    def startup_message(self) -> None:
        """Print the initial welcome message."""
        self.reporting.system_message("Welcome to the LAIR")

    def _flash(self, message: str, duration: float = 1.2) -> None:
        """Flash a message on the bottom toolbar.

        Args:
            message: Prompt Toolkit HTML message to display.
            duration: Amount of time to show the message for.

        """
        columns = shutil.get_terminal_size().columns

        message = message[:columns]  # Truncate long messages
        message += " " * (columns - len(message))  # Pad with spaces

        self.flash_message = message
        self.flash_message_expiration = time.time() + duration

    def _prompt_handler_system_message(self, message: str) -> None:
        """Display a system message from within the prompt."""
        prompt_toolkit.application.run_in_terminal(lambda: self.reporting.system_message(message))

    def _get_embedded_response(self, message: str, position: int) -> str | None:
        """Extract an embedded response from the message."""
        regex = cast(str, lair.config.get("chat.embedded_syntax_regex"))
        matches = re.findall(regex, message, re.DOTALL)

        if abs(position) > len(matches) - 1:
            return None

        for section in matches[position]:
            if section.endswith("\n"):  # Chomp the extra newline off of strings
                section = section[:-1]

            if section:  # Return the first non-empty capture
                return section

        return None

    def _template_keys(self) -> dict[str, str | int | bool]:
        """Return template variables used in prompts and toolbars."""
        return {
            "flags": self._generate_toolbar_template_flags(),
            "mode": lair.config.active_mode,
            "model": cast(str, lair.config.get("model.name")),
            "session_id": self.chat_session.session_id,
            "session_alias": self.chat_session.session_alias or "",
        }

    def _generate_prompt(self) -> prompt_toolkit.formatted_text.HTML:
        """Generate the formatted prompt string."""
        return prompt_toolkit.formatted_text.HTML(
            cast(str, lair.config.active["chat.prompt_template"]).format(
                **self._template_keys(),
            )
        )

    def _generate_toolbar_template_flags(self) -> str:
        """Return the toolbar flag string based on configuration."""

        def flag(character: str, parameter: str) -> str:
            if lair.config.active[parameter]:
                return f"<flag.on>{character.upper()}</flag.on>"
            else:
                return f"<flag.off>{character.lower()}</flag.off>"

        return (
            flag("l", "chat.multiline_input")
            + flag("m", "style.render_markdown")
            + flag("t", "tools.enabled")
            + flag("v", "chat.verbose")
            + flag("w", "style.word_wrap")
        )

    def _generate_toolbar(self) -> prompt_toolkit.formatted_text.HTML | str:
        """Generate the bottom toolbar markup."""
        if not lair.config.active["chat.enable_toolbar"]:
            padding = " " * shutil.get_terminal_size().columns
            return prompt_toolkit.formatted_text.HTML(f"<bottom-toolbar.off>{padding}</bottom-toolbar.off>")

        if time.time() < self.flash_message_expiration:
            return prompt_toolkit.formatted_text.HTML(
                f"<bottom-toolbar.flash>{self.flash_message}</bottom-toolbar.flash>"
            )

        try:
            template = cast(str, lair.config.active["chat.toolbar_template"]).format(
                **self._template_keys(),
            )

            return prompt_toolkit.formatted_text.HTML(template)
        except Exception as error:
            logger.error(f"Unable to render toolbar: {error}")
            logger.error("Disabling toolbar")
            lair.config.active["chat.enable_toolbar"] = False
            return ""

    def _prompt(self) -> None:
        """Read a request from the user and handle it."""
        if self.prompt_session is None:
            raise RuntimeError("Prompt session not initialized")
        self.is_reading_prompt = True

        request = self.prompt_session.prompt(
            self._generate_prompt,
            multiline=prompt_toolkit.filters.Condition(lambda: bool(lair.config.active["chat.multiline_input"])),
            style=prompt_toolkit.styles.Style.from_dict(
                {
                    "bottom-toolbar": str(lair.config.active["chat.toolbar_style"]),
                    "bottom-toolbar.text": str(lair.config.active["chat.toolbar_text_style"]),
                    "bottom-toolbar.flash": str(lair.config.active["chat.toolbar_flash_style"]),
                    "bottom-toolbar.off": "fg:black bg:white",
                    "flag.off": str(lair.config.active["chat.flag_off_style"]),
                    "flag.on": str(lair.config.active["chat.flag_on_style"]),
                }
            ),
        ).strip()

        self.is_reading_prompt = False
        if self._handle_request(request):
            self.session_manager.refresh_from_chat_session(self.chat_session)

    def start(self) -> None:
        """Start the interactive chat loop."""
        self.startup_message()

        while True:
            try:
                self._prompt()
            except KeyboardInterrupt:
                if not self.is_reading_prompt:
                    self.reporting.error("Interrupt received")
            except EOFError:
                sys.exit(0)
