import argparse
import sys
import io
import types

import lair
from lair.modules import comfy as comfy_mod
import pytest


class DummyComfyCaller:
    def __init__(self):
        cmds = [
            "hunyuan-video-t2v",
            "image",
            "ltxv-i2v",
            "ltxv-prompt",
            "outpaint",
            "upscale",
        ]
        self.defaults = {c: {"batch_size": 1} for c in cmds}
        self.called = []
        self.url = None

    def run_workflow(self, command, **kwargs):
        self.called.append((command, kwargs))
        return [b"result"]

    def set_url(self, url):
        self.url = url


@pytest.fixture
def comfy(monkeypatch):
    obj = comfy_mod.Comfy.__new__(comfy_mod.Comfy)
    obj.comfy = DummyComfyCaller()
    obj._image_file_extensions = {".jpg"}
    return obj


def test_save_output_to_stdout(comfy, monkeypatch):
    buf = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", types.SimpleNamespace(buffer=buf))
    comfy._save_output([b"abc"], "-", single_output=True)
    assert buf.getvalue() == b"abc\n"


def test_save_output_multiple_files(tmp_path, comfy):
    records = []
    comfy._save_output__save_to_disk = lambda item, name: records.append((item, name))
    file = tmp_path / "out.png"
    comfy._save_output([b"a", b"b"], str(file), start_index=1)
    assert records[0][1].endswith("000001.png")
    assert records[1][1].endswith("000002.png")


@pytest.mark.parametrize("filename", ["-", "outfile"])
def test_save_output_invalid(filename, comfy):
    if filename == "-":
        with pytest.raises(Exception):
            comfy._save_output([b"a"], filename)
    else:
        with pytest.raises(ValueError):
            comfy._save_output([b"a", b"b"], filename)


def test_save_output_save_to_disk(tmp_path, comfy, monkeypatch):
    image_path = tmp_path / "img.bin"
    dummy_image_type = type("Img", (), {"save": lambda self, fn: fn})
    monkeypatch.setattr(sys.modules["PIL"], "Image", types.SimpleNamespace(Image=dummy_image_type), raising=False)
    comfy._save_output__save_to_disk(b"data", str(image_path))
    assert image_path.read_bytes() == b"data"
    image_path2 = tmp_path / "img2.bin"
    file_like = io.BytesIO(b"xyz")
    comfy._save_output__save_to_disk(file_like, str(image_path2))
    assert image_path2.read_bytes() == b"xyz"
    with pytest.raises(TypeError):
        comfy._save_output__save_to_disk(123, str(image_path2))


def test_extend_queue_from_dir(tmp_path, comfy):
    dir_path = tmp_path / "d"
    dir_path.mkdir()
    sub = dir_path / "sub"
    sub.mkdir()
    img = dir_path / "img.jpg"
    txt = dir_path / "file.txt"
    img.touch()
    txt.touch()
    q = []
    comfy._extend_queue_from_dir(str(dir_path), q)
    assert str(img.absolute()) in q
    assert str(sub.absolute()) in q
    assert str(txt.absolute()) not in q


def test_process_file_skip_and_error(tmp_path, comfy, monkeypatch):
    template = "{basename}.png"
    args = argparse.Namespace(comfy_command="image", skip_existing=True)
    existing = tmp_path / "source.png"
    existing.touch()
    # Should skip due to existing file
    called = []
    monkeypatch.setattr(comfy.comfy, "run_workflow", lambda *a, **k: called.append(True))
    comfy._process_file(str(tmp_path / "source.jpg"), args, {}, template)

    assert called == []
    # Now file does not exist and workflow returns empty
    args.skip_existing = False

    def run_none(cmd, **kwargs):
        return []

    monkeypatch.setattr(comfy.comfy, "run_workflow", run_none)
    with pytest.raises(ValueError):
        comfy._process_file(str(tmp_path / "new.jpg"), args, {}, template)

    # Success path
    args.skip_existing = False
    out = []
    monkeypatch.setattr(comfy.comfy, "run_workflow", lambda *a, **k: [b"ok"])
    monkeypatch.setattr(comfy, "_save_output", lambda data, name, **kw: out.append(name))
    comfy._process_file(str(tmp_path / "file.jpg"), args, {}, template)
    assert out and out[0].endswith("file.png")


