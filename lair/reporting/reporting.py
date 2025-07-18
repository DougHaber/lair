import datetime
import math
import re
import sys
import traceback
from typing import Any

import rich
import rich.columns
import rich.highlighter
import rich.markdown
import rich.text
import rich.traceback

import lair


class ReportingSingletoneMeta(type):
    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Reporting(metaclass=ReportingSingletoneMeta):
    def __init__(self, *, disable_color=False, force_color=False):
        force_terminal = None
        if disable_color:
            no_color = True
        elif force_color:
            no_color = False
            force_terminal = True
        else:
            no_color = None

        self.console = rich.console.Console(no_color=no_color, force_terminal=force_terminal)
        self.json_highlighter = rich.highlighter.JSONHighlighter()

    def print_rich(self, *args, **kwargs):
        """Print using rich."""
        kwargs["no_wrap"] = not lair.config.get("style.word_wrap")

        self.console.print(*args, **kwargs)

    def print_highlighted_json(self, json_str):
        if lair.config.get("style.messages_command.syntax_highlight"):
            rich.print_json(json_str, indent=None)
        else:
            rich.print(json_str)

    def style(self, *args, **kwargs):
        """Style a string using rich.
        If no style parameter is provided, convert to plaintext so that rich markup isn't processed"""
        return rich.text.Text(*args, **kwargs)

    def filter_keys_dict_list(self, rows_of_dicts, allowed_keys):
        new_rows = []
        for row in rows_of_dicts or []:
            new_rows.append(dict(filter(lambda r: r[0] in allowed_keys, row.items())))

        return new_rows

    def table_from_dicts(
        self,
        rows_of_dicts,
        *,
        column_names=None,
        column_formatters=None,
        automatic_column_names=True,
        style=None,
        markup=False,
    ):
        if not rows_of_dicts:
            return

        if column_names is None:
            column_names = list(rows_of_dicts[0].keys()) if automatic_column_names else None
        else:
            column_names = list(column_names)

        # Construct table rows by selecting values based on the specified column order.
        # This ensures only the requested columns are included and maintains their order.
        table_rows = [[r[col] for col in column_names if col in r] for r in rows_of_dicts]

        self.table(
            table_rows, column_names=column_names, column_formatters=column_formatters, style=style, markup=markup
        )

    def format_value(self, value):
        if value is None:
            return ""
        elif isinstance(value, datetime.datetime):
            return value.strftime("%m/%d/%y %H:%M:%S")
        elif not isinstance(value, str):
            return str(value)
        else:
            return value

    def table(self, rows, *, column_names=None, column_formatters=None, style=None, markup=False):
        """
        Display a table from a 2-dimensional array.

        Args:
            rows (Iterable): A 2-dimensional array of row data.
            column_names (Optional[List[str]]): A list of names for the columns.
                When provided, these names are used in the header, and also as
                keys for column_formatters if specified.
            column_formatters (Optional[Dict[str, Callable]]): A dictionary
                mapping column names to formatter functions. For any cell in a
                column with an associated formatter, the cell value is passed to
                the formatter, and its return value is used directly (without
                applying self.style()).
                Note: This option only takes effect if column_names is provided.
            style (Optional[str]): Base rich style to apply to the table.
            markup (bool): If False, all column names and row data (except those formatted via column_formatters)
                are converted to plain text using self.style(self.format_value(...)). If True, values are used as-is
                unless a formatter is defined.

        Returns:
            None
        """
        if rows is None:
            return

        table = rich.table.Table(style=style, show_header=column_names is not None)

        if column_names:
            for column_name in column_names:
                table.add_column(column_name if markup else self.style(column_name))

        for row in rows:
            formatted = [
                self._format_cell(cell, idx, column_names, column_formatters, markup) for idx, cell in enumerate(row)
            ]
            table.add_row(*formatted)

        self.print_rich(table)

    def _format_cell(self, cell, idx, column_names, column_formatters, markup):
        if column_names and column_formatters and idx < len(column_names) and column_names[idx] in column_formatters:
            return column_formatters[column_names[idx]](cell)

        if not markup:
            return cell if isinstance(cell, rich.text.Text) else self.style(self.format_value(cell))

        return cell

    def table_from_dicts_system(self, *args, **kwargs):
        kwargs["style"] = lair.config.get("style.system_message")
        self.table_from_dicts(*args, **kwargs)

    def table_system(self, *args, **kwargs):
        kwargs["style"] = lair.config.get("style.system_message")
        self.table(*args, **kwargs)

    def exception(self):
        if lair.config.get("style.render_rich_tracebacks"):
            self.print_rich(rich.traceback.Traceback())
        else:
            traceback.print_exception(*sys.exc_info())

    def error(self, message, show_exception=None):
        """
        When show_exception is:
          - None - Show if DEBUG is enabled
          - true - Always show
          - false - Never show
        """
        if show_exception or show_exception is None and lair.util.is_debug_enabled():
            self.exception()

        self.print_rich(self.style("ERROR: " + message), style=lair.config.get("style.error"))

    def format_json(self, json_str, max_length=None, plain_style=None, enable_highlighting=True):
        if enable_highlighting:
            json_text = self.json_highlighter(json_str)
        else:
            json_text = rich.text.Text(json_str, style=plain_style)

        if max_length is not None and len(json_text) > max_length:
            json_text = json_text[:max_length]
            json_text.append("...", style=lair.config.get("style.ellipsis"))

        return json_text

    def assistant_tool_calls(self, message, show_heading=False):
        if lair.config.get("style.llm_output.tool_call.background"):
            background_style = " on " + lair.config.get("style.llm_output.tool_call.background")
        else:
            background_style = ""

        if show_heading:
            self.print_rich(
                "AI" + " " * (self.console.width - 2),
                style=lair.config.get("style.llm_output_heading") + background_style,
                soft_wrap=True,
            )

        for tool_call in message["tool_calls"]:
            function = tool_call["function"]

            text = rich.text.Text()
            text.append("- ", style=lair.config.get("style.llm_output.tool_call.bullet"))
            text.append("TOOL CALL: ", style=lair.config.get("style.llm_output.tool_call.prefix"))
            text.append(f"{function['name']}(", style=lair.config.get("style.llm_output.tool_call.function"))
            arguments = self.format_json(
                function["arguments"],
                max_length=lair.config.get("style.llm_output.tool_call.max_arguments_length"),
                plain_style=lair.config.get("style.llm_output.tool_call.arguments"),
                enable_highlighting=lair.config.get("style.llm_output.tool_call.arguments_syntax_highlighting"),
            )
            text.append(arguments)

            text.append(")", style=lair.config.get("style.llm_output.tool_call.function"))
            text.append(f"  ({tool_call['id']})", style=lair.config.get("style.llm_output.tool_call.id"))
            self.console.print(text, markup=False, style=background_style, soft_wrap=True, end="")

            remaining_characters = self.console.width - len(text) % self.console.width
            self.console.print(" " * remaining_characters, style=background_style)

    def tool_message(self, message, show_heading=False):
        if lair.config.get("style.tool_message.background"):
            background_style = " on " + lair.config.get("style.tool_message.background")
        else:
            background_style = ""

        if show_heading:
            self.console.print(
                "TOOL" + " " * (self.console.width - 4),
                style=lair.config.get("style.tool_message.heading") + background_style,
                soft_wrap=True,
            )

        text = rich.text.Text()
        text.append("- ", style=lair.config.get("style.tool_message.bullet"))
        text.append(f"({message['tool_call_id']})", style=lair.config.get("style.tool_message.id"))
        text.append(" -> ", style=lair.config.get("style.tool_message.arrow"))

        response = self.format_json(
            message["content"],
            max_length=lair.config.get("style.tool_message.max_response_length"),
            plain_style=lair.config.get("style.tool_message.response"),
            enable_highlighting=lair.config.get("style.tool_message.response_syntax_highlighting"),
        )
        text.append(response)
        self.console.print(text, end="", soft_wrap=True, style=background_style)

        remaining_characters = self.console.width - len(text) % self.console.width
        self.console.print(" " * remaining_characters, style=background_style)

    def user_error(self, message):
        self.print_rich(self.style(message), style=lair.config.get("style.user_error"))

    def system_message(self, message, show_heading=False, disable_markdown=False):
        if show_heading:
            self.print_rich("SYSTEM", style=lair.config.get("style.system_message_heading"))

        if lair.config.get("style.render_markdown") and not disable_markdown:
            self.print_rich(rich.markdown.Markdown(message), style=lair.config.get("style.system_message"))
        else:
            self.print_rich(self.style(message), style=lair.config.get("style.system_message"))

    def _llm_output__with_thoughts(self, message):
        sections = re.split(r"(<(?:thought|think|thinking)>.*?</(?:thought|think|thinking)>)", message, flags=re.DOTALL)
        pattern = re.compile(r"<(thought|think|thinking)>.*?</\1>", re.DOTALL)

        for section in sections:
            if pattern.search(section.strip()):  # Search for a thought-like tag
                if lair.config.get("style.thoughts.hide_thoughts"):
                    continue
                elif lair.config.get("style.thoughts.hide_tags"):
                    section = re.sub(r"(<(/?)(thought|think|thinking)>)", r"", section)
                else:  # Protect the tags from markdown rendering
                    section = re.sub(r"(<(/?)(thought|think|thinking)>)", r"\\\1", section)
                self.print_rich(rich.markdown.Markdown(section), style=lair.config.get("style.llm_output_thought"))
            elif section.strip():  # Ignore completely empty sections
                self.print_rich(rich.markdown.Markdown(section), style=lair.config.get("style.llm_output"))

    def llm_output(self, message, show_heading=False):
        if show_heading:
            self.print_rich("AI", style=lair.config.get("style.llm_output_heading"))

        if lair.config.get("style.render_markdown"):
            if lair.config.get("style.thoughts.enabled"):
                self._llm_output__with_thoughts(message)
            else:
                self.print_rich(rich.markdown.Markdown(message), style=lair.config.get("style.llm_output"))
        else:
            self.print_rich(self.style(message), style=lair.config.get("style.llm_output"))

    def format_content_list(self, content_list):
        message_parts = ["[multipart message]"]
        for part in content_list:
            if part["type"] == "text":
                message_parts.append(f"---> text: {part['text']}")
            elif part["type"] == "image_url":
                mime_type = re.match(r"data:([^;]+);base64,", part["image_url"]["url"]).group(1)
                message_parts.append(f"---> image: {mime_type}")
            else:
                raise ValueError("format_content_list(): Unknown content type: {part['type']}")

        return "\n".join(message_parts)

    def message(self, message):
        """Display a message object in history style."""
        if isinstance(message["content"], str):
            content = message["content"].rstrip()
        else:
            content = self.format_content_list(message["content"])

        if message["role"] == "user":
            self.print_rich("HUMAN", style=lair.config.get("style.human_output_heading"))
            self.print_rich(content, style=lair.config.get("style.human_output"))
        elif message["role"] == "assistant":
            if "tool_calls" in message:
                self.assistant_tool_calls(message, show_heading=True)
            else:
                self.llm_output(content, show_heading=True)
        elif message["role"] == "system":
            self.system_message(content, show_heading=True)
        elif message["role"] == "tool":
            self.tool_message(message, show_heading=True)
        else:
            self.system_message(content, show_heading=True)

    def messages_to_str(self, messages):
        lines = []
        for message in messages:
            lines.append(f"{message['role'].upper()}: {message['content']}")

        return "\n".join(lines)

    def get_style_by_range(
        self,
        value,
        minimum=0,
        maximum=100,
        *,
        display_value=None,
        log=False,
        inverse=False,
        styles=None,
    ):
        """
        Color a value based on where it falls within a range
        """
        if styles is None:
            styles = [
                "rgb(51,0,0)",
                "rgb(102,0,0)",
                "rgb(153,0,0)",
                "rgb(204,0,0)",
                "rgb(255,0,0)",
                "rgb(51,51,0)",
                "rgb(102,102,0)",
                "rgb(153,153,0)",
                "rgb(204,204,0)",
                "rgb(255,255,0)",
                "rgb(0,51,0)",
                "rgb(0,102,0)",
                "rgb(0,153,0)",
                "rgb(0,204,0)",
                "rgb(0,255,0)",
            ]
        index_percent = (value - minimum) / (maximum - minimum)
        if log:
            index_percent = math.log(1 + index_percent, 2)
        if inverse:
            index_percent = 1 - index_percent

        return styles[round(len(styles) * index_percent)]

    def color_gt_lt(self, value, *, center=0, gt_style="green", lt_style="red", eq_style="gray"):
        if value > center:
            return gt_style
        elif value < center:
            return lt_style
        else:
            return eq_style

    def color_bool(self, value, true_str="true", false_str="false", true_style="bold green", false_style="dim red"):
        if value:
            return rich.text.Text(true_str, style=true_style)
        else:
            return rich.text.Text(false_str, style=false_style)
