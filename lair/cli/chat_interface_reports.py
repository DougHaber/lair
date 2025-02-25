import lair
from lair.logging import logger  # noqa


class ChatInterfaceReports():
    def print_help(self):
        rows = []
        for command, details in sorted(self.commands.items()):
            rows.append([command, details['description']])

        self.reporting.table_system(rows)

        rows = []
        for shortcut, description in sorted(self._get_shortcut_details().items()):
            rows.append([shortcut, description])

        self.reporting.table_system(rows)

    def print_config_report(self):
        self.reporting.system_message(f"Current mode: {lair.config.active_mode}")

        default_settings = lair.config.default_settings
        modified_style = lair.config.get('chat.set_command.modified_style')
        unmodified_style = lair.config.get('chat.set_command.unmodified_style')
        rows = []
        for key, value in sorted(lair.config.active.items()):
            if not key.startswith('_'):
                if value == default_settings.get(key):
                    display_value = self.reporting.plain(str(value), style=unmodified_style)
                else:
                    display_value = self.reporting.plain(str(value), style=modified_style)
                rows.append([key, display_value])

        self.reporting.table_system(rows)

    def print_modes_report(self):
        rows = []
        for mode in filter(lambda m: not m.startswith('_'), lair.config.modes.keys()):
            current = '* ' if mode == lair.config.active_mode else '  '
            rows.append([current + mode, lair.config.modes[mode].get('_description', '')])

        self.reporting.table_system(rows)

    def print_models_report(self, update_cache=False):
        models = sorted(self.chat_session.list_models(), key=lambda m: m['id'])
        if update_cache:  # Update the cached list of models with the latest results
            self._models = models
        self.reporting.table_from_dicts_system(models)

    def print_sessions_report(self):
        current_session_id = self.chat_session.session_id
        rows = []
        for details in sorted(self.session_manager.all_sessions(), key=lambda s: s['id']):
            rows.append({
                'active': '*' if details['id'] == current_session_id else '',
                'id': details['id'],
                'alias': details['alias'],
                'title': details['title'],
                'model': details['session']['fixed_model_name'],
                'num_messages': len(details['history']),
            })

        if len(rows) == 0:
            self.reporting.system_message('No sessions found.')
        else:
            self.reporting.table_from_dicts_system(rows,
                                                   column_names=['active', 'id', 'alias', 'model',
                                                                 'title', 'num_messages'])

    def print_tools_report(self):
        tools = sorted(self.chat_session.tool_set.get_all_tools(), key=lambda m: m['name'])
        self.reporting.table_from_dicts_system(tools, column_names=['class_name', 'name', 'enabled'])

    def print_current_model_report(self):
        active_config = lair.config.active
        self.reporting.table_system([
            ['Name', self.chat_session.fixed_model_name or active_config.get('model.name')],
            ['Temperature', str(active_config.get('model.temperature'))],
            ['OpenAI API Base', str(active_config.get('openai.api_base'))],
            ['Max Tokens', str(active_config.get('model.max_tokens'))],
        ])
