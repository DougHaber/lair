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
        pass

    def run(self, arguments):
        chat = lair.cli.ChatInterface()
        chat.start()
