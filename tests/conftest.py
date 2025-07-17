import sys
import types

modules_to_stub = [
    "diffusers",
    "transformers",
    "torch",
    "comfy_script",
    "lair.comfy_caller",
    "trafilatura",
    "PIL",
    "duckduckgo_search",
    "yaml",
    "requests",
    "libtmux",
    "lmdb",
    "openai",
]

for name in modules_to_stub:
    module = sys.modules.setdefault(name, types.ModuleType(name))
    if name == "duckduckgo_search":
        module.DDGS = object
    elif name == "pdfplumber":
        # pdfplumber is only used in tests and may not be installed. Provide a
        # minimal stub so monkeypatching works without raising AttributeError.
        module.open = lambda *args, **kwargs: None
    elif name == "yaml":
        module.safe_load = lambda *a, **k: {}


def pytest_collection_modifyitems(config, items):
    import pytest

    for item in items:
        if "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)
