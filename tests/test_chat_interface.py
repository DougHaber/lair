import sys
import types
import importlib
from lair.components.history.chat_history import ChatHistory
from lair.logging import logger


def import_commands():
    mod = types.ModuleType('lair.cli.chat_interface')
    mod.ChatInterface = object
    sys.modules['lair.cli.chat_interface'] = mod
    return importlib.import_module('lair.cli.chat_interface_commands')


class DummyReporting:
    def __init__(self):
        self.messages = []
    def system_message(self, message, **kwargs):
        self.messages.append(('system', message))
    def user_error(self, message):
        self.messages.append(('error', message))
    def print_rich(self, *args, **kwargs):
        pass
    def table_system(self, *args, **kwargs):
        pass


class DummyChatSession:
    def __init__(self):
        self.history = ChatHistory()
        self.session_title = 'title'
        self.last_prompt = 'prompt'
        self.last_response = 'response'


def make_interface():
    commands = import_commands()
    class CI(commands.ChatInterfaceCommands):
        def __init__(self):
            self.chat_session = DummyChatSession()
            self.reporting = DummyReporting()
            self.session_manager = None
    return CI()


def test_command_clear():
    ci = make_interface()
    ci.chat_session.history.add_message('user', 'hi')
    ci.command_clear('/clear', [], '')
    assert ci.chat_session.history.num_messages() == 0
    assert ci.chat_session.session_title is None
    assert ('system', 'Conversation history cleared') in ci.reporting.messages


def test_command_debug_toggle():
    ci = make_interface()
    orig = logger.level
    ci.command_debug('/debug', [], '')
    first = logger.level
    ci.command_debug('/debug', [], '')
    second = logger.level
    assert first != orig
    assert second != first


def test_command_history_slice():
    ci = make_interface()
    for i in range(5):
        ci.chat_session.history.add_message('user', str(i))
    ci.command_history_slice('/history-slice', ['1:3'], '1:3')
    msgs = ci.chat_session.history.get_messages()
    assert [m['content'] for m in msgs] == ['1', '2']
    assert any('History updated' in m[1] for m in ci.reporting.messages)
