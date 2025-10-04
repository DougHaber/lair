from __future__ import annotations

import importlib
import sys
import types

from tests.helpers import ChatSessionDouble, RecordingReporting


def import_commands():
    mod = types.ModuleType("lair.cli.chat_interface")
    mod.ChatInterface = object
    sys.modules["lair.cli.chat_interface"] = mod
    return importlib.import_module("lair.cli.chat_interface_commands")


class TestChatInterfaceCommands:
    def make_interface(self):
        commands = import_commands()

        class CI(commands.ChatInterfaceCommands):
            def __init__(self):
                self.chat_session = ChatSessionDouble()
                self.reporting = RecordingReporting()
                self.session_manager = None

        return CI()

    def test_command_clear(self):
        ci = self.make_interface()
        ci.chat_session.history.add_message("user", "hi")
        ci.command_clear("/clear", [], "")
        assert ci.chat_session.history.num_messages() == 0
        assert ci.chat_session.session_title is None
        assert ("system", "Conversation history cleared") in ci.reporting.messages

    def test_command_debug_toggle(self):
        ci = self.make_interface()
        from lair.logging import logger

        original_level = logger.level
        ci.command_debug("/debug", [], "")
        first_level = logger.level
        ci.command_debug("/debug", [], "")
        second_level = logger.level

        assert first_level != original_level
        assert second_level != first_level

    def test_command_history_slice(self):
        ci = self.make_interface()
        for index in range(5):
            ci.chat_session.history.add_message("user", str(index))
        ci.command_history_slice("/history-slice", ["1:3"], "1:3")
        messages = ci.chat_session.history.get_messages()
        assert [message["content"] for message in messages] == ["1", "2"]
        assert any("History updated" in message for _, message in ci.reporting.messages)
