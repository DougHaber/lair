import os

import lair
from lair.logging import logger


class ChatInterfaceCommands():

    def _get_commands(self):
        return {
            '/clear': {
                'callback': lambda c, a: self.command_clear(c, a),
                'description': 'Clear the conversation history'
            },
            '/debug': {
                'callback': lambda c, a: self.command_debug(c, a),
                'description': 'Toggle debugging'
            },
            '/help': {
                'callback': lambda c, a: self.command_help(c, a),
                'description': 'Show available commands and shortcuts'
            },
            '/history': {
                'callback': lambda c, a: self.command_history(c, a),
                'description': 'Show current conversation'
            },
            '/last-prompt': {
                'callback': lambda c, a: self.command_last_prompt(c, a),
                'description': 'Display the most recently used prompt'
            },
            '/last-response': {
                'callback': lambda c, a: self.command_last_response(c, a),
                'description': 'Display the most recently seen response'
            },
            '/load': {
                'callback': lambda c, a: self.command_load(c, a),
                'description': 'Load a session from a file  (usage: /load [filename?], default filename is chat_session.json)',
            },
            '/mode': {
                'callback': lambda c, a: self.command_mode(c, a),
                'description': 'Show or select a mode  (usage: /mode [name?])'
            },
            '/model': {
                'callback': lambda c, a: self.command_model(c, a),
                'description': 'Show or set a model  (usage: /model [name?])'
            },
            '/prompt': {
                'callback': lambda c, a: self.command_prompt(c, a),
                'description': 'Show or set the system prompt  (usage: /prompt [prompt?])'
            },
            '/reload-settings': {
                'callback': lambda c, a: self.command_reload_settings(c, a),
                'description': 'Reload settings from disk  (resets everything, except current mode)'
            },
            '/save': {
                'callback': lambda c, a: self.command_save(c, a),
                'description': 'Save the current session to a file  (usage: /save [filename?], default filename is chat_session.json)',
            },
            '/set': {
                'callback': lambda c, a: self.command_set(c, a),
                'description': 'Show configuration or set a configuration value for the current mode  (usage: /set ([key?] [value?])?'
            },
        }

    def command_clear(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /clear takes no arguments")
        else:
            self.chat_session.history.clear()

    def command_debug(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /debug takes no arguments")
        else:
            if lair.util.get_log_level() == 'DEBUG':
                logger.setLevel('INFO')
                self.reporting.system_message('Debugging disabled')
            else:
                logger.setLevel('DEBUG')
                self.reporting.system_message('Debugging enabled')

    def command_help(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /help takes no arguments")
        else:
            rows = []
            for command, details in sorted(self.commands.items()):
                rows.append([command, details['description']])

            self.reporting.table_system(rows)

            rows = []
            for shortcut, description in sorted(self._get_shortcut_details().items()):
                rows.append([shortcut, description])

            self.reporting.table_system(rows)

    def command_history(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /history takes no arguments")
        else:
            messages = self.chat_session.history.get_messages()

            if not messages:
                return
            else:
                for message in messages:
                    self.reporting.message(message)

    def command_last_prompt(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /last-prompt takes no arguments")
        else:
            last_prompt = self.chat_session.last_prompt
            if last_prompt:
                self.reporting.print_rich(self.reporting.plain(last_prompt))
            else:
                logger.warn("No last prompt found")

    def command_last_response(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /last-response takes no arguments")
        else:
            if self.chat_session.last_response:
                self.reporting.llm_output(self.chat_session.last_response)
            else:
                logger.warn("No last response found")

    def command_load(self, command, arguments):
        filename = 'chat_session.json' if len(arguments) == 0 else os.path.expanduser(arguments[0])
        self.chat_session.load(filename)
        self.reporting.system_message(f"Session loaded from {filename}")

    def command_mode(self, command, arguments):
        if len(arguments) == 0:  # Show modes
            rows = []
            for mode in filter(lambda m: not m.startswith('_'), lair.config.modes.keys()):
                current = '* ' if mode == lair.config.active_mode else '  '
                rows.append([current + mode, lair.config.modes[mode].get('_description', '')])

            self.reporting.table_system(rows)
        elif len(arguments) == 1:  # Set mode
            lair.config.change_mode(arguments[0])
            old_session = self.chat_session
            self.chat_session = lair.sessions.get_session(
                lair.config.active.get('session.type'),
                history=old_session.history)
        else:
            self.reporting.user_error("ERROR: Invalid arguments: Usage: /mode [name?]")

    def command_model(self, command, arguments):
        if len(arguments) > 1:
            self.reporting.user_error("ERROR: Invalid arguments: Usage /model [name?]")
        elif len(arguments) == 0:
            active_config = lair.config.active
            self.reporting.table_system([
                ['Name', self.chat_session.fixed_model_name or active_config.get('model.name')],
                ['Temperature', str(active_config.get('model.temperature'))],
                ['OpenAI API Base', str(active_config.get('openai.api_base'))],
                ['Max Tokens', str(active_config.get('model.max_tokens'))],
            ])
        elif len(arguments) == 1:
            lair.config.set('model.name', arguments[0])

    def command_prompt(self, command, arguments):
        if len(arguments) == 0:
            self.reporting.system_message(self.chat_session.system_prompt)
        else:
            self.chat_session.set_system_prompt(' '.join(arguments))

    def command_reload_settings(self, command, arguments):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: USAGE: /reload_settings")
        else:
            lair.config.reload()
            self.reporting.system_message('Settings reloaded from disk')

    def command_save(self, command, arguments):
        filename = 'chat_session.json' if len(arguments) == 0 else os.path.expanduser(arguments[0])
        self.chat_session.save(filename)
        self.reporting.system_message(f"Session written to {filename}")

    def command_set(self, command, arguments):
        if len(arguments) == 0:
            self.reporting.system_message(f"Current mode: {lair.config.active_mode}")
            rows = []
            for key, value in sorted(lair.config.active.items()):
                if not key.startswith('_'):
                    rows.append([key, str(value)])

            self.reporting.table_system(rows)
        elif not (len(arguments) == 1 or len(arguments) == 2):
            self.reporting.user_error("ERROR: USAGE: /set ([key?] [value?])?")
        else:
            key = arguments[0]
            value = '' if len(arguments) == 1 else arguments[1]
            if key not in lair.config.active:
                self.reporting.user_error("ERROR Unknown key: %s" % key)
            else:
                lair.config.set(key, value)
