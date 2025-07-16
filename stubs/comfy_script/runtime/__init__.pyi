from typing import Any, ContextManager

class Workflow(ContextManager[Any]):
    ...

queue: Any


def load(url: str) -> None: ...
