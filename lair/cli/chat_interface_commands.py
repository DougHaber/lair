import json
import os
import shlex

import lair
from lair.logging import logger
from lair.util.argparse import (
    ArgumentParserExitException,
    ArgumentParserHelpException,
    ErrorRaisingArgumentParser,
)


class ChatInterfaceCommands():

    def _get_commands(self):
        return {
            '/clear': {
                'callback': lambda command, arguments, arguments_str: self.command_clear(command, arguments, arguments_str),
                'description': 'Clear the conversation history'
            },
            '/debug': {
                'callback': lambda command, arguments, arguments_str: self.command_debug(command, arguments, arguments_str),
                'description': 'Toggle debugging'
            },
            '/extract': {
                'callback': lambda command, arguments, arguments_str: self.command_extract(command, arguments, arguments_str),
                'description': 'Display or save an embedded response  (usage: `/extract [position?] [filename?]`)'
            },
            '/help': {
                'callback': lambda command, arguments, arguments_str: self.command_help(command, arguments, arguments_str),
                'description': 'Show available commands and shortcuts'
            },
            '/history': {
                'callback': lambda command, arguments, arguments_str: self.command_history(command, arguments, arguments_str),
                'description': 'Show current conversation'
            },
            '/history-edit': {
                'callback': lambda command, arguments, arguments_str: self.command_history_edit(command, arguments, arguments_str),
                'description': 'Modify the history JSONL in an external editor'
            },
            '/history-slice': {
                'callback': lambda command, arguments, arguments_str: self.command_history_slice(command, arguments, arguments_str),
                'description': 'Modify the history with a Python style slice string  (usage: /history-slice [slice], Slice format: start:stop:step)'
            },
            '/last-prompt': {
                'callback': lambda command, arguments, arguments_str: self.command_last_prompt(command, arguments, arguments_str),
                'description': 'Display the most recently used prompt'
            },
            '/last-response': {
                'callback': lambda command, arguments, arguments_str: self.command_last_response(command, arguments, arguments_str),
                'description': 'Display or save the most recently seen response  (usage: /last-response [filename?])'
            },
            '/list-models': {
                'callback': lambda command, arguments, arguments_str: self.command_list_models(command, arguments, arguments_str),
                'description': 'Display a list of available models for the current session'
            },
            '/list-settings': {
                'callback': lambda command, arguments, arguments_str: self.command_list_settings(command, arguments, arguments_str),
                'description': 'Show and search settings  (for usage, run /list-settings --help)'
            },
            '/list-tools': {
                'callback': lambda command, arguments, arguments_str: self.command_list_tools(command, arguments, arguments_str),
                'description': 'Show tools and their status'
            },
            '/load': {
                'callback': lambda command, arguments, arguments_str: self.command_load(command, arguments, arguments_str),
                'description': 'Load a session from a file  (usage: /load [filename?], default filename is chat_session.json)',
            },
            '/messages': {
                'callback': lambda command, arguments, arguments_str: self.command_messages(command, arguments, arguments_str),
                'description': 'Display or save the JSON message history as JSONL (usage: /messages [filename?])'
            },
            '/mode': {
                'callback': lambda command, arguments, arguments_str: self.command_mode(command, arguments, arguments_str),
                'description': 'Show or select a mode  (usage: /mode [name?])'
            },
            '/model': {
                'callback': lambda command, arguments, arguments_str: self.command_model(command, arguments, arguments_str),
                'description': 'Show or set a model  (usage: /model [name?])'
            },
            '/prompt': {
                'callback': lambda command, arguments, arguments_str: self.command_prompt(command, arguments, arguments_str),
                'description': 'Show or set the system prompt  (usage: /prompt [prompt?])'
            },
            '/reload-settings': {
                'callback': lambda command, arguments, arguments_str: self.command_reload_settings(command, arguments, arguments_str),
                'description': 'Reload settings from disk  (resets everything, except current mode)'
            },
            '/save': {
                'callback': lambda command, arguments, arguments_str: self.command_save(command, arguments, arguments_str),
                'description': 'Save the current session to a file  (usage: /save [filename?], default filename is chat_session.json)',
            },
            '/session': {
                'callback': lambda command, arguments, arguments_str: self.command_session(command, arguments, arguments_str),
                'description': 'List or switch sessions  (usage: /session [session_id|alias?])'
            },
            '/session-alias': {
                'callback': lambda command, arguments, arguments_str: self.command_session_alias(command, arguments, arguments_str),
                'description': 'Set or remove a session alias  (usage: /session-alias [session_id|alias] [new_alias?])'
            },
            '/session-delete': {
                'callback': lambda command, arguments, arguments_str: self.command_session_delete(command, arguments, arguments_str),
                'description': 'Delete session(s)  (usage: /session-delete [session_id|alias|all]...)'
            },
            '/session-new': {
                'callback': lambda command, arguments, arguments_str: self.command_session_new(command, arguments, arguments_str),
                'description': 'Create a new session'
            },
            '/session-title': {
                'callback': lambda command, arguments, arguments_str: self.command_session_title(command, arguments, arguments_str),
                'description': 'Set or remove a session title  (usage: /session-title [session_id|alias] [new_title?])'
            },
            '/set': {
                'callback': lambda command, arguments, arguments_str: self.command_set(command, arguments, arguments_str),
                'description': 'Show configuration or set a configuration value for the current mode  (usage: /set ([key?] [value?])'
            },
        }

    def register_command(self, command, callback, description):
        # Other modules can subscribe to chat.init() and then call
        # this function to register their own sub-commands.
        if command in self.commands:
            raise Exception(f"Failed to register chat command '{command}': Already registered")

        self.commands[command] = {
            'callback': callback,
            'description': description,
        }

    def command_clear(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /clear takes no arguments")
        else:
            self.chat_session.history.clear()
            self.chat_session.session_title = None

    def command_debug(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /debug takes no arguments")
        else:
            if lair.util.is_debug_enabled():
                logger.setLevel('INFO')
                self.reporting.system_message('Debugging disabled')
            else:
                logger.setLevel('DEBUG')
                self.reporting.system_message('Debugging enabled')

    def command_extract(self, command, arguments, arguments_str):
        if len(arguments) > 2:
            self.reporting.user_error("ERROR: usage: /extract [position?] [filename?]")
        else:
            position = arguments[0] if len(arguments) >= 1 else 0
            filename = arguments[1] if len(arguments) >= 2 else None

            if not isinstance(lair.util.safe_int(position), int):
                logger.error("Position must be an integer")
                return
            else:
                position = int(position)

            if self.chat_session.last_response:
                response = self._get_embedded_response(self.chat_session.last_response, position)
                if response:
                    if filename is not None:
                        lair.util.save_file(filename, response + '\n')
                        self.reporting.system_message(f'Section saved  ({len(response)} bytes)')
                    else:
                        print(response)
                else:
                    logger.error("Extract failed: No matching section found")
            else:
                logger.error("Extract failed: Last response is not set")

    def command_help(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /help takes no arguments")
        else:
            self.print_help()

    def command_history(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /history takes no arguments")
        else:
            self.print_history()

    def command_history_edit(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /history-edit takes no arguments")
        else:
            history = self.chat_session.history
            jsonl_str = history.get_messages_as_jsonl_string()
            edited_jsonl_str = lair.util.edit_content_in_editor(jsonl_str, '.json')

            if edited_jsonl_str is not None:
                try:
                    if not edited_jsonl_str.strip():
                        new_messages = []
                    else:
                        new_messages = lair.util.decode_jsonl(edited_jsonl_str)
                except Exception as error:
                    logger.error(f"Failed to decode edited history JSONL: {error}")
                    return

                history.set_history(new_messages)
                self.reporting.system_message(f"History updated  ({history.num_messages()} messages)")
            else:
                self.reporting.user_error("History was not modified.")

    def command_history_slice(self, command, arguments, arguments_str):
        if len(arguments) != 1:
            self.reporting.user_error("ERROR: Invalid arguments: Usage: /history-slice [slice]")
        else:
            history = self.chat_session.history
            original_num_messages = history.num_messages()
            messages = lair.util.slice_from_str(history.get_messages(), arguments[0])
            self.chat_session.history.set_history(messages)
            new_num_messages = history.num_messages()

            self.reporting.system_message(f"History updated  (Selected {new_num_messages} messages out of {original_num_messages})")

    def command_last_prompt(self, command, arguments, arguments_str):
        if len(arguments) > 1:
            self.reporting.user_error("ERROR: Invalid arguments: Usage: /last-prompt [filename?]")
        else:
            last_prompt = self.chat_session.last_prompt
            if last_prompt:
                filename = arguments[0] if len(arguments) == 1 else None
                if filename is not None:
                    lair.util.save_file(filename, last_prompt + '\n')
                    self.reporting.system_message(f'Last prompt saved  ({len(last_prompt)} bytes)')
                else:
                    self.reporting.print_rich(self.reporting.style(last_prompt))
            else:
                logger.warn("No last prompt found")

    def command_last_response(self, command, arguments, arguments_str):
        if len(arguments) > 1:
            self.reporting.user_error("ERROR: Invalid arguments: Usage: /last-response [filename?]")
        else:
            last_response = self.chat_session.last_response
            if last_response:
                filename = arguments[0] if len(arguments) == 1 else None
                if filename is not None:
                    lair.util.save_file(filename, last_response + '\n')
                    self.reporting.system_message(f'Last response saved  ({len(last_response)} bytes)')
                else:
                    self.reporting.llm_output(last_response)
            else:
                logger.warn("No last response found")

    def command_list_models(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /list-models takes no arguments")
        else:
            self.print_models_report(update_cache=True)

    def command_list_settings(self, command, arguments, arguments_str):
        parser = ErrorRaisingArgumentParser(prog='/list-settings')
        parser.add_argument('-b', '--baseline', type=str,
                            help='Baseline mode to compare against (default is the built in default configuration)')
        parser.add_argument('-d', '--show-diff', action='store_true',
                            help='Only show settings which do not match the baselines')
        parser.add_argument('search', nargs='?', default=None,
                            help='Regular expression to filter settings by')

        try:
            new_arguments = parser.parse_args(shlex.split(arguments_str))
        except ArgumentParserHelpException as error:  # Display help with styles
            self.reporting.system_message(str(error), disable_markdown=True)
            return
        except ArgumentParserExitException:  # Ignore exits
            return

        self.print_config_report(
            baseline=new_arguments.baseline,
            show_only_differences=new_arguments.show_diff,
            filter_regex=new_arguments.search,
        )

    def command_list_tools(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /list-tools takes no arguments")
        else:
            self.print_tools_report()

    def command_load(self, command, arguments, arguments_str):
        filename = 'chat_session.json' if len(arguments) == 0 else os.path.expanduser(arguments[0])
        with lair.events.defer_events():
            current_session_id = self.chat_session.session_id  # Preserve to overwrite the current session
            self.chat_session.load_from_file(filename)
            self.chat_session.session_id = current_session_id
            if self.chat_session.session_alias is not None and \
               not self.session_manager.is_alias_available(self.chat_session.session_alias):
                logger.warn("Session loaded without alias. The alias is already in use")
                self.chat_session.session_alias = None
            self._rebuild_chat_session()
            self.reporting.system_message(f"Session loaded from {filename}")

    def command_messages(self, command, arguments, arguments_str):
        if len(arguments) > 1:
            self.reporting.user_error("ERROR: Invalid arguments: Usage /messages [filename?]")
        else:
            history = self.chat_session.history
            if history.num_messages() == 0:
                logger.warn("No messages found")
                return

            filename = arguments[0] if len(arguments) == 1 else None
            if filename is not None:
                jsonl_str = history.get_messages_as_jsonl_string()
                lair.util.save_file(filename, jsonl_str + "\n")
                self.reporting.system_message(f'Messages saved  ({len(jsonl_str)} bytes)')
            else:
                messages = history.get_messages()
                for message in messages:
                    self.reporting.print_highlighted_json(json.dumps(message))

    def command_mode(self, command, arguments, arguments_str):
        if len(arguments) == 0:
            self.print_modes_report()
        elif len(arguments) == 1:  # Set mode
            lair.config.change_mode(arguments[0])
            old_session = self.chat_session
            self.chat_session = lair.sessions.get_chat_session(lair.config.get('session.type'))
            self.chat_session.import_state(old_session)
        else:
            self.reporting.user_error("ERROR: Invalid arguments: Usage: /mode [name?]")

    def command_model(self, command, arguments, arguments_str):
        if len(arguments) > 1:
            self.reporting.user_error("ERROR: Invalid arguments: Usage /model [name?]")
        elif len(arguments) == 0:
            self.print_current_model_report()
        elif len(arguments) == 1:
            lair.config.set('model.name', arguments[0])

    def command_prompt(self, command, arguments, arguments_str):
        if len(arguments) == 0:
            self.reporting.system_message(lair.config.get('session.system_prompt_template'))
        else:
            lair.config.set('session.system_prompt_template', arguments_str)

    def command_reload_settings(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: USAGE: /reload_settings")
        else:
            lair.config.reload()
            self.reporting.system_message('Settings reloaded from disk')

    def command_save(self, command, arguments, arguments_str):
        filename = 'chat_session.json' if len(arguments) == 0 else os.path.expanduser(arguments[0])
        self.chat_session.save_to_file(filename)
        self.reporting.system_message(f"Session written to {filename}")

    def command_session(self, command, arguments, arguments_str):
        if len(arguments) == 0:
            self.print_sessions_report()
        elif len(arguments) == 1:
            id_or_alias = arguments[0]
            self._switch_to_session(id_or_alias)
        else:
            self.reporting.user_error("ERROR: USAGE: /session [session_id|alias?]")

    def command_session_alias(self, command, arguments, arguments_str):
        if len(arguments) != 1 and len(arguments) != 2:
            self.reporting.user_error("ERROR: Invalid arguments: Usage /session-alias [session_id|alias?] [new_alias?])")
        else:
            session_id = self.session_manager.get_session_id(arguments[0])
            new_alias = arguments[1] if len(arguments) == 2 else None
            if self.session_manager.is_alias_available(new_alias):
                if self.chat_session.session_id == session_id:
                    self.chat_session.session_alias = new_alias
                self.session_manager.set_alias(session_id, new_alias)
            elif isinstance(lair.util.safe_int(new_alias), int):
                self.reporting.user_error("ERROR: Aliases may not be integers")
            else:
                self.reporting.user_error("ERROR: That alias is unavailable")

    def command_session_delete(self, command, arguments, arguments_str):
        if len(arguments) == 0:
            self.reporting.user_error("ERROR: Invalid arguments: Usage /session-delete [session_id|alias?]...)")
        else:
            self.session_manager.delete_sessions(arguments)

            # If the current session was deleted, recreate it
            try:
                self.session_manager.get_session_id(self.chat_session.session_id)
            except lair.sessions.session_manager.UnknownSessionException:
                self._new_chat_session()

    def command_session_new(self, command, arguments, arguments_str):
        if len(arguments) != 0:
            self.reporting.user_error("ERROR: /session-new takes no arguments")
        else:
            self._new_chat_session()
            self.reporting.system_message('New session created')

    def command_session_title(self, command, arguments, arguments_str):
        if len(arguments) == 0:
            self.reporting.user_error("ERROR: Invalid arguments: Usage /session-title [session_id|alias?] [new_title?])")
        else:
            session_id = self.session_manager.get_session_id(arguments[0])
            new_title = ' '.join(arguments[1:]) if len(arguments) != 1 else None
            if self.chat_session.session_id == session_id:
                self.chat_session.session_title = new_title
            self.session_manager.set_title(session_id, new_title)

    def command_set(self, command, arguments, arguments_str):
        if len(arguments) == 0:
            self.print_config_report()
        else:
            key = arguments[0]
            value = '' if len(arguments) == 1 else arguments_str[len(arguments[0]) + 1:].strip()
            if key not in lair.config.active:
                self.reporting.user_error("ERROR: Unknown key: %s" % key)
            else:
                lair.config.set(key, value)
