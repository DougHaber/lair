import lair
import lair.cli
from lair.logging import logger  # noqa


def _module_info():
    return {"description": "Run the interactive Chat interface", "class": Chat, "tags": ["cli"], "aliases": []}


class Chat:
    def __init__(self, parser):
        parser.add_argument("-s", "--session", type=str, help="Session id or alias to use.")
        parser.add_argument(
            "-S",
            "--allow-create-session",
            action="store_true",
            help="If an alias provided via --session is not found, create it",
        )

    def run(self, arguments):
        chat = lair.cli.ChatInterface(
            starting_session_id_or_alias=arguments.session, create_session_if_missing=arguments.allow_create_session
        )
        chat.start()
