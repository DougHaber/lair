import base64
from prompt_toolkit.document import Document
import lair
from lair.cli.chat_interface_completer import ChatInterfaceCompleter
from tests.test_chat_interface_extended import make_interface
import lair.util.core as core


def test_get_embedded_response(monkeypatch):
    ci = make_interface(monkeypatch)
    message = "<answer>(foo)</answer> \n```txt\nbar\n```"
    assert ci._get_embedded_response(message, 0) == "foo"
    assert ci._get_embedded_response(message, 1) == "bar"
    assert ci._get_embedded_response(message, -1) == "bar"
    assert ci._get_embedded_response(message, 2) is None


def test_completer(monkeypatch):
    ci = make_interface(monkeypatch)
    lair.config.set("session.system_prompt_template", "prompt text")
    ci._models = [{"id": "alpha"}, {"id": "beta"}]
    completer = ChatInterfaceCompleter(ci)

    doc = Document("/mode o", cursor_position=len("/mode o"))
    results = [c.text for c in completer.get_completions(doc, None)]
    assert "/mode openai" in results
    assert any(r in results for r in ["/mode openai_local", "/mode openai-dev"])

    doc = Document("/model a", cursor_position=len("/model a"))
    results = [c.text for c in completer.get_completions(doc, None)]
    assert "/model alpha" in results

    doc = Document("/prompt p", cursor_position=len("/prompt p"))
    results = [c.text for c in completer.get_completions(doc, None)]
    assert "/prompt prompt text" in results

    doc = Document("/set chat.multiline_input ", cursor_position=len("/set chat.multiline_input "))
    results = [c.text for c in completer.get_completions(doc, None)]
    assert any(r.startswith("/set chat.multiline_input") for r in results)

    doc = Document("/hist", cursor_position=len("/hist"))
    results = [c.text for c in completer.get_completions(doc, None)]
    assert "/history" in results


def test_get_attachments_content(monkeypatch, tmp_path):
    text_file = tmp_path / "a.txt"
    text_file.write_text("hello")
    img_file = tmp_path / "img.png"
    img_file.write_bytes(
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kBlcAAAAASUVORK5CYII=")
    )
    pdf_file = tmp_path / "a.pdf"
    pdf_file.write_text("dummy")
    monkeypatch.setattr(core, "read_pdf", lambda *a, **k: "pdfdata")
    parts, messages = core.get_attachments_content([str(img_file), str(pdf_file), str(text_file)])
    assert any(p["type"] == "image_url" for p in parts)
    joined = " ".join(m["content"] for m in messages)
    assert "pdfdata" in joined and "hello" in joined
