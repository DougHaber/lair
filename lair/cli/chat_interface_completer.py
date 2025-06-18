import re

import lair

from prompt_toolkit.completion import Completer
from prompt_toolkit.completion import Completion


class ChatInterfaceCompleter(Completer):
    def __init__(self, chat_interface, *args, **kwargs):
        self.chat_interface = chat_interface
        self.completion_handlers = {  # prefix -> handler
            "/mode ": lambda *args, **kwargs: self.get_completions__mode(*args, **kwargs),
            "/model ": lambda *args, **kwargs: self.get_completions__model(*args, **kwargs),
            "/prompt ": lambda *args, **kwargs: self.get_completions__prompt(*args, **kwargs),
            "/set ": lambda *args, **kwargs: self.get_completions__set(*args, **kwargs),
        }

        super().__init__(*args, **kwargs)

    def get_completions__mode(self, text):
        components = re.split(r"\s+", text)
        if len(components) > 2:
            return

        for mode in filter(lambda m: not m.startswith("_"), lair.config.modes.keys()):
            if mode.startswith(components[1]) and components[1] != mode:
                yield Completion(f"/mode {mode}", display=mode, start_position=-len(text))

    def get_completions__model(self, text):
        if self.chat_interface._models is None:
            return

        components = re.split(r"\s+", text)
        if len(components) > 2:
            return

        for model in sorted(self.chat_interface._models, key=lambda m: m["id"]):
            model_id = model["id"]
            if model_id.startswith(components[1]) and components[1] != model_id:
                yield Completion(f"/model {model_id}", display=model_id, start_position=-len(text))

    def get_completions__prompt(self, text):
        components = re.split(r"\s+", text, maxsplit=1)
        current_prompt = lair.config.get("session.system_prompt_template")
        if len(components) != 2:
            return

        if current_prompt.startswith(components[1]):
            yield Completion(f"/prompt {current_prompt}", display=current_prompt, start_position=-len(text))

    def get_completions__set(self, text):
        components = re.split(r"\s+", text, maxsplit=3)
        num_components = len(components)

        if num_components == 3:  # Provide the current value as an auto-complete choice
            key = components[1]
            value_raw = lair.config.get(key, allow_not_found=True)
            value = str(value_raw)

            if value_raw is None:
                if not components[2]:
                    # If the current value is None, show a <null> choice
                    yield Completion(f"/set {key}", display="<null>", start_position=-len(text))
            elif value.startswith(components[2]) and components[2] != value:
                yield Completion(f"/set {key} {value}", display=value, start_position=-len(text))
        else:
            for key in lair.config.active.keys():
                if key.startswith("_"):
                    continue
                elif key.startswith(components[1]) and components[1] != key:
                    yield Completion(f"/set {key}", display=key, start_position=-len(text))

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        for prefix, handler in self.completion_handlers.items():
            if text.startswith(prefix):
                yield from handler(text)
                return

        for command in sorted(self.chat_interface.commands.keys()):
            if command.startswith(text):
                yield Completion(command, start_position=-len(text))
