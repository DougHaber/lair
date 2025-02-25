import lair
import lair.cli
from lair.logging import logger  # noqa


def _module_info():
    return {
        'description': 'Run the interactive Chat interface',
        'class': Chat,
        'tags': ['cli'],
        'aliases': []
    }


class Chat():

    def __init__(self, parser):
        parser.add_argument('-s', '--session', type=str,
                            help='Session id or alias to use (default is a new session)')

    def run(self, arguments):
        chat = lair.cli.ChatInterface(starting_session_id_or_alias=arguments.session)
        chat.start()
