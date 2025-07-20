"""Prompt Toolkit completer for the interactive chat interface."""

from __future__ import annotations

import re
from collections.abc import Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

import lair

from .chat_interface import ChatInterface


class ChatInterfaceCompleter(Completer):
    """Provide tab completion for chat interface commands."""

    def __init__(self, chat_interface: ChatInterface, *args: object, **kwargs: object) -> None:
        """
        Initialize the completer.

        Args:
            chat_interface: The chat interface instance the completer is attached to.
            *args: Positional arguments forwarded to ``Completer``.
            **kwargs: Keyword arguments forwarded to ``Completer``.

        """
        self.chat_interface = chat_interface
        self.completion_handlers = {  # prefix -> handler
            "/mode ": lambda *args, **kwargs: self.get_completions__mode(*args, **kwargs),
            "/model ": lambda *args, **kwargs: self.get_completions__model(*args, **kwargs),
            "/prompt ": lambda *args, **kwargs: self.get_completions__prompt(*args, **kwargs),
            "/set ": lambda *args, **kwargs: self.get_completions__set(*args, **kwargs),
        }

        super().__init__(*args, **kwargs)

    def get_completions__mode(self, text: str) -> Iterable[Completion]:
        """
        Yield completions for the ``/mode`` command.

        Args:
            text: The text entered so far.

        Yields:
            Completion objects for matching modes.

        """
        components = re.split(r"\s+", text)
        if len(components) > 2:
            return

        for mode in filter(lambda m: not m.startswith("_"), lair.config.modes.keys()):
            if mode.startswith(components[1]) and components[1] != mode:
                yield Completion(f"/mode {mode}", display=mode, start_position=-len(text))

    def get_completions__model(self, text: str) -> Iterable[Completion]:
        """
        Yield completions for the ``/model`` command.

        Args:
            text: The text entered so far.

        Yields:
            Completion objects for available models.

        """
        if self.chat_interface._models is None:
            return

        components = re.split(r"\s+", text)
        if len(components) > 2:
            return

        for model in sorted(self.chat_interface._models, key=lambda m: m["id"]):
            model_id = model["id"]
            if model_id.startswith(components[1]) and components[1] != model_id:
                yield Completion(f"/model {model_id}", display=model_id, start_position=-len(text))

    def get_completions__prompt(self, text: str) -> Iterable[Completion]:
        """
        Yield completions for the ``/prompt`` command.

        Args:
            text: The text entered so far.

        Yields:
            Completion objects for the current system prompt template.

        """
        components = re.split(r"\s+", text, maxsplit=1)
        current_prompt = lair.config.get("session.system_prompt_template")
        if len(components) != 2:
            return

        if current_prompt.startswith(components[1]):
            yield Completion(f"/prompt {current_prompt}", display=current_prompt, start_position=-len(text))

    def _get_set_value_completion(self, components: list[str], text: str) -> Iterable[Completion]:
        """
        Yield value completions for the ``/set`` command.

        Args:
            components: The parsed command components.
            text: The text entered so far.

        Yields:
            Completion objects for configuration values.

        """
        key = components[1]
        value_raw = lair.config.get(key, allow_not_found=True)
        value = str(value_raw)

        if value_raw is None and not components[2]:
            yield Completion(f"/set {key}", display="<null>", start_position=-len(text))
        elif value_raw is not None and value.startswith(components[2]) and components[2] != value:
            yield Completion(f"/set {key} {value}", display=value, start_position=-len(text))

    def _get_set_key_completion(self, prefix: str, text: str) -> Iterable[Completion]:
        """
        Yield key completions for the ``/set`` command.

        Args:
            prefix: The config key prefix typed so far.
            text: The text entered so far.

        Yields:
            Completion objects for configuration keys.

        """
        for key in lair.config.active:
            if key.startswith("_"):
                continue
            if key.startswith(prefix) and prefix != key:
                yield Completion(f"/set {key}", display=key, start_position=-len(text))

    def get_completions__set(self, text: str) -> Iterable[Completion]:
        """
        Yield completions for the ``/set`` command.

        Args:
            text: The text entered so far.

        Yields:
            Completion objects for matching configuration keys or values.

        """
        components = re.split(r"\s+", text, maxsplit=3)

        if len(components) == 3:
            yield from self._get_set_value_completion(components, text)
        else:
            yield from self._get_set_key_completion(components[1], text)

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        """
        Return completions based on the current document.

        Args:
            document: The current prompt-toolkit document.
            complete_event: The completion trigger event.

        Yields:
            Completion objects for the active command.

        """
        text = document.text_before_cursor

        for prefix, handler in self.completion_handlers.items():
            if text.startswith(prefix):
                yield from handler(text)
                return

        for command in sorted(self.chat_interface.commands.keys()):
            if command.startswith(text):
                yield Completion(command, start_position=-len(text))
