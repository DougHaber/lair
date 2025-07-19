import argparse
import io
import os
import sys
from types import SimpleNamespace

import PIL
import pytest

import lair
from lair.modules.comfy import Comfy
from lair.util.argparse import ArgumentParserHelpException, ErrorRaisingArgumentParser


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

    with pytest.raises(Exception):  # noqa: B017 - function raises base Exception
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


def test_get_chat_command_parser(monkeypatch):
    module = make_module()
    order = []
    module._add_argparse_hunyuan_video_t2v = lambda sp: order.append("t2v")
    module._add_argparse_image = lambda sp: order.append("img")
    module._add_argparse_ltxv_i2v = lambda sp: order.append("i2v")
    module._add_argparse_ltxv_prompt = lambda sp: order.append("prompt")
    module._add_argparse_upscale = lambda sp: order.append("up")
    parser = module._get_chat_command_parser()
    assert order == ["t2v", "img", "i2v", "prompt", "up"]
    assert isinstance(parser, ErrorRaisingArgumentParser)


def test_on_chat_init(monkeypatch):
    module = make_module()
    cmd_holder = {}

    class DummyParser:
        def parse_args(self, args):
            raise ArgumentParserHelpException("help")

        def format_help(self):
            return "H"

    monkeypatch.setattr(module, "_get_chat_command_parser", lambda: DummyParser())
    errors = []
    chat_interface = SimpleNamespace(
        reporting=SimpleNamespace(error=lambda msg, show_exception=False: errors.append(msg)),
        register_command=lambda name, func, desc: cmd_holder.setdefault("func", func),
    )
    module._on_chat_init(chat_interface)
    cmd_holder["func"]("/comfy", ["--help"], "--help")
    assert errors == ["help"]

    # success path
    class OKParser:
        def parse_args(self, args):
            return argparse.Namespace(comfy_command="image", comfy_url="u")

    monkeypatch.setattr(module, "_get_chat_command_parser", lambda: OKParser())
    ran = []
    monkeypatch.setattr(module, "run", lambda params: ran.append(True))
    chat_interface = SimpleNamespace(
        reporting=SimpleNamespace(error=lambda *a, **k: None),
        register_command=lambda n, f, d: cmd_holder.update({"func2": f}),
    )
    module._on_chat_init(chat_interface)
    cmd_holder["func2"]("/comfy", [], "")
    assert ran


def test_save_output_save_to_disk(monkeypatch, tmp_path):
    module = make_module()

    class FakeImage:
        def __init__(self):
            self.saved = None

        def save(self, filename):
            self.saved = filename

    PIL.Image = SimpleNamespace(Image=FakeImage)
    img = FakeImage()
    target = tmp_path / "img.png"
    module._save_output__save_to_disk(img, str(target))
    assert img.saved == str(target)

    data_target = tmp_path / "b.dat"
    module._save_output__save_to_disk(b"123", str(data_target))
    assert data_target.read_bytes() == b"123"

    reader_target = tmp_path / "r.dat"
    module._save_output__save_to_disk(io.BytesIO(b"456"), str(reader_target))
    assert reader_target.read_bytes() == b"456"

    with pytest.raises(TypeError):
        module._save_output__save_to_disk(object(), str(tmp_path / "bad"))

    assert module.get_output_file_name("a.png").endswith("-upscaled.png")


def test_save_output_single_file(monkeypatch, tmp_path):
    module = make_module()
    calls = []
    monkeypatch.setattr(module, "_save_output__save_to_disk", lambda item, name: calls.append((item, name)))
    out_file = tmp_path / "out.png"
    module._save_output([b"data"], str(out_file), single_output=True)
    assert calls == [(b"data", str(out_file))]


def test_run_workflow_queue(monkeypatch, tmp_path):
    module = make_module()
    directory = tmp_path / "dir"
    directory.mkdir()
    file_path = tmp_path / "img.png"
    file_path.write_text("d")
    extra = tmp_path / "extra.png"
    captured = {"extend": 0, "process": []}
    monkeypatch.setattr(module, "_extend_queue_from_dir", lambda d, q: (q.append(str(extra)), captured.__setitem__("extend", captured["extend"] + 1)))
    monkeypatch.setattr(module, "_process_file", lambda f, a, fa, t: captured["process"].append(f))
    args = SimpleNamespace(recursive=True, skip_existing=False, comfy_command="image")
    module._run_workflow_queue(args, {}, {}, queue=[str(directory), str(file_path)], output_filename_template="tmpl")
    assert captured["extend"] == 1
    assert str(extra) in captured["process"] and str(file_path) in captured["process"]

    warnings = []
    monkeypatch.setattr(module, "_extend_queue_from_dir", lambda d, q: warnings.append("extend"))
    monkeypatch.setattr(module, "_process_file", lambda *a, **k: warnings.append("process"))
    monkeypatch.setattr(lair.modules.comfy.logger, "warning", lambda msg: warnings.append(msg))
    args = SimpleNamespace(recursive=False, skip_existing=False, comfy_command="image")
    module._run_workflow_queue(args, {}, {}, queue=[str(directory)], output_filename_template="tmpl")
    assert any("Use --recursive" in w for w in warnings)
    assert "extend" not in warnings and "process" not in warnings


def test_run_workflow_upscale(monkeypatch):
    module = make_module()
    captured = {}
    monkeypatch.setattr(module, "_run_workflow_queue", lambda a, d, f, *, queue, output_filename_template: captured.update({"queue": queue, "template": output_filename_template}))
    monkeypatch.setattr(lair.config, "get", lambda k: "tmpl" if k == "comfy.upscale.output_filename" else None)
    args = SimpleNamespace(comfy_command="upscale", scale_files=["a.png", "b.png"], recursive=False)
    module.run_workflow_upscale(args, {}, {})
    assert captured["queue"] == ["a.png", "b.png"]
    assert captured["template"] == "tmpl"


def test_run_workflow_default_single(monkeypatch):
    module = make_module()
    args = SimpleNamespace(comfy_command="image", repeat=1, output_file="o.png")
    called = []
    monkeypatch.setattr(module, "_save_output", lambda res, name, start_index=0, single_output=False: called.append(single_output))
    module.run_workflow_default(args, {"batch_size": 1}, {})
    assert called == [True]


def test_on_chat_init_argument_error(monkeypatch):
    module = make_module()
    errors = []
    class ErrParser:
        def parse_args(self, args):
            raise argparse.ArgumentError(None, "the following arguments are required: comfy_command")
        def format_help(self):
            return "HELP"
    monkeypatch.setattr(module, "_get_chat_command_parser", lambda: ErrParser())
    holder = {}
    chat_interface = SimpleNamespace(
        reporting=SimpleNamespace(error=lambda msg, show_exception=False: errors.append(msg)),
        register_command=lambda n, f, d: holder.setdefault("func", f),
    )
    module._on_chat_init(chat_interface)
    holder["func"]("/comfy", [], "")
    assert errors == ["HELP"]

    logs = []
    class BadParser:
        def parse_args(self, args):
            raise argparse.ArgumentError(None, "bad")
        def format_help(self):
            return "BADHELP"
    monkeypatch.setattr(module, "_get_chat_command_parser", lambda: BadParser())
    monkeypatch.setattr(lair.modules.comfy.logger, "error", lambda msg: logs.append(msg))
    chat_interface = SimpleNamespace(
        reporting=SimpleNamespace(error=lambda *a, **k: None),
        register_command=lambda n, f, d: holder.update({"func2": f}),
    )
    module._on_chat_init(chat_interface)
    holder["func2"]("/comfy", [], "")
    assert logs == ["bad"]
