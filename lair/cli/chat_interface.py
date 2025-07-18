import os
import re
import shutil
import sys
import time

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
    def __init__(self, *, starting_session_id_or_alias=None, create_session_if_missing=False):
        self.chat_session = lair.sessions.get_chat_session(lair.config.get("session.type"))
        self.session_manager = lair.sessions.SessionManager()
        self._init_starting_session(starting_session_id_or_alias, create_session_if_missing)

        self.last_used_session_id = None

        self.commands = self._get_commands()
        self.reporting = lair.reporting.Reporting()
        self._models = None  # Cached list of models

        self.flash_message = None
        self.flash_message_expiration = 0
        self.is_reading_prompt = False

        self.history = None
        self.sub_prompt_history = {  # Prompt history for each sub-prompt type
            "session_set_alias": prompt_toolkit.history.InMemoryHistory(),
            "session_set_title": prompt_toolkit.history.InMemoryHistory(),
            "session_switch": prompt_toolkit.history.InMemoryHistory(),
        }

        self.prompt_session = None
        self._on_config_update()  # Trigger the initial state updates

        lair.events.subscribe("config.update", lambda d: self._on_config_update(), instance=self)
        lair.events.fire("chat.init", self)

    def _on_config_update(self):
        self._init_history()
        self._init_prompt_session()
        self._rebuild_chat_session()
        self._models = self.chat_session.list_models(ignore_errors=True)

    def _init_history(self):
        history_file = lair.config.get("chat.history_file")
        if history_file:
            self.history = prompt_toolkit.history.FileHistory(os.path.expanduser(history_file))
        else:
            self.history = None

    def _init_prompt_session(self):
        self.prompt_session = prompt_toolkit.PromptSession(
            bottom_toolbar=lambda: self._generate_toolbar(),
            completer=ChatInterfaceCompleter(self),
            enable_open_in_editor=True,
            enable_suspend=True,
            history=self.history,
            key_bindings=self._get_keybindings(),
            refresh_interval=0.2,
        )

    def _init_starting_session(self, id_or_alias, create_session_if_missing):
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

    def _get_shortcut_details(self):
        def format_key(name):
            return lair.config.get(f"chat.keys.{name}").replace("escape ", "ESC-").replace("c-", "C-")

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

    def _get_keybindings(self):
        key_bindings = prompt_toolkit.key_binding.KeyBindings()

        def get_key(name):
            return lair.config.get(f"chat.keys.{name}").split(" ")

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

    def _enter_key_on_selected_completion(self, event):
        current_buffer = event.app.current_buffer
        current_buffer.insert_text(" ")
        current_buffer.cancel_completion()

    def toggle_debug(self, event):
        if lair.util.is_debug_enabled():
            logger.setLevel("INFO")
            self._prompt_handler_system_message("Debugging disabled")
        else:
            logger.setLevel("DEBUG")
            self._prompt_handler_system_message("Debugging enabled")

    def toggle_toolbar(self, event):
        if lair.config.active["chat.enable_toolbar"]:
            lair.config.set("chat.enable_toolbar", "false")
            self._prompt_handler_system_message("Bottom toolbar disabled")
        else:
            lair.config.set("chat.enable_toolbar", "true")
            self._prompt_handler_system_message("Bottom toolbar enabled")

    def toggle_multiline_input(self, event):
        if lair.config.active["chat.multiline_input"]:
            lair.config.set("chat.multiline_input", "false")
            self._prompt_handler_system_message("Multi-line input disabled")
        else:
            lair.config.set("chat.multiline_input", "true")
            self._prompt_handler_system_message("Multi-line input enabled")

    def toggle_markdown(self, event):
        if lair.config.active["style.render_markdown"]:
            lair.config.set("style.render_markdown", "false")
            self._prompt_handler_system_message("Markdown rendering disabled")
        else:
            lair.config.set("style.render_markdown", "true")
            self._prompt_handler_system_message("Markdown rendering enabled")

    def toggle_tools(self, event):
        if lair.config.active["tools.enabled"]:
            lair.config.set("tools.enabled", "false")
            self._prompt_handler_system_message("Tools disabled")
        else:
            lair.config.set("tools.enabled", "true")
            self._prompt_handler_system_message("Tools enabled")

    def toggle_verbose(self, event):
        if lair.config.active["chat.verbose"]:
            lair.config.set("chat.verbose", "false")
            self._prompt_handler_system_message("Verbose output disabled")
        else:
            lair.config.set("chat.verbose", "true")
            self._prompt_handler_system_message("Verbose output enabled")

    def toggle_word_wrap(self, event):
        if lair.config.active["style.word_wrap"]:
            lair.config.set("style.word_wrap", "false")
            self._prompt_handler_system_message("Word wrap disabled")
        else:
            lair.config.set("style.word_wrap", "true")
            self._prompt_handler_system_message("Word wrap enabled")

    def session_new(self, event):
        self._new_chat_session()
        self._prompt_handler_system_message("New session created")

    def session_next(self, event):
        session_id = self.session_manager.get_next_session_id(self.chat_session.session_id)
        if session_id is not None:
            self._switch_to_session(session_id)

    def session_clear(self, event):
        self.chat_session.new_session(preserve_alias=True, preserve_id=True)
        self.session_manager.refresh_from_chat_session(self.chat_session)
        self._prompt_handler_system_message("Conversation history cleared")

    def session_previous(self, event):
        session_id = self.session_manager.get_previous_session_id(self.chat_session.session_id)
        if session_id is not None:
            self._switch_to_session(session_id)

    def session_set_alias(self, event):
        prompt_toolkit.application.run_in_terminal(self._handle_session_set_alias)

    def session_set_title(self, event):
        prompt_toolkit.application.run_in_terminal(self._handle_session_set_title)

    def session_status(self, event):
        prompt_toolkit.application.run_in_terminal(self.print_sessions_report)

    def session_switch(self, event):
        prompt_toolkit.application.run_in_terminal(self._handle_session_switch)

    def show_help(self, event):
        prompt_toolkit.application.run_in_terminal(self.print_help)

    def show_history(self, event):
        prompt_toolkit.application.run_in_terminal(self.print_history)

    def show_recent_history(self, event):
        prompt_toolkit.application.run_in_terminal(lambda: self.print_history(num_messages=2))

    def list_models(self, event):
        prompt_toolkit.application.run_in_terminal(lambda: self.print_models_report(update_cache=True))

    def list_tools(self, event):
        prompt_toolkit.application.run_in_terminal(self.print_tools_report)

    def _f_key(self, event):
        session_id = int(event.key_sequence[0].key[1:])
        prompt_toolkit.application.run_in_terminal(lambda: self._switch_to_session(session_id, raise_exceptions=False))

    def _new_chat_session(self):
        self.chat_session.new_session()
        lair.config.change_mode(lair.config.active_mode)  # Reset the config to the default mode config
        self.session_manager.add_from_chat_session(self.chat_session)

    def _rebuild_chat_session(self):
        """
        Regenerate the current chat session
        This is necessary, since changes to session.type can alter the chat session class used
        """
        old_chat_session = self.chat_session
        self.chat_session = lair.sessions.get_chat_session(lair.config.get("session.type"))
        self.chat_session.import_state(old_chat_session)

    def _switch_to_session(self, id_or_alias, raise_exceptions=True):
        """
        Switch to a new session.

        Arguments:
          id_or_alias: Either a session ID or session alias to switch to.
          raise_exceptions: When True, an unknown session ID raises an exception.
                            When False, it logs an error instead.

        Raises:
          lair.sessions.UnknownSessionException: If the session ID is unknown
                                                 and `raise_exceptions` is True.
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

    def _get_default_switch_session_id(self):
        """
        Return a session id to default to for quick-switch
        This will be either the last used session id or the next session_id
        """
        if self.last_used_session_id is not None and self.session_manager.get_session_id(
            self.last_used_session_id, raise_exception=False
        ):
            # If the last_used_session_id is still valid, return that
            return self.last_used_session_id
        else:
            return self.session_manager.get_next_session_id(self.chat_session.session_id)

    def _handle_session_switch(self):
        default_session_id = self._get_default_switch_session_id()

        key_bindings = prompt_toolkit.key_binding.KeyBindings()

        @key_bindings.add("tab")
        def show_sessions(event):
            prompt_toolkit.application.run_in_terminal(lambda: self.print_sessions_report())

        try:
            id_or_alias = prompt_toolkit.prompt(
                f"Switch to session (default {default_session_id}): ",
                history=self.sub_prompt_history["session_switch"],
                in_thread=True,
                key_bindings=key_bindings,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return

        id_or_alias = id_or_alias or default_session_id

        try:
            self._switch_to_session(id_or_alias)
        except lair.sessions.UnknownSessionException:
            self.reporting.user_error(f"ERROR: Unknown session: {id_or_alias}")

    def _handle_session_set_alias(self):
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

    def _handle_session_set_title(self):
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

    def _handle_request_command(self, request):
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

    def _handle_request_chat(self, request):
        """Handle chat with the current chain."""
        if lair.config.get("chat.attachments_enabled"):
            attachment_regex = lair.config.get("chat.attachment_syntax_regex")
            attachments = re.findall(attachment_regex, request)
            content_parts, messages = lair.util.get_attachments_content(attachments)

            # Remove the attachments from the user's message
            request = re.sub(attachment_regex, "", request)
            if request.strip() == "":
                request = None

            if len(content_parts) > 0:
                request = [
                    *([{"type": "text", "text": request}] if request else []),
                    *content_parts,
                ]
            if request:
                self.chat_session.history.add_message("user", request)

            self.chat_session.history.add_messages(messages)

        response = self.chat_session.chat()
        self.reporting.llm_output(response)
        return True

    def _handle_request(self, request):
        """
        Process a request, calling the necessary command or model.

        Returns:
          bool: True if a request was properly handled, otherwise False
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

    def startup_message(self):
        self.reporting.system_message("Welcome to the LAIR")

    def _flash(self, message, duration=1.2):
        """Flash a message on the bottom toolbar.

        message: Prompt Toolkit HTML message to display
        duration: Amount of time to show the mesage for (default 1.2)
        """
        columns = shutil.get_terminal_size().columns

        message = message[:columns]  # Truncate long messages
        message += " " * (columns - len(message))  # Pad with spaces

        self.flash_message = message
        self.flash_message_expiration = time.time() + duration

    def _prompt_handler_system_message(self, message):
        prompt_toolkit.application.run_in_terminal(lambda: self.reporting.system_message(message))

    def _get_embedded_response(self, message, position):
        regex = lair.config.get("chat.embedded_syntax_regex")
        matches = re.findall(regex, message, re.DOTALL)

        if abs(position) > len(matches) - 1:
            return None

        for section in matches[position]:
            if section.endswith("\n"):  # Chomp the extra newline off of strings
                section = section[:-1]

            if section:  # Return the first non-empty capture
                return section

        return None

    def _template_keys(self):
        return {
            "flags": self._generate_toolbar_template_flags(),
            "mode": lair.config.active_mode,
            "model": lair.config.get("model.name"),
            "session_id": self.chat_session.session_id,
            "session_alias": self.chat_session.session_alias or "",
        }

    def _generate_prompt(self):
        return prompt_toolkit.formatted_text.HTML(
            lair.config.active["chat.prompt_template"].format(
                **self._template_keys(),
            )
        )

    def _generate_toolbar_template_flags(self):
        def flag(character, parameter):
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

    def _generate_toolbar(self):
        if not lair.config.active["chat.enable_toolbar"]:
            padding = " " * shutil.get_terminal_size().columns
            return prompt_toolkit.formatted_text.HTML(f"<bottom-toolbar.off>{padding}</bottom-toolbar.off>")

        if time.time() < self.flash_message_expiration:
            return prompt_toolkit.formatted_text.HTML(
                f"<bottom-toolbar.flash>{self.flash_message}</bottom-toolbar.flash>"
            )

        try:
            template = lair.config.active["chat.toolbar_template"].format(
                **self._template_keys(),
            )

            return prompt_toolkit.formatted_text.HTML(template)
        except Exception as error:
            logger.error(f"Unable to render toolbar: {error}")
            logger.error("Disabling toolbar")
            lair.config.active["chat.enable_toolbar"] = False
            return ""

    def _prompt(self):
        self.is_reading_prompt = True

        request = self.prompt_session.prompt(
            self._generate_prompt,
            multiline=prompt_toolkit.filters.Condition(lambda: lair.config.active["chat.multiline_input"]),
            style=prompt_toolkit.styles.Style.from_dict(
                {
                    "bottom-toolbar": lair.config.active["chat.toolbar_style"],
                    "bottom-toolbar.text": lair.config.active["chat.toolbar_text_style"],
                    "bottom-toolbar.flash": lair.config.active["chat.toolbar_flash_style"],
                    "bottom-toolbar.off": "fg:black bg:white",
                    "flag.off": lair.config.active["chat.flag_off_style"],
                    "flag.on": lair.config.active["chat.flag_on_style"],
                }
            ),
        ).strip()

        self.is_reading_prompt = False
        if self._handle_request(request):
            self.session_manager.refresh_from_chat_session(self.chat_session)

    def start(self):
        self.startup_message()

        while True:
            try:
                self._prompt()
            except KeyboardInterrupt:
                if not self.is_reading_prompt:
                    self.reporting.error("Interrupt received")
            except EOFError:
                sys.exit(0)
