import re

import lair
from lair.logging import logger  # noqa


class ChatInterfaceReports:
    def _iter_config_rows(self, show_only_differences, filter_regex, baseline):
        default_settings = lair.config.default_settings if baseline is None else lair.config.modes[baseline]
        modified_style = lair.config.get("chat.set_command.modified_style")
        unmodified_style = lair.config.get("chat.set_command.unmodified_style")

        for key, value in sorted(lair.config.active.items()):
            if key.startswith("_") or (filter_regex is not None and not re.search(filter_regex, key)):
                continue

            if value == default_settings.get(key):
                if show_only_differences:
                    continue
                display_value = self.reporting.style(str(value), style=unmodified_style)
            else:
                display_value = self.reporting.style(str(value), style=modified_style)

            yield [key, display_value]

    def print_config_report(self, *, show_only_differences=False, filter_regex=None, baseline=None):
        if baseline:
            if baseline not in lair.config.modes:
                logger.error(f"Unknown mode: {baseline}")
                return
            self.reporting.system_message(f"Current mode: {lair.config.active_mode}, Baseline mode: {baseline}")
        else:
            self.reporting.system_message(f"Current mode: {lair.config.active_mode}")

        rows = list(self._iter_config_rows(show_only_differences, filter_regex, baseline))

        if rows:
            self.reporting.table_system(rows)
        else:
            self.reporting.system_message("No matching keys")

    def print_current_model_report(self):
        active_config = lair.config.active
        self.reporting.table_system(
            [
                ["Name", active_config.get("model.name")],
                ["Temperature", str(active_config.get("model.temperature"))],
                ["OpenAI API Base", str(active_config.get("openai.api_base"))],
                ["Max Tokens", str(active_config.get("model.max_tokens"))],
            ]
        )

    def print_help(self):
        rows = []
        for command, details in sorted(self.commands.items()):
            rows.append([command, details["description"]])

        self.reporting.table_system(rows)

        rows = []
        for shortcut, description in sorted(self._get_shortcut_details().items()):
            rows.append([shortcut, description])

        self.reporting.table_system(rows)

    def print_history(self, *, num_messages=None):
        messages = self.chat_session.history.get_messages()

        if not messages:
            return
        else:
            if num_messages is not None:
                messages = messages[-num_messages:]
            for message in messages:
                self.reporting.message(message)

    def print_models_report(self, update_cache=False):
        models = sorted(self.chat_session.list_models(), key=lambda m: m["id"])
        if update_cache:  # Update the cached list of models with the latest results
            self._models = models

        column_formatters = {
            "id": lambda v: self.reporting.style(v, style="bright_cyan" if v == lair.config.get("model.name") else "")
        }
        self.reporting.table_from_dicts_system(models, column_formatters=column_formatters)

    def print_modes_report(self):
        rows = []
        for mode in sorted(filter(lambda m: not m.startswith("_"), lair.config.modes.keys())):
            if mode == lair.config.active_mode:
                mode_display_value = self.reporting.style(mode, style="bright_cyan")
            else:
                mode_display_value = self.reporting.style(mode)

            rows.append([mode_display_value, lair.config.modes[mode].get("_description", "")])

        self.reporting.table_system(rows)

    def print_sessions_report(self):
        current_session_id = self.chat_session.session_id
        rows = []
        for details in sorted(self.session_manager.all_sessions(), key=lambda s: s["id"]):
            rows.append(
                {
                    "id": details["id"],
                    "alias": details["alias"],
                    "title": details["title"],
                    "mode": details["session"]["mode"],
                    "model": details["session"]["model_name"],
                    "num_messages": len(details["history"]),
                }
            )

        if len(rows) == 0:
            self.reporting.system_message("No sessions found.")
        else:
            column_formatters = {
                "id": lambda v: self.reporting.style(str(v), style="bright_cyan" if v == current_session_id else None),
                "num_messages": lambda v: self.reporting.style(str(v), style="gray39" if v == 0 else None),
            }
            self.reporting.table_from_dicts_system(
                rows,
                column_formatters=column_formatters,
                column_names=["id", "alias", "mode", "model", "title", "num_messages"],
            )

    def print_tools_report(self):
        tools = sorted(self.chat_session.tool_set.get_all_tools(), key=lambda m: (m["class_name"], m["name"]))
        column_formatters = {
            "enabled": lambda v: self.reporting.color_bool(v, true_str="yes", false_str="-", false_style="dim"),
        }
        self.reporting.table_from_dicts_system(
            tools, column_names=["class_name", "name", "enabled"], column_formatters=column_formatters
        )
