from typing import Any
class Chat:
    completions: Any
class Models:
    def list(self) -> Any: ...
class OpenAI:
    chat: Chat
    models: Models
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
