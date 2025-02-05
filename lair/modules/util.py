import re
import sys
import textwrap

import lair
import lair.cli
import lair.util
import lair.reporting
from lair.logging import logger  # noqa


def _module_info():
    return {
        'description': 'Make simple calls to LLMs',
        'class': Util,
        'tags': [],
        'aliases': []
    }


class Util():
    system_prompt = textwrap.dedent("""\
    """)

    def __init__(self, parser):
        parser.add_argument('-a', '--attach-file', type=str, dest='attachments', action='append',
                            help='Specify one or more image files to attach to the request. Multiple files may be provided by repeating the argument. Ensure the model you are interacting with supports file attachments. Globs are supported.')
        parser.add_argument('-c', '--content', type=str,
                            help='Content to use'),
        parser.add_argument('-C', '--content-file', type=str,
                            help='Filename containing content use')
        parser.add_argument('-F', '--include-filenames', action='store_true', default=None,
                            help='Provide filenames of attached files (via misc.provide_attachment_filenames, default=%s)' % lair.config.get('misc.provide_attachment_filenames'))
        parser.add_argument('-i', '--instructions', type=str,
                            help='Instructions for the request')
        parser.add_argument('-I', '--instructions-file', type=str,
                            help='Filename containing instructions for the request')
        parser.add_argument('-p', '--pipe', action='store_true',
                            help='Read content from stdin')
        parser.add_argument('-t', '--enable-tools', action='store_true',
                            help='Allow the model to call tools')

    def call_llm(self, chat_session, *, instructions, user_messages, enable_tools=True):
        messages = [
            lair.util.get_message('system', chat_session.get_system_prompt()),
            lair.util.get_message('user', instructions),
            *user_messages,
        ]

        if enable_tools:
            response, _ = chat_session.invoke_with_tools(messages)
        else:
            response = chat_session.invoke(messages)

        return response

    def clean_response(self, response):
        response = re.sub(r'^```.*\n?', '', response, flags=re.MULTILINE)

        return response

    def _read_file(self, filename):
        with open(filename, 'r') as fd:
            return fd.read()

    def _get_instructions(self, arguments):
        if arguments.instructions_file:
            return self._read_file(arguments.instructions_file)
        elif arguments.instructions:
            return arguments.instructions
        else:
            logger.error("Either --instructions or --instructions-file must be proved")
            sys.exit(1)

    def _get_user_messages(self, arguments):
        # Read the user "content" message
        message = None
        if arguments.pipe:
            message = sys.stdin.read()
        elif arguments.content_file:
            message = self._read_file(arguments.content_file)
        elif arguments.content:
            message = arguments.content

        if message:  # These extra instructions helps a lot in some models
            message = "CONTENT is found below. Everything above is instructions and rules:\n" + message

        messages = []
        if arguments.attachments:
            attachment_content_parts, attachment_messages = lair.util.get_attachments_content(arguments.attachments)
            messages.extend(attachment_messages)
        else:
            attachment_content_parts = []

        # Add the regular message as a standard message, or image sections if there are images
        if message:
            if len(attachment_content_parts) < 0:
                messages.append(lair.util.get_message('user', message))
            else:
                content_parts = []

                if message:
                    content_parts.append({"type": "text", "text": message})

                content_parts.extend(attachment_content_parts)

                messages.append({
                    'role': 'user',
                    'content': content_parts,
                })

        return messages

    def run(self, arguments):
        util_prompt_template = lair.config.get('util.system_prompt_template')
        lair.config.set('session.system_prompt_template', util_prompt_template)

        chat_session = lair.sessions.get_session(
            session_type=lair.config.get('session.type'),
        )

        if arguments.include_filenames is not None:
            lair.config.set('misc.provide_attachment_filenames', arguments.include_filenames)

        instructions = self._get_instructions(arguments)
        user_messages = self._get_user_messages(arguments)

        response = self.call_llm(chat_session,
                                 instructions=instructions,
                                 enable_tools=arguments.enable_tools,
                                 user_messages=user_messages)
        response = self.clean_response(response)

        print(response)
