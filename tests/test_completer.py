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


def test_completer_edge_cases(monkeypatch):
    ci = make_interface(monkeypatch)
    # No models available
    ci._models = None
    comp = ChatInterfaceCompleter(ci)

    from prompt_toolkit.document import Document

    # /model with no cached models
    doc = Document("/model a", cursor_position=len("/model a"))
    assert list(comp.get_completions(doc, None)) == []

    # /mode with too many components
    doc = Document("/mode openai extra", cursor_position=len("/mode openai extra"))
    assert list(comp.get_completions(doc, None)) == []

    # /prompt without argument uses handler directly
    assert list(comp.get_completions__prompt("/prompt")) == []

    # /set value suggestions when key has value
    value_prefix = lair.config.get("model.name")[0]
    doc = Document(f"/set model.name {value_prefix}", cursor_position=len(f"/set model.name {value_prefix}"))
    results = [c.text for c in comp.get_completions(doc, None)]
    assert f"/set model.name {lair.config.get('model.name')}" in results

    # /set value suggestions when key is unset
    doc = Document("/set no.key ", cursor_position=len("/set no.key "))
    results = [c.text for c in comp.get_completions(doc, None)]
    assert "/set no.key" in results

    # /set key suggestions
    doc = Document("/set model.", cursor_position=len("/set model."))
    results = [c.text for c in comp.get_completions(doc, None)]
    assert any(r.startswith("/set model.") for r in results)
