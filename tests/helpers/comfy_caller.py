import importlib
import sys


def get_ComfyCaller():
    if "lair.comfy_caller" in sys.modules:
        mod = importlib.reload(sys.modules["lair.comfy_caller"])
    else:
        mod = importlib.import_module("lair.comfy_caller")
    return mod.ComfyCaller
