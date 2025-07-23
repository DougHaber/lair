"""Utility methods for reporting chat interface information."""

import re
from collections.abc import Iterator
from typing import Any

import lair
from lair.logging import logger


class ChatInterfaceReports:
    """Mixin that provides chat report printing helpers."""

    chat_session: Any
    session_manager: Any
    commands: dict[str, Any]
    reporting: Any
    _models: list[dict[str, Any]] | None
    _get_shortcut_details: Any

    def _iter_config_rows(
        self,
        show_only_differences: bool,
        filter_regex: str | None,
        baseline: str | None,
    ) -> Iterator[list[str]]:
        """
        Generate formatted configuration rows.

        Args:
            show_only_differences: If ``True`` only return values that differ from the baseline.
            filter_regex: Optional regular expression used to filter keys.
            baseline: Name of the baseline mode to compare against.

        Returns:
            Iterator over ``[key, formatted_value]`` pairs for display.

        """
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

    def print_config_report(
        self,
        *,
        show_only_differences: bool = False,
        filter_regex: str | None = None,
        baseline: str | None = None,
    ) -> None:
        """
        Display the current configuration table.

        Args:
            show_only_differences: When ``True`` hide values that match the baseline.
            filter_regex: Regex used to filter configuration keys.
            baseline: Mode to compare values against. If ``None``, compares against defaults.

        """
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

    def print_current_model_report(self) -> None:
        """Print information about the active model."""
        active_config = lair.config.active
        self.reporting.table_system(
            [
                ["Name", active_config.get("model.name")],
                ["Temperature", str(active_config.get("model.temperature"))],
                ["OpenAI API Base", str(active_config.get("openai.api_base"))],
                ["Max Tokens", str(active_config.get("model.max_tokens"))],
            ]
        )

    def print_help(self) -> None:
        """Display available commands and shortcuts."""
        rows = []
        for command, details in sorted(self.commands.items()):
            rows.append([command, details["description"]])

        self.reporting.table_system(rows)

        rows = []
        for shortcut, description in sorted(self._get_shortcut_details().items()):
            rows.append([shortcut, description])

        self.reporting.table_system(rows)

    def print_history(self, *, num_messages: int | None = None) -> None:
        """
        Print the conversation history.

        Args:
            num_messages: Optional number of recent messages to display. If ``None`` all messages are shown.

        """
        messages = self.chat_session.history.get_messages()

        if not messages:
            return
        else:
            if num_messages is not None:
                messages = messages[-num_messages:]
            for message in messages:
                self.reporting.message(message)

    def print_models_report(self, update_cache: bool = False) -> None:
        """
        Show available models.

        Args:
            update_cache: If ``True`` refresh the cached model list.

        """
        models = sorted(self.chat_session.list_models(), key=lambda m: m["id"])
        if update_cache:  # Update the cached list of models with the latest results
            self._models = models

        column_formatters = {
            "id": lambda v: self.reporting.style(v, style="bright_cyan" if v == lair.config.get("model.name") else "")
        }
        self.reporting.table_from_dicts_system(models, column_formatters=column_formatters)

    def print_modes_report(self) -> None:
        """Display all available configuration modes."""
        rows = []
        for mode in sorted(filter(lambda m: not m.startswith("_"), lair.config.modes.keys())):
            if mode == lair.config.active_mode:
                mode_display_value = self.reporting.style(mode, style="bright_cyan")
            else:
                mode_display_value = self.reporting.style(mode)

            rows.append([mode_display_value, lair.config.modes[mode].get("_description", "")])

        self.reporting.table_system(rows)

    def print_sessions_report(self) -> None:
        """List all sessions with basic metadata."""
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

    def print_tools_report(self) -> None:
        """Display all available tools and their status."""
        tools = sorted(self.chat_session.tool_set.get_all_tools(), key=lambda m: (m["class_name"], m["name"]))
        column_formatters = {
            "enabled": lambda v: self.reporting.color_bool(v, true_str="yes", false_str="-", false_style="dim"),
        }
        self.reporting.table_from_dicts_system(
            tools, column_names=["class_name", "name", "enabled"], column_formatters=column_formatters
        )

    def print_mcp_tools_report(self) -> None:
        """Display tools loaded from MCP manifests."""
        tools = [tool for tool in self.chat_session.tool_set.get_all_tools() if tool["class_name"] == "MCPTool"]
        if not tools:
            self.reporting.system_message("No MCP tools found.")
            return
        column_formatters = {
            "enabled": lambda v: self.reporting.color_bool(v, true_str="yes", false_str="-", false_style="dim"),
        }
        self.reporting.table_from_dicts_system(
            sorted(tools, key=lambda m: m["name"]),
            column_names=["name", "enabled", "source"],
            column_formatters=column_formatters,
        )
