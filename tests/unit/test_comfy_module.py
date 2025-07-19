import io
import os
import sys
import pathlib
from types import SimpleNamespace

import pytest

import lair
from lair.modules.comfy import Comfy


class DummyComfyCaller:
    def __init__(self):
        self.defaults = {
            "image": {
                "batch_size": 1,
                "cfg": 1.0,
                "output_height": 10,
                "output_width": 10,
                "model_name": "model",
                "negative_prompt": "",
                "steps": 1,
                "sampler": "euler",
                "scheduler": "normal",
                "seed": None,
                "loras": None,
                "prompt": "",
            },
            "outpaint": {
                "padding_top": 0,
                "padding_right": 0,
                "padding_bottom": 0,
                "padding_left": 0,
                "cfg": 1.0,
                "denoise": 1.0,
                "feathering": 0,
                "grow_mask_by": 0,
                "model_name": "model",
                "negative_prompt": "",
                "sampler": "euler",
                "scheduler": "normal",
                "seed": None,
                "steps": 1,
                "loras": None,
                "prompt": "",
            },
            "upscale": {"model_name": "model"},
        }
        self.set_url_called = None
        self.return_value = [b"data"]
        self.run_calls = []

    def set_url(self, url):
        self.set_url_called = url

    def run_workflow(self, command, **kwargs):
        self.run_calls.append((command, kwargs))
        return self.return_value


def make_module(caller=None):
    module = object.__new__(Comfy)
    module.comfy = caller or DummyComfyCaller()
    module._image_file_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
    return module


def test_save_output_stdout(monkeypatch):
    module = make_module()
    monkeypatch.setattr(
        module, "_save_output__save_to_disk", lambda *a, **k: (_ for _ in ()).throw(Exception("should not save"))
    )
    buffer = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=buffer))
    module._save_output([b"x"], "-", single_output=True)
    assert buffer.getvalue() == b"x\n"


def test_save_output_multiple(monkeypatch, tmp_path):
    module = make_module()
    calls = []
    monkeypatch.setattr(module, "_save_output__save_to_disk", lambda item, name: calls.append((item, name)))
    module._save_output([b"a", b"b"], str(tmp_path / "out.png"))
    assert calls[0][1].endswith("000000.png")
    assert calls[1][1].endswith("000001.png")

    with pytest.raises(Exception):
        module._save_output([b"a"], "-", single_output=False)
    with pytest.raises(ValueError):
        module._save_output([b"a"], "noext")


def test_extend_queue_from_dir(tmp_path):
    module = make_module()
    (tmp_path / "dir").mkdir()
    (tmp_path / "good.PNG").write_text("a")
    (tmp_path / "bad.txt").write_text("b")
    queue: list[str] = []
    module._extend_queue_from_dir(tmp_path, queue)
    expected = {str((tmp_path / "dir").absolute()), str((tmp_path / "good.PNG").absolute())}
    assert expected.issubset(set(queue))
    assert str((tmp_path / "bad.txt").absolute()) not in queue


def test_process_file(monkeypatch, tmp_path):
    module = make_module()
    src = tmp_path / "img.jpg"
    src.write_text("data")
    template = str(tmp_path / "{basename}_out.png")
    expected_output = template.format(basename=os.path.splitext(str(src))[0])
    args = SimpleNamespace(comfy_command="image", skip_existing=True)
    module.comfy.return_value = [b"new"]
    called = []
    monkeypatch.setattr(module, "_save_output", lambda res, name, **k: called.append(name))
    monkeypatch.setattr(os.path, "exists", lambda p: p == expected_output)
    module._process_file(str(src), args, {}, template)
    assert not called  # skipped because file exists

    monkeypatch.setattr(os.path, "exists", lambda p: False)
    module._process_file(str(src), args, {}, template)
    assert called == [expected_output]

    module.comfy.return_value = []
    with pytest.raises(ValueError):
        module._process_file(str(src), args, {}, template)


def test_run_workflow_outpaint(monkeypatch):
    module = make_module()
    args = SimpleNamespace(
        comfy_command="outpaint",
        padding="1x2x3x4",
        outpaint_files=["a.png"],
        recursive=False,
    )
    captured = {}
    monkeypatch.setattr(
        module,
        "_run_workflow_queue",
        lambda a, d, f, *, queue, output_filename_template: captured.update(
            {"queue": queue, "tmpl": output_filename_template, "args": f}
        ),
    )
    monkeypatch.setattr(lair.config, "get", lambda k: "tpl" if k == "comfy.outpaint.output_filename" else None)
    module.run_workflow_outpaint(args, {}, {})
    assert captured["queue"] == ["a.png"]
    assert captured["tmpl"] == "tpl"
    assert captured["args"]["padding_top"] == 1
    assert captured["args"]["padding_right"] == 2

    with pytest.raises(ValueError):
        module.run_workflow_outpaint(
            SimpleNamespace(comfy_command="outpaint", padding="1x2x3", outpaint_files=[]), {}, {}
        )
    with pytest.raises(ValueError):
        module.run_workflow_outpaint(
            SimpleNamespace(comfy_command="outpaint", padding="1x2xthreex4", outpaint_files=[]), {}, {}
        )


def test_run_workflow_default(monkeypatch):
    module = make_module()
    args = SimpleNamespace(comfy_command="image", repeat=2, output_file="o.png")
    captured = []
    monkeypatch.setattr(
        module,
        "_save_output",
        lambda res, name, start_index=0, single_output=False: captured.append((start_index, single_output)),
    )
    module.run_workflow_default(args, {"batch_size": 1}, {})
    assert captured == [(0, False), (1, False)]

    module.comfy.return_value = []
    with pytest.raises(ValueError):
        module.run_workflow_default(
            SimpleNamespace(comfy_command="image", repeat=1, output_file="o.png"), {"batch_size": 1}, {}
        )


def test_run(monkeypatch, tmp_path):
    caller = DummyComfyCaller()
    module = make_module(caller)
    args = SimpleNamespace(
        comfy_command="image",
        comfy_url="http://server",
        prompt_file=str(tmp_path / "p.txt"),
        output_file="o.png",
        repeat=1,
    )
    (tmp_path / "p.txt").write_text("prompt")
    monkeypatch.setattr(lair.util, "slurp_file", lambda p: "promptfile")
    called = []
    monkeypatch.setattr(module, "run_workflow_default", lambda a, b, c: called.append(c))
    module.run(args)
    assert caller.set_url_called == "http://server"
    assert called and called[0]["prompt"] == "promptfile"

    args2 = SimpleNamespace(
        comfy_command="outpaint",
        comfy_url="http://server",
        padding=None,
        outpaint_files=[],
        recursive=False,
    )
    called.clear()
    monkeypatch.setattr(module, "run_workflow_outpaint", lambda a, b, c: called.append("outpaint"))
    module.run(args2)
    assert called == ["outpaint"]
