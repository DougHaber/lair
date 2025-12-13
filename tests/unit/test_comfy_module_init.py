import argparse
import sys
import types

import pytest

import lair
from lair.modules import comfy as comfy_mod


class DummyComfyCaller:
    def __init__(self):
        self.defaults = {
            "image": {},
            "hunyuan-video-t2v": {},
            "ltxv-i2v": {"output_format": "mp4"},
            "ltxv-prompt": {},
            "outpaint": {},
            "upscale": {},
        }

    def set_url(self, url):
        pass

    def run_workflow(self, command, **kwargs):
        return []


@pytest.mark.unit
def test_comfy_init_adds_commands_and_event(monkeypatch):
    subscribed = []
    monkeypatch.setattr(
        lair.events, "subscribe", lambda name, handler, instance=None: subscribed.append((name, instance))
    )
    dummy = types.SimpleNamespace(ComfyCaller=DummyComfyCaller)
    monkeypatch.setitem(sys.modules, "lair.comfy_caller", dummy)
    monkeypatch.setattr(lair, "comfy_caller", dummy, raising=False)
    order = []
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_hunyuan_video_t2v",
        lambda self, sp: (order.append("t2v"), sp.add_parser("hunyuan-video-t2v")),
    )
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_image",
        lambda self, sp: (order.append("img"), sp.add_parser("image")),
    )
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_ltxv_i2v",
        lambda self, sp: (order.append("i2v"), sp.add_parser("ltxv-i2v")),
    )
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_ltxv_prompt",
        lambda self, sp: (order.append("prompt"), sp.add_parser("ltxv-prompt")),
    )
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_outpaint",
        lambda self, sp: (order.append("outpaint"), sp.add_parser("outpaint")),
    )
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_upscale",
        lambda self, sp: (order.append("up"), sp.add_parser("upscale")),
    )
    parser = argparse.ArgumentParser(prog="test", add_help=False)
    module = comfy_mod.Comfy(parser)

    sp_action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    commands = {"image", "hunyuan-video-t2v", "ltxv-i2v", "ltxv-prompt", "outpaint", "upscale"}
    assert commands.issubset(set(sp_action.choices.keys()))
    assert subscribed == [("chat.init", module)]


@pytest.mark.unit
@pytest.mark.parametrize(
    "command, args, field, value",
    [
        ("image", [], "comfy_command", "image"),
        ("ltxv-i2v", [], "comfy_command", "ltxv-i2v"),
        ("ltxv-prompt", [], "comfy_command", "ltxv-prompt"),
        ("outpaint", [], "comfy_command", "outpaint"),
        ("upscale", [], "comfy_command", "upscale"),
    ],
)
def test_comfy_argument_parsing(monkeypatch, command, args, field, value):
    monkeypatch.setattr(lair.events, "subscribe", lambda *a, **k: None)
    dummy = types.SimpleNamespace(ComfyCaller=DummyComfyCaller)
    monkeypatch.setitem(sys.modules, "lair.comfy_caller", dummy)
    monkeypatch.setattr(lair, "comfy_caller", dummy, raising=False)
    monkeypatch.setattr(lair.config, "get", lambda *a, **k: None)
    monkeypatch.setattr(
        comfy_mod.Comfy,
        "_add_argparse_hunyuan_video_t2v",
        lambda self, sp: sp.add_parser("hunyuan-video-t2v"),
    )
    monkeypatch.setattr(comfy_mod.Comfy, "_add_argparse_image", lambda self, sp: sp.add_parser("image"))
    monkeypatch.setattr(comfy_mod.Comfy, "_add_argparse_ltxv_i2v", lambda self, sp: sp.add_parser("ltxv-i2v"))
    monkeypatch.setattr(comfy_mod.Comfy, "_add_argparse_ltxv_prompt", lambda self, sp: sp.add_parser("ltxv-prompt"))
    monkeypatch.setattr(comfy_mod.Comfy, "_add_argparse_outpaint", lambda self, sp: sp.add_parser("outpaint"))
    monkeypatch.setattr(comfy_mod.Comfy, "_add_argparse_upscale", lambda self, sp: sp.add_parser("upscale"))
    parser = argparse.ArgumentParser(prog="test", add_help=False)
    comfy_mod.Comfy(parser)

    parsed = parser.parse_args([command, *args])
    assert getattr(parsed, field) == value
    assert parsed.comfy_command == command


@pytest.mark.unit
def test_module_info_contents():
    info = comfy_mod._module_info()
    assert info["class"] is comfy_mod.Comfy and "description" in info
