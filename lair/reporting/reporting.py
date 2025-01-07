import datetime
import math
import re
import sys
import traceback

import lair

import rich
import rich.markdown
import rich.text
import rich.traceback


class ReportingSingletoneMeta(type):
    _instances = {}

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

        self.console = rich.console.Console(no_color=no_color,
                                            force_terminal=force_terminal)

    def print_rich(self, *args, **kwargs):
        """Print using rich."""
        kwargs['no_wrap'] = not lair.config.get('style.word_wrap')

        self.console.print(*args, **kwargs)

    def plain(self, *args, **kwargs):
        """Return plain rich string with no Markup."""
        return rich.text.Text(*args, **kwargs)

    def filter_keys_dict_list(self, rows_of_dicts, allowed_keys):
        new_rows = []
        for row in rows_of_dicts or []:
            new_rows.append(dict(filter(lambda r: r[0] in allowed_keys, row.items())))

        return new_rows

    def table_from_dicts(self, rows_of_dicts, *, column_names=None,
                         automatic_column_names=True, style=None, markup=False):
        if not rows_of_dicts:
            return

        if column_names is None:
            if automatic_column_names:
                column_names = map(lambda i: i, rows_of_dicts[0].keys())
            else:
                column_names = None

        table_rows = list(map(lambda r: [*r.values()], rows_of_dicts))
        self.table(table_rows,
                   column_names=column_names,
                   style=style,
                   markup=markup)

    def format_value(self, value):
        if value is None:
            return ''
        elif isinstance(value, datetime.datetime):
            return value.strftime("%m/%d/%y %H:%M:%S")
        elif not isinstance(value, str):
            return str(value)
        else:
            return value

    def table(self, rows, *, column_names=None, style=None, markup=False):
        if rows is None:
            return

        table = rich.table.Table(style=style,
                                 # row_styles=[style],
                                 show_header=column_names is not None)

        if column_names:
            for column_name in column_names:
                table.add_column(column_name if markup else self.plain(column_name))

        for row in rows:
            if not markup:
                row = map(lambda i: self.plain(self.format_value(i)), row)
            table.add_row(*row)

        self.print_rich(table)

    def table_system(self, *args, **kwargs):
        kwargs['style'] = lair.config.get('style.system_message')
        self.table(*args, **kwargs)

    def exception(self):
        if lair.config.get('style.render_rich_tracebacks'):
            self.print_rich(rich.traceback.Traceback())
        else:
            traceback.print_exception(*sys.exc_info())

    def error(self, message, show_exception=None):
        '''
        When show_exception is:
          - None - Show if DEBUG is enabled
          - true - Always show
          - false - Never show
        '''
        if show_exception or show_exception is None and lair.util.get_log_level() == 'DEBUG':
            self.exception()

        self.print_rich(self.plain('ERROR: ' + message),
                        style=lair.config.get('style.error'))

    def tool_message(self, message, show_heading=False):
        if show_heading:
            self.console.print('TOOL',
                               style=lair.config.get('style.tool_message_heading'))

        self.print_rich(self.plain(message),
                        markup=False,
                        style=lair.config.get('style.tool_message'))

    def user_error(self, message):
        self.print_rich(self.plain(message),
                        style=lair.config.get('style.user_error'))

    def system_message(self, message, show_heading=False):
        if show_heading:
            self.print_rich('SYSTEM',
                            style=lair.config.get('style.system_message_heading'))

        if lair.config.get('style.render_markdown'):
            self.print_rich(rich.markdown.Markdown(message),
                            style=lair.config.get('style.system_message'))
        else:
            self.print_rich(self.plain(message),
                            style=lair.config.get('style.system_message'))

    def llm_output(self, message, show_heading=False):
        if show_heading:
            self.print_rich('AI',
                            style=lair.config.get('style.llm_output_heading'))

        if lair.config.get('style.render_markdown'):
            self.print_rich(rich.markdown.Markdown(message),
                            style=lair.config.get('style.llm_output'))
        else:
            self.print_rich(self.plain(message),
                            style=lair.config.get('style.llm_output'))

    def format_content_list(self, content_list):
        message_parts = ['[multipart message]']
        for part in content_list:
            if part['type'] == 'text':
                message_parts.append(f"---> text: {part['text']}")
            elif part['type'] == 'image_url':
                mime_type = re.match(r"data:([^;]+);base64,", part['image_url']['url']).group(1)
                message_parts.append(f"---> image: {mime_type}")
            else:
                raise ValueError("format_content_list(): Unknown content type: {part['type']}")

        return '\n'.join(message_parts)

    def message(self, message):
        """Display a message object in history style."""
        if isinstance(message['content'], str):
            content = message['content'].rstrip()
        else:
            content = self.format_content_list(message['content'])

        if message['role'] == 'user':
            self.print_rich('HUMAN',
                            style=lair.config.get('style.human_output_heading'))
            self.print_rich(content, style=lair.config.get('style.human_output'))
        elif message['role'] == 'assistant':
            self.llm_output(content, show_heading=True)
        elif message['role'] == 'system':
            self.system_message(content, show_heading=True)
        elif message['role'] == 'tool':
            self.tool_message(content, show_heading=True)
        else:
            self.system_message(content, show_heading=True)

    def messages_to_str(self, messages):
        lines = []
        for message in messages:
            lines.append(f'{message["role"].upper()}: {message["content"]}')

        return '\n'.join(lines)

    def get_style_by_range(self, value, minimum=0, maximum=100, *,
                           display_value=None, log=False, inverse=False,
                           styles=[  # shades in red, yellow, and green
                               'rgb(51,0,0)', 'rgb(102,0,0)', 'rgb(153,0,0)',
                               'rgb(204,0,0)', 'rgb(255,0,0)',
                               'rgb(51,51,0)', 'rgb(102,102,0)', 'rgb(153,153,0)',
                               'rgb(204,204,0)', 'rgb(255,255,0)',
                               'rgb(0,51,0)', 'rgb(0,102,0)', 'rgb(0,153,0)',
                               'rgb(0,204,0)', 'rgb(0,255,0)',
                           ]):
        '''
        Color a value based on where it falls within a range
        '''
        index_percent = (value - minimum) / (maximum - minimum)
        if log:
            index_percent = math.log(1 + index_percent, 2)
        if inverse:
            index_percent = 1 - index_percent

        return styles[round(len(styles) * index_percent)]

    def color_gt_lt(self, value, *, center=0):
        if value > center:
            return 'green'
        elif value < center:
            return 'red'
        else:
            return 'gray'