def test_run_workflow_outpaint(monkeypatch, comfy):
    args = argparse.Namespace(padding="1x2x3x4", outpaint_files=["img.jpg"], recursive=False)
    defaults = {}
    func_args = {}
    outputs = []
    monkeypatch.setattr(
        comfy, "_run_workflow_queue", lambda a, b, c, *, queue, output_filename_template: outputs.append((queue, c))
    )
    monkeypatch.setattr(lair.config, "get", lambda k: "{basename}.png")
    comfy.run_workflow_outpaint(args, defaults, func_args)
    assert func_args == {"padding_top": 1, "padding_right": 2, "padding_bottom": 3, "padding_left": 4}
    assert outputs[0][0] == ["img.jpg"]

    with pytest.raises(ValueError):
        comfy.run_workflow_outpaint(
            argparse.Namespace(padding="1x2x3", outpaint_files=[], recursive=False), defaults, {}
        )
    with pytest.raises(ValueError):
        comfy.run_workflow_outpaint(
            argparse.Namespace(padding="1x2xthreex4", outpaint_files=[], recursive=False), defaults, {}
        )


def test_run_workflow_default(monkeypatch, comfy):
    args = argparse.Namespace(comfy_command="image", repeat=2, output_file="file.png")
    outputs = []
    monkeypatch.setattr(comfy.comfy, "run_workflow", lambda cmd, **kw: [b"d"])
    monkeypatch.setattr(
        comfy,
        "_save_output",
        lambda data, fname, start_index=0, single_output=False: outputs.append((fname, start_index)),
    )
    comfy.run_workflow_default(args, {"batch_size": 1}, {})
    assert outputs == [("file.png", 0), ("file.png", 1)]

    monkeypatch.setattr(comfy.comfy, "run_workflow", lambda *a, **kw: [])
    with pytest.raises(ValueError):
        comfy.run_workflow_default(argparse.Namespace(comfy_command="image", repeat=1, output_file="f.png"), {}, {})


def test_run(monkeypatch, tmp_path, comfy):
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("hello")
    calls = []
    monkeypatch.setattr(comfy, "run_workflow_upscale", lambda a, b, c: calls.append("upscale"))
    args = argparse.Namespace(
        comfy_command="upscale",
        comfy_url="http://example",
        prompt_file=str(prompt_file),
        scale_files=["f"],
    )
    monkeypatch.setattr(lair.util, "slurp_file", lambda f: "content")
    comfy.run(args)
    assert comfy.comfy.url == "http://example"
    assert calls == ["upscale"]


def test_get_output_file_name(comfy):
    assert comfy.get_output_file_name("img.png") == "img-upscaled.png"


def test_run_workflow_queue(monkeypatch, tmp_path, comfy):
    dir_path = tmp_path / "d"
    dir_path.mkdir()
    file_path = tmp_path / "f.jpg"
    file_path.touch()
    processed = []
    extended = []
    warnings = []
    monkeypatch.setattr(comfy, "_process_file", lambda f, a, b, c: processed.append(f))
    monkeypatch.setattr(comfy, "_extend_queue_from_dir", lambda d, q: extended.append(d))
    monkeypatch.setattr(comfy_mod.logger, "warning", lambda msg: warnings.append(msg))

    args = argparse.Namespace(recursive=False, skip_existing=False, comfy_command="image")
    comfy._run_workflow_queue(args, {}, {}, queue=[str(dir_path), str(file_path)], output_filename_template="{basename}.png")
    assert processed == [str(file_path)]
    assert extended == []
    assert warnings and str(dir_path) in warnings[0]


def test_run_workflow_queue_recursive(monkeypatch, tmp_path, comfy):
    dir_path = tmp_path / "d"
    dir_path.mkdir()
    file_path = tmp_path / "f.jpg"
    file_path.touch()
    processed = []
    extended = []
    monkeypatch.setattr(comfy, "_process_file", lambda f, a, b, c: processed.append(f))
    monkeypatch.setattr(comfy, "_extend_queue_from_dir", lambda d, q: extended.append(d))

    args = argparse.Namespace(recursive=True, skip_existing=False, comfy_command="image")
    comfy._run_workflow_queue(args, {}, {}, queue=[str(dir_path), str(file_path)], output_filename_template="{basename}.png")
    assert processed == [str(file_path)]
    assert extended == [str(dir_path)]
