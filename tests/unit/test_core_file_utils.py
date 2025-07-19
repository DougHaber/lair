import mimetypes
import os
import base64
import datetime
import subprocess
import pytest
import lair
import lair.util.core as core


def test_safe_dump_and_file_ops(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    filename = "~/test.txt"
    core.save_file(filename, "hello")
    assert core.slurp_file(filename) == "hello"

    data = {"time": datetime.datetime(2000, 1, 1, 0, 0)}
    json_name = tmp_path / "data.json"
    core.save_json_file(json_name, data)
    loaded = core.load_json_file(json_name)
    assert loaded["time"].startswith("2000-01-01")


def test_misc_utils(monkeypatch):
    assert "editor_command" in core.read_package_file("lair.files", "settings.yaml")
    assert os.path.isdir(os.path.normpath(core.get_lib_path("")))

    original = lair.logging.logger.level
    lair.logging.logger.setLevel("DEBUG")
    try:
        assert core.is_debug_enabled()
        assert core.get_log_level() == "DEBUG"
    finally:
        lair.logging.logger.setLevel(original)

    assert core.strip_escape_codes("abc\033[31mdef") == "abcdef"
    assert core.get_message("a", "b") == {"role": "a", "content": "b"}


def test_expand_filename_list_errors(tmp_path):
    with pytest.raises(Exception):
        core.expand_filename_list([str(tmp_path / "nofile")])

    f = tmp_path / "a.txt"
    f.write_text("x")
    res = core.expand_filename_list([str(f)], sort_results=False)
    assert res == [str(f)]


def test_image_attachment(tmp_path, monkeypatch):
    img = tmp_path / "img.png"
    img.write_bytes(
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kBlcAAAAASUVORK5CYII=")
    )
    monkeypatch.setattr(lair.config, "active", {**lair.config.active, "misc.provide_attachment_filenames": True})
    parts = core._get_attachments_content__image_file(str(img))
    assert parts[0]["type"] == "text"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


class DummyPage:
    def __init__(self, text):
        self.text = text

    def extract_text(self, x_tolerance=0, y_tolerance=0):
        return self.text


class DummyPDF:
    def __init__(self, texts):
        self.pages = [DummyPage(t) for t in texts]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


def test_read_pdf_limits(tmp_path, monkeypatch):
    dummy_file = tmp_path / "x.pdf"
    dummy_file.write_text("data")
    monkeypatch.setattr(core.pdfplumber, "open", lambda f: DummyPDF(["abc", "def", "ghi"]))
    monkeypatch.setattr(
        lair.config,
        "active",
        {**lair.config.active, "misc.text_attachment_max_size": 5, "misc.text_attachment_truncate": True},
    )
    out = core.read_pdf(dummy_file, enforce_limits=True)
    assert len(out) == 5
    monkeypatch.setattr(lair.config, "active", {**lair.config.active, "misc.text_attachment_truncate": False})
    with pytest.raises(Exception):
        core.read_pdf(dummy_file, enforce_limits=True)


def test_pdf_and_text_files(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "read_pdf", lambda f: "pdf")
    msg = core._get_attachments_content__pdf_file("a.pdf")
    assert "pdf" in msg["content"]

    textfile = tmp_path / "t.txt"
    textfile.write_text("abcdef")
    monkeypatch.setattr(
        lair.config,
        "active",
        {**lair.config.active, "misc.text_attachment_max_size": 3, "misc.text_attachment_truncate": True},
    )
    msg2 = core._get_attachments_content__text_file(str(textfile))
    assert msg2["content"].endswith("abc")

    textfile.write_bytes(b"\xff\xfe")
    with pytest.raises(Exception):
        core._get_attachments_content__text_file(str(textfile))


def test_edit_content_in_editor(monkeypatch):
    monkeypatch.setattr(lair.config, "active", {**lair.config.active, "misc.editor_command": "dummy"})

    def fake_run(cmd, check):
        with open(cmd[-1], "w") as fd:
            fd.write("new")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = core.edit_content_in_editor("old")
    assert result == "new"


def test_image_file_wrong_mime(tmp_path, monkeypatch):
    img = tmp_path / "img.png"
    img.write_bytes(b"data")
    monkeypatch.setattr(mimetypes, "guess_type", lambda f: ("text/plain", None))
    with pytest.raises(ValueError):
        core._get_attachments_content__image_file(str(img))


def test_pdf_header(monkeypatch):
    monkeypatch.setattr(core, "read_pdf", lambda f: "content")
    monkeypatch.setattr(lair.config, "active", {**lair.config.active, "misc.provide_attachment_filenames": True})
    msg = core._get_attachments_content__pdf_file("file.pdf")
    assert msg["content"].startswith("User provided file: filename=file.pdf")


def test_text_file_limits(tmp_path, monkeypatch):
    f = tmp_path / "t.txt"
    f.write_text("abcdef")
    monkeypatch.setattr(
        lair.config,
        "active",
        {**lair.config.active, "misc.text_attachment_max_size": 3, "misc.text_attachment_truncate": False},
    )
    with pytest.raises(Exception):
        core._get_attachments_content__text_file(str(f))

    monkeypatch.setattr(
        lair.config,
        "active",
        {
            **lair.config.active,
            "misc.text_attachment_max_size": 10,
            "misc.text_attachment_truncate": False,
            "misc.provide_attachment_filenames": True,
        },
    )
    msg = core._get_attachments_content__text_file(str(f))
    assert msg["content"].startswith(f"User provided file: filename={f}")
