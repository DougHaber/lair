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
