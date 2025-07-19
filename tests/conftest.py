import inspect
from pathlib import Path

import pytest

_FILE_CACHE: dict[Path, str] = {}


def _read_file(path: Path) -> str:
    if path not in _FILE_CACHE:
        try:
            _FILE_CACHE[path] = path.read_text()
        except OSError:
            _FILE_CACHE[path] = ""
    return _FILE_CACHE[path]


def _uses_clirunner(item: pytest.Item) -> bool:
    try:
        source = inspect.getsource(item.obj)
    except (OSError, TypeError):
        source = ""
    if "CliRunner" in source:
        return True
    file_text = _read_file(Path(str(item.fspath)))
    return "CliRunner" in file_text


TESTS_ROOT = Path(__file__).resolve().parent
INTEGRATION_DIR = TESTS_ROOT / "integration"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if "integration" in item.keywords or "unit" in item.keywords:
            continue

        path = Path(str(item.fspath)).resolve()
        if INTEGRATION_DIR in path.parents or _uses_clirunner(item):
            item.add_marker("integration")
        else:
            item.add_marker("unit")
