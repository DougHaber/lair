import os
import re
import shutil
import sys
import time

import lair
import lair.sessions
from lair.cli.chat_interface_commands import ChatInterfaceCommands
from lair.cli.chat_interface_completer import ChatInterfaceCompleter
from lair.logging import logger  # noqa

import prompt_toolkit
import prompt_toolkit.filters
import prompt_toolkit.formatted_text
import prompt_toolkit.history
import prompt_toolkit.key_binding
import prompt_toolkit.keys
import prompt_toolkit.styles


class ChatInterface(ChatInterfaceCommands):

    def __init__(self):
        self.chat_session = lair.sessions.get_session(lair.config.get('session.type'),
                                                      enable_chat_output=True)
        self.commands = self._get_commands()
        self.reporting = lair.reporting.Reporting()
        self._models = None  # Cached list of models for the session

        self.flash_message = None
        self.flash_message_expiration = 0
        self.is_reading_prompt = False

        self.history = None
        self.prompt_session = None
        self._on_config_update()  # Trigger the initial state updates

        lair.events.subscribe('config.update', lambda d: self._on_config_update())
        lair.events.fire('chat.init', self)

    def _on_config_update(self):
        self._init_history()
        self._init_prompt_session()
        self._models = self.chat_session.list_models(ignore_errors=True)

    def _init_history(self):
        history_file = lair.config.get('chat.history_file')
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

    def _get_shortcut_details(self):
        return {  # shortcut ->  description
            'ESC-B': 'Toggle bottom toolbar',
            'ESC-L': 'Toggle multi-line input',
            'ESC-M': 'Toggle markdown rendering',
            'ESC-T': 'Toggle tools',
            'ESC-V': 'Toggle verbose output',
            'ESC-W': 'Toggle word wrapping',
        }

    def _get_keybindings(self):
        key_bindings = prompt_toolkit.key_binding.KeyBindings()

        @key_bindings.add("enter", filter=prompt_toolkit.filters.completion_is_selected)
        def enter_key_on_selected_completion(event):
            current_buffer = event.app.current_buffer
            current_buffer.insert_text(' ')
            current_buffer.cancel_completion()

        @key_bindings.add('escape', 'b')
        def toggle_toolbar(event):
            if lair.config.active['chat.enable_toolbar']:
                lair.config.set('chat.enable_toolbar', 'false')
                self._flash("Disabling bottom toolbar")
            else:
                lair.config.set('chat.enable_toolbar', 'true')
                self._flash("Enabling bottom toolbar")

        @key_bindings.add('escape', 'l')
        def toggle_multiline(event):
            if lair.config.active['chat.multiline_input']:
                lair.config.set('chat.multiline_input', 'false')
                self._flash("Disabling multi-line input")
            else:
                lair.config.set('chat.multiline_input', 'true')
                self._flash("Enabling multi-line input")

        @key_bindings.add('escape', 'm')
        def toggle_markdown(event):
            if lair.config.active['style.render_markdown']:
                lair.config.set('style.render_markdown', 'false')
                self._flash("Disabling markdown rendering")
            else:
                lair.config.set('style.render_markdown', 'true')
                self._flash("Enabling markdown rendering")

        @key_bindings.add('escape', 't')
        def toggle_toolbar(event):
            if lair.config.active['tools.enabled']:
                lair.config.set('tools.enabled', 'false')
                self._flash("Disabling tools")
            else:
                lair.config.set('tools.enabled', 'true')
                self._flash("Enabling tools")

        @key_bindings.add('escape', 'v')
        def toggle_verbose(event):
            if lair.config.active['chat.verbose']:
                lair.config.set('chat.verbose', 'false')
                self._flash("Disabling verbose output")
            else:
                lair.config.set('chat.verbose', 'true')
                self._flash("Enabling verbose output")

        @key_bindings.add('escape', 'w')
        def toggle_word_wrap(event):
            if lair.config.active['style.word_wrap']:
                lair.config.set('style.word_wrap', 'false')
                self._flash("Disabling word wrapping")
            else:
                lair.config.set('style.word_wrap', 'true')
                self._flash("Enabling word wrapping")

        return key_bindings

    def _handle_request_command(self, request):
        """Handle slash commands."""
        command, *arguments = re.split(r'\s+', request)
        arguments_str = request[len(command) + 1:].strip()
        if command in self.commands:
            try:
                self.commands[command]['callback'](command, arguments, arguments_str)
            except Exception as error:
                self.reporting.error("Command failed: %s" % error)
        else:
            self.reporting.user_error("Unknown command")

    def _handle_request_chat(self, request):
        """Handle chat with the current chain."""
        if lair.config.get('chat.attachments_enabled'):
            attachment_regex = lair.config.get('chat.attachment_syntax_regex')
            attachments = re.findall(attachment_regex, request)
            content_parts, messages = lair.util.get_attachments_content(attachments)

            # Remove the attachments from the user's message
            request = re.sub(attachment_regex, '', request)
            if request.strip() == '':
                request = None

            if len(content_parts) > 0:
                request = [
                    *([{'type': 'text', 'text': request}] if request else []),
                    *content_parts,
                ]
            if request:
                self.chat_session.history.add_message('user', request)

            self.chat_session.history.add_messages(messages)

        response = self.chat_session.chat()
        self.reporting.llm_output(response)

    def _handle_request(self, request):
        try:
            if request == '':
                return
            elif request.startswith('/'):
                self._handle_request_command(request)
            else:
                self._handle_request_chat(request)
        except Exception as error:
            self.reporting.error("Chat failed: %s" % error)

    def startup_message(self):
        self.reporting.system_message('Welcome to the LAIR')

    def _flash(self, message, duration=1.2):
        """Flash a message on the bottom toolbar.

        message: Prompt Toolkit HTML message to display
        duration: Amount of time to show the mesage for (default 1.2)
        """
        columns = shutil.get_terminal_size().columns

        message = message[:columns]  # Truncate long messages
        message += ' ' * (columns - len(message))  # Pad with spaces

        self.flash_message = message
        self.flash_message_expiration = time.time() + duration

    def _get_embedded_response(self, message, position):
        regex = lair.config.get('chat.embedded_syntax_regex')
        matches = re.findall(regex, message, re.DOTALL)

        if abs(position) > len(matches) - 1:
            return None

        for section in matches[position]:
            if section.endswith('\n'):  # Chomp the extra newline off of strings
                section = section[:-1]

            if section:  # Return the first non-empty capture
                return section

        return None

    def _template_keys(self):
        return {
            'flags': self._generate_toolbar_template_flags(),
            'mode': lair.config.active_mode,
            'model': self.chat_session.model_name,
        }

    def _generate_prompt(self):
        return prompt_toolkit.formatted_text.HTML(
            lair.config.active['chat.prompt_template'].format(
                **self._template_keys(),
            ))

    def _generate_toolbar_template_flags(self):
        def flag(character, parameter):
            if lair.config.active[parameter]:
                return '<flag.on>%s</flag.on>' % character.upper()
            else:
                return '<flag.off>%s</flag.off>' % character.lower()

        return \
            flag('l', 'chat.multiline_input') + \
            flag('m', 'style.render_markdown') + \
            flag('t', 'tools.enabled') + \
            flag('v', 'chat.verbose') + \
            flag('w', 'style.word_wrap')

    def _generate_toolbar(self):
        if not lair.config.active['chat.enable_toolbar']:
            padding = ' ' * shutil.get_terminal_size().columns
            return prompt_toolkit.formatted_text.HTML(
                f'<bottom-toolbar.off>{padding}</bottom-toolbar.off>')

        if time.time() < self.flash_message_expiration:
            return prompt_toolkit.formatted_text.HTML(
                '<bottom-toolbar.flash>%s</bottom-toolbar.flash>' % self.flash_message)

        try:
            template = lair.config.active['chat.toolbar_template'].format(
                **self._template_keys(),
            )

            return prompt_toolkit.formatted_text.HTML(template)
        except Exception as error:
            logger.error("Unable to render toolbar: %s" % error)
            logger.error("Disabling toolbar")
            lair.config.active['chat.enable_toolbar'] = False
            return ''

    def _prompt(self):
        self.is_reading_prompt = True

        request = self.prompt_session.prompt(
            self._generate_prompt(),
            multiline=prompt_toolkit.filters.Condition(lambda: lair.config.active['chat.multiline_input']),
            style=prompt_toolkit.styles.Style.from_dict({
                'bottom-toolbar': lair.config.active['chat.toolbar_style'],
                'bottom-toolbar.text': lair.config.active['chat.toolbar_text_style'],
                'bottom-toolbar.flash': lair.config.active['chat.toolbar_flash_style'],
                'bottom-toolbar.off': 'fg:black bg:white',
                'flag.off': lair.config.active['chat.flag_off_style'],
                'flag.on': lair.config.active['chat.flag_on_style'],
            }))
        self.is_reading_prompt = False
        self._handle_request(request.strip())

    def start(self):
        self.startup_message()

        while True:
            try:
                self._prompt()
            except KeyboardInterrupt:
                if not self.is_reading_prompt:
                    self.reporting.error('Interrupt received')
            except EOFError:
                sys.exit(0)
